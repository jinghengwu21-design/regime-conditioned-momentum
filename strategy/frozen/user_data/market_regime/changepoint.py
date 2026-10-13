from __future__ import annotations

from dataclasses import dataclass
import math

import numpy as np
import pandas as pd

from .core import RegimeRecognitionError

try:
    from scipy.special import gammaln
except ModuleNotFoundError:  # pragma: no cover - fallback for minimal installs
    gammaln = np.vectorize(math.lgamma)


@dataclass(frozen=True)
class BOCPDGaussianConfig:
    """
    Online Gaussian BOCPD-style filter for transition-risk context.

    The filter is deliberately small-surface: one scalar observation goes in,
    and the output is a posterior over recent run lengths. With a constant
    hazard, the exact `run_length = 0` probability is mostly the prior hazard,
    so the useful risk signal is the posterior mass assigned to short run
    lengths after the current completed bar. The default risk bucket uses
    expected-run collapse thresholds, which are more conservative than raw
    short-run probability for autocorrelated market streams.
    """

    hazard: float = 1.0 / 288.0
    max_run_length: int = 576
    short_run_bars: int = 72
    prior_mean: float = 0.0
    prior_std: float = 1.0
    prior_kappa: float = 1.0
    prior_alpha: float = 3.0
    risk_bucket_mode: str = "expected_run"
    high_expected_run_bars: float = 6.0
    elevated_expected_run_bars: float = 12.0
    watch_expected_run_bars: float = 24.0
    high_recent_change_prob: float = 0.80
    elevated_recent_change_prob: float = 0.60
    watch_recent_change_prob: float = 0.40

    def validate(self) -> None:
        if not 0.0 < float(self.hazard) < 1.0:
            raise RegimeRecognitionError("BOCPD hazard must be in (0, 1)")
        if int(self.max_run_length) < 2:
            raise RegimeRecognitionError("BOCPD max_run_length must be >= 2")
        if int(self.short_run_bars) < 1:
            raise RegimeRecognitionError("BOCPD short_run_bars must be >= 1")
        if int(self.short_run_bars) > int(self.max_run_length):
            raise RegimeRecognitionError("BOCPD short_run_bars must be <= max_run_length")
        if float(self.prior_std) <= 0.0:
            raise RegimeRecognitionError("BOCPD prior_std must be positive")
        if float(self.prior_kappa) <= 0.0:
            raise RegimeRecognitionError("BOCPD prior_kappa must be positive")
        if float(self.prior_alpha) <= 1.0:
            raise RegimeRecognitionError("BOCPD prior_alpha must be > 1")
        if self.risk_bucket_mode not in {"expected_run", "recent_change_prob"}:
            raise RegimeRecognitionError("BOCPD risk_bucket_mode must be expected_run or recent_change_prob")
        run_thresholds = [
            self.high_expected_run_bars,
            self.elevated_expected_run_bars,
            self.watch_expected_run_bars,
        ]
        if any(float(value) <= 0.0 for value in run_thresholds):
            raise RegimeRecognitionError("BOCPD expected-run thresholds must be positive")
        if run_thresholds != sorted(run_thresholds):
            raise RegimeRecognitionError("BOCPD expected-run thresholds must be ordered high <= elevated <= watch")
        thresholds = [
            self.watch_recent_change_prob,
            self.elevated_recent_change_prob,
            self.high_recent_change_prob,
        ]
        if not all(0.0 <= float(value) <= 1.0 for value in thresholds):
            raise RegimeRecognitionError("BOCPD recent-change thresholds must be in [0, 1]")
        if thresholds != sorted(thresholds):
            raise RegimeRecognitionError("BOCPD thresholds must be ordered watch <= elevated <= high")


def _prior_beta(config: BOCPDGaussianConfig) -> float:
    return (float(config.prior_alpha) - 1.0) * float(config.prior_std) ** 2


def _student_t_logpdf(x: float, *, loc: np.ndarray, scale: np.ndarray, df: np.ndarray) -> np.ndarray:
    scale = np.maximum(scale.astype(float), 1e-8)
    df = np.maximum(df.astype(float), 1e-8)
    z = (float(x) - loc.astype(float)) / scale
    log_coef = (
        gammaln((df + 1.0) / 2.0)
        - gammaln(df / 2.0)
        - 0.5 * (np.log(df * math.pi) + 2.0 * np.log(scale))
    )
    return log_coef - ((df + 1.0) / 2.0) * np.log1p((z * z) / df)


def _predictive_logpdf(
    x: float,
    *,
    n: np.ndarray,
    sample_mean: np.ndarray,
    sample_m2: np.ndarray,
    config: BOCPDGaussianConfig,
) -> np.ndarray:
    n = n.astype(float)
    kappa0 = float(config.prior_kappa)
    alpha0 = float(config.prior_alpha)
    beta0 = _prior_beta(config)
    mu0 = float(config.prior_mean)

    kappa = kappa0 + n
    alpha = alpha0 + 0.5 * n
    mean_delta = sample_mean.astype(float) - mu0
    beta = beta0 + 0.5 * sample_m2.astype(float) + (kappa0 * n * mean_delta * mean_delta) / (2.0 * kappa)
    loc = (kappa0 * mu0 + n * sample_mean.astype(float)) / kappa
    scale = np.sqrt(np.maximum(beta * (kappa + 1.0) / (alpha * kappa), 1e-12))
    return _student_t_logpdf(float(x), loc=loc, scale=scale, df=2.0 * alpha)


