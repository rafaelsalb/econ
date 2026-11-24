"""Minimal CONNECT-only egress proxy with a host allowlist.

The proxy never decrypts TLS. It allows a connection only when the CONNECT
target is on ALLOW_HOSTS (exact or a subdomain), logs destination and byte
counts as JSON, and refuses everything else.

Environment:
  ALLOW_HOSTS  comma-separated hostnames (e.g. "opencode.ai,models.dev")
  PORT         listen port, default 3128
"""

from __future__ import annotations

import asyncio
import json
import os
import time

ALLOW = {h.strip().lower() for h in os.environ.get("ALLOW_HOSTS", "").split(",") if h.strip()}
PORT = int(os.environ.get("PORT", "3128"))


def allowed(host: str) -> bool:
    host = host.lower().strip("[]")
    return host in ALLOW or any(host.endswith("." + a) for a in ALLOW)


async def _pump(reader: asyncio.StreamReader, writer: asyncio.StreamWriter, counter: list[int]):
    try:
        while True:
            data = await reader.read(65536)
            if not data:
                break
            writer.write(data)
            await writer.drain()
            counter[0] += len(data)
    except Exception:
        pass
    finally:
        try:
            writer.close()
        except Exception:
            pass


async def handle(reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
    started = time.time()
    line = await reader.readline()
    if not line:
        writer.close()
        return
    parts = line.decode(errors="replace").split()
    log = {
        "ts": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "method": parts[0] if parts else None,
        "target": parts[1] if len(parts) > 1 else None,
    }
    if len(parts) < 2 or parts[0] != "CONNECT":
        writer.write(b"HTTP/1.1 405 Method Not Allowed\r\n\r\n")
        await writer.drain()
        writer.close()
        log["status"] = 405
        print(json.dumps(log), flush=True)
        return

    target = parts[1]
    host, _, port_s = target.partition(":")
    try:
        port = int(port_s or 443)
    except ValueError:
        port = 443
    log.update({"host": host, "port": port, "allowed": allowed(host)})

    if not allowed(host):
        writer.write(b"HTTP/1.1 403 Forbidden\r\n\r\n")
        await writer.drain()
        writer.close()
        log["status"] = 403
        print(json.dumps(log), flush=True)
        return

    while True:
        header = await reader.readline()
        if header in (b"\r\n", b"\n", b""):
            break

    try:
        up_reader, up_writer = await asyncio.open_connection(host, port)
    except Exception as exc:  # noqa: BLE001
        writer.write(b"HTTP/1.1 502 Bad Gateway\r\n\r\n")
        await writer.drain()
        writer.close()
        log.update({"status": 502, "error": str(exc)[:200]})
        print(json.dumps(log), flush=True)
        return

    writer.write(b"HTTP/1.1 200 Connection Established\r\n\r\n")
    await writer.drain()

    up = [0]
    down = [0]
    tasks = [
        asyncio.create_task(_pump(reader, up_writer, up)),
        asyncio.create_task(_pump(up_reader, writer, down)),
    ]
    await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
    for task in tasks:
        task.cancel()
    await asyncio.gather(*tasks, return_exceptions=True)

    log.update(
        {
            "status": 200,
            "bytes_client_to_server": up[0],
            "bytes_server_to_client": down[0],
            "duration_s": round(time.time() - started, 3),
        }
    )
    print(json.dumps(log), flush=True)


async def main():
    server = await asyncio.start_server(handle, "0.0.0.0", PORT)
    print(json.dumps({"event": "listen", "port": PORT, "allow": sorted(ALLOW)}), flush=True)
    async with server:
        await server.serve_forever()


if __name__ == "__main__":
    asyncio.run(main())
