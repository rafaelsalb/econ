from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd

from ..targets import compound, inflation_12m_from_path, month_of, quarter_of
from .base import Forecast


def ipca_rows(
    path: pd.Series,
    known: pd.Series,
    origin: date,
    horizons_12m: tuple[int, ...] = (3, 6, 12),
) -> list[Forecast]:
    """Expand a monthly IPCA path (origin month .. +12) into registry rows."""
    m0 = month_of(origin)
    required = pd.period_range(m0, m0 + 12, freq="M")
    missing = [p for p in required if p not in path.index]
    if missing:
        raise ValueError(f"IPCA path missing months: {missing}")
    anchor_m = float(known.iloc[-1])
    anchor_12 = compound(known.loc[m0 - 12 : m0 - 1])
    full = pd.concat([known, path]).sort_index()
    full = full[~full.index.duplicated(keep="last")]

    rows: list[Forecast] = []
    for h in range(0, 13):
        p = m0 + h
        rows.append(
            Forecast(
                target="ipca_m",
                horizon=h,
                ref_date=p.end_time.date(),
                point=float(path.loc[p]),
                anchor=anchor_m,
            )
        )
    for h in horizons_12m:
        p = m0 + h
        rows.append(
            Forecast(
                target="ipca_12m",
                horizon=h,
                ref_date=p.end_time.date(),
                point=float(inflation_12m_from_path(full, p)),
                anchor=anchor_12,
            )
        )
    return rows


def gdp_rows(values: dict[int, float], origin: date, anchor: float) -> list[Forecast]:
    q0 = quarter_of(origin)
    rows = []
    for h in range(0, 5):
        q = q0 + h
        rows.append(
            Forecast(
                target="gdp_qq",
                horizon=h,
                ref_date=q.end_time.date(),
                point=float(values[h]),
                anchor=float(anchor),
            )
        )
    return rows


def selic_rows(
    path: pd.Series,
    origin: date,
    anchor: float,
    horizons: tuple[int, ...] = (0, 3, 6, 12),
) -> list[Forecast]:
    m0 = month_of(origin)
    rows = []
    for h in horizons:
        p = m0 + h
        if p not in path.index:
            raise ValueError(f"Selic path missing {p}")
        rows.append(
            Forecast(
                target="selic",
                horizon=h,
                ref_date=p.end_time.date(),
                point=float(path.loc[p]),
                anchor=float(anchor),
            )
        )
    return rows


def fit_ar(y: np.ndarray, max_p: int) -> tuple[int, np.ndarray]:
    """OLS AR(p) with BIC selection and a constant."""
    y = np.asarray(y, dtype=float)
    y = y[np.isfinite(y)]
    best_bic = np.inf
    best = (1, np.array([float(np.mean(y))]))
    for p in range(1, max_p + 1):
        n = len(y) - p
        if n < 20:
            break
        X = np.column_stack([np.ones(n)] + [y[p - l : len(y) - l] for l in range(1, p + 1)])
        target = y[p:]
        beta, *_ = np.linalg.lstsq(X, target, rcond=None)
        resid = target - X @ beta
        sse = float(resid @ resid)
        if sse <= 0:
            continue
        bic = n * np.log(sse / n) + p * np.log(n)
        if bic < best_bic:
            best_bic = bic
            best = (p, beta)
    return best


def forecast_ar(y: np.ndarray, p: int, beta: np.ndarray, steps: int) -> np.ndarray:
    hist = list(np.asarray(y, dtype=float)[-p:])
    out = []
    for _ in range(steps):
        x = np.array([1.0] + hist[::-1][:p])
        val = float(x @ beta)
        out.append(val)
        hist.append(val)
        hist = hist[-p:]
    return np.array(out)


class MinnesotaBVAR:
    """Bayesian VAR with a diagonal Minnesota prior (posterior mean)."""

    def __init__(self, p: int = 2, lam: float = 0.2, delta: float = 0.5):
        self.p = p
        self.lam = lam
        self.delta = delta

    def _design(self, Y: np.ndarray):
        T, n = Y.shape
        p = self.p
        X = np.ones((T - p, 1 + n * p))
        for l in range(1, p + 1):
            X[:, 1 + (l - 1) * n : 1 + l * n] = Y[p - l : T - l]
        return X, Y[p:]

    def _fit_once(self, Y: np.ndarray, lam: float):
        T, n = Y.shape
        X, Yy = self._design(Y)
        k = X.shape[1]
        s = np.empty(n)
        for i in range(n):
            yi = Y[:, i]
            a = np.column_stack([np.ones(len(yi) - 1), yi[:-1]])
            b, *_ = np.linalg.lstsq(a, yi[1:], rcond=None)
            s[i] = max(float(np.std(yi[1:] - a @ b)), 1e-4)
        sd = np.maximum(np.std(Y, axis=0), 1e-4)

        B = np.zeros((n, k))
        for i in range(n):
            b_prior = np.zeros(k)
            v_prior = np.zeros(k)
            for j in range(n):
                for l in range(1, self.p + 1):
                    idx = 1 + (l - 1) * n + j
                    if i == j and l == 1:
                        b_prior[idx] = self.delta
                    v_prior[idx] = (lam * s[i] / (l * sd[j])) ** 2
            v_prior[0] = 1e6
            Vi = np.diag(1.0 / v_prior)
            XtX = X.T @ X
            Vpost = np.linalg.inv(XtX + Vi)
            B[i] = Vpost @ (X.T @ Yy[:, i] + Vi @ b_prior)

        resid = Yy - X @ B.T
        Sigma = (resid.T @ resid) / max(len(Yy) - k, 1)
        return B, Sigma

    def _stable(self, B: np.ndarray) -> bool:
        n = B.shape[0]
        p = self.p
        A = np.zeros((n * p, n * p))
        A[:n, :] = B[:, 1:]
        if p > 1:
            A[n:, :-n] = np.eye(n * (p - 1))
        eig = np.max(np.abs(np.linalg.eigvals(A)))
        return np.isfinite(eig) and eig < 0.999

    def fit(self, Y: np.ndarray) -> "MinnesotaBVAR":
        Y = np.asarray(Y, dtype=float)
        self.Y = Y
        lam = self.lam
        for _ in range(4):
            B, Sigma = self._fit_once(Y, lam)
            if self._stable(B):
                break
            lam *= 0.5
        self.B = B
        self.Sigma = Sigma
        self.lam_used = lam
        return self

    def forecast(self, steps: int) -> np.ndarray:
        hist = self.Y[-self.p :].copy()
        out = []
        for _ in range(steps):
            x = np.concatenate([[1.0], hist[::-1].ravel()])
            y = self.B @ x
            out.append(y)
            hist = np.vstack([hist[1:], y])
        return np.vstack(out)


def focus_annual(panel, series_id: str) -> dict[int, float]:
    g = panel.obs[panel.obs["series_id"] == series_id]
    if g.empty:
        return {}
    latest = g["ref_date"].max()
    g = g[g["ref_date"] == latest]
    out: dict[int, float] = {}
    for _, row in g.sort_values("ref_date").iterrows():
        extra = str(row["extra"]).strip()
        if not extra or extra.lower() == "nan":
            continue
        try:
            out[int(float(extra))] = float(row["value"])
        except ValueError:
            continue
    return out