def _logsumexp(values: np.ndarray) -> float:
    finite = values[np.isfinite(values)]
    if finite.size == 0:
        return float("-inf")
    max_value = float(np.max(finite))
    return max_value + float(np.log(np.exp(finite - max_value).sum()))


def gaussian_bocpd_transition_risk(
    observation: pd.Series | np.ndarray | list[float],
    *,
    config: BOCPDGaussianConfig | None = None,
    output_prefix: str = "bocpd",
) -> pd.DataFrame:
    """
    Run a causal BOCPD-style filter over a scalar observation stream.

    Missing or non-finite observations are skipped without updating the
    posterior. The returned rows remain aligned to the input order.
    """

    cfg = config or BOCPDGaussianConfig()
    cfg.validate()

    series = pd.Series(observation, dtype="float64")
    values = series.to_numpy(dtype=float)

    posterior = np.array([1.0], dtype=float)
    n = np.array([0.0], dtype=float)
    mean = np.array([0.0], dtype=float)
    m2 = np.array([0.0], dtype=float)

    short_limit = int(cfg.short_run_bars)
    max_len = int(cfg.max_run_length) + 1
    hazard = float(cfg.hazard)
    log_hazard = math.log(hazard)
    log_growth_hazard = math.log1p(-hazard)
    prior_short_run_prob = max(1.0 - (1.0 - hazard) ** (short_limit + 1), 1e-12)

    rows: list[dict[str, object]] = []
    for value in values:
        if not np.isfinite(value):
            rows.append(
                {
                    f"{output_prefix}_observation": np.nan,
                    f"{output_prefix}_valid_observation": False,
                    f"{output_prefix}_instant_cp_prob": np.nan,
                    f"{output_prefix}_recent_change_prob": np.nan,
                    f"{output_prefix}_recent_change_odds": np.nan,
                    f"{output_prefix}_expected_run_bars": np.nan,
                    f"{output_prefix}_map_run_bars": np.nan,
                    f"{output_prefix}_log_evidence": np.nan,
                    f"{output_prefix}_risk_bucket": "missing_observation",
                }
            )
            continue

        log_pred = _predictive_logpdf(value, n=n, sample_mean=mean, sample_m2=m2, config=cfg)
        log_previous = np.log(np.clip(posterior, 1e-300, 1.0))
        log_growth = log_previous + log_growth_hazard + log_pred
        log_cp_components = log_previous + log_hazard + log_pred
        log_cp = _logsumexp(log_cp_components)
        log_evidence = _logsumexp(np.concatenate(([log_cp], log_growth)))

        growth = np.exp(log_growth - log_evidence)
        cp_prob = math.exp(log_cp - log_evidence)
        new_posterior = np.concatenate(([cp_prob], growth))

        delta = float(value) - mean
        growth_n = n + 1.0
        growth_mean = mean + delta / growth_n
        growth_m2 = m2 + delta * (float(value) - growth_mean)

        new_n = np.concatenate(([1.0], growth_n))
        new_mean = np.concatenate(([float(value)], growth_mean))
        new_m2 = np.concatenate(([0.0], growth_m2))

        if new_posterior.size > max_len:
            new_posterior = new_posterior[:max_len]
            new_n = new_n[:max_len]
            new_mean = new_mean[:max_len]
            new_m2 = new_m2[:max_len]
            total = float(new_posterior.sum())
            if total > 0.0:
                new_posterior = new_posterior / total

        posterior = new_posterior
        n = new_n
        mean = new_mean
        m2 = new_m2

        run_lengths = np.arange(posterior.size, dtype=float)
        recent_change_prob = float(posterior[: min(short_limit + 1, posterior.size)].sum())
        recent_change_odds = recent_change_prob / prior_short_run_prob
        expected_run = float(np.dot(run_lengths, posterior))
        map_run = int(np.argmax(posterior))
        if cfg.risk_bucket_mode == "recent_change_prob":
            bucket = np.select(
                [
                    recent_change_prob >= float(cfg.high_recent_change_prob),
                    recent_change_prob >= float(cfg.elevated_recent_change_prob),
                    recent_change_prob >= float(cfg.watch_recent_change_prob),
                ],
                [
                    "high_bocpd_transition_risk",
                    "elevated_bocpd_transition_risk",
                    "watch_bocpd_transition_risk",
                ],
                default="stable_bocpd_context",
            ).item()
        else:
            bucket = np.select(
                [
                    expected_run <= float(cfg.high_expected_run_bars),
                    expected_run <= float(cfg.elevated_expected_run_bars),
                    expected_run <= float(cfg.watch_expected_run_bars),
                ],
                [
                    "high_bocpd_transition_risk",
                    "elevated_bocpd_transition_risk",
                    "watch_bocpd_transition_risk",
                ],
                default="stable_bocpd_context",
            ).item()

        rows.append(
            {
                f"{output_prefix}_observation": float(value),
                f"{output_prefix}_valid_observation": True,
                f"{output_prefix}_instant_cp_prob": float(cp_prob),
                f"{output_prefix}_recent_change_prob": recent_change_prob,
                f"{output_prefix}_recent_change_odds": float(recent_change_odds),
                f"{output_prefix}_expected_run_bars": expected_run,
                f"{output_prefix}_map_run_bars": map_run,
                f"{output_prefix}_log_evidence": float(log_evidence),
                f"{output_prefix}_risk_bucket": bucket,
            }
        )

    return pd.DataFrame(rows, index=series.index)
