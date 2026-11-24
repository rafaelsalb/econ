from __future__ import annotations

from econ import config
from econ.lockbox import LEDGER, lockbox_status, open_lockbox


def test_lockbox_ledger_exists_and_is_one_time():
    if not LEDGER.exists():
        import pytest

        pytest.skip("lockbox not opened in this checkout")
    status = lockbox_status()
    assert status is not None
    assert status["lockbox_start"] == "2020-01-01"
    assert status["lockbox_end"] == "2026-10-31"
    assert status["rows"] > 0
    # A second open must be refused without an explicit force reason.
    import pytest

    with pytest.raises(RuntimeError):
        open_lockbox()


def test_phase3_outputs_exist():
    assert (config.EVAL / "ensemble_scoreboard.csv").exists()
    assert (config.REPORTS / "fan_chart.png").exists()
    assert (config.REPORTS / "disagreement.csv").exists()
    assert (config.REPORTS / "final_report.md").exists()
    if LEDGER.exists():
        assert (config.REPORTS / "lockbox_report.md").exists()
        assert (config.EVAL / "lockbox_scoreboard.csv").exists()
