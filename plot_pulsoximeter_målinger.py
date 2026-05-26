from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data" / "live"
PLOT_DIR = ROOT / "data" / "plots"


@dataclass(frozen=True)
class PlotConfig:
    stem: str
    title: str
    stats_start_s: float
    phases: tuple[tuple[float, float, str, str], ...] = ()
    event_s: float | None = None
    event_label: str | None = None


PLOTS = (
    PlotConfig(
        stem="live_normal_maaling",
        title="Normal vejrtrækning",
        stats_start_s=15,
        phases=((0, 15, "Opstart", "#e6e6e6"),),
    ),
    PlotConfig(
        stem="live_holder_vejret",
        title="Holder vejret - normal vejrtrækning fra 30 s",
        stats_start_s=30,
        phases=((0, 30, "Holder vejret", "#eadede"),),
        event_s=30,
        event_label="Normal vejrtrækning",
    ),
    PlotConfig(
        stem="live_hyperventilation",
        title="Hyperventilation - normal vejrtrækning fra 30 s",
        stats_start_s=30,
        phases=((0, 30, "Hyperventilation", "#dfe8f3"),),
        event_s=30,
        event_label="Normal vejrtrækning",
    ),
)


def robust_ylim(*series: pd.Series | np.ndarray, pad_fraction: float = 0.12) -> tuple[float, float]:
    values = np.concatenate([np.asarray(s, dtype=float) for s in series])
    values = values[np.isfinite(values)]
    if len(values) == 0:
        return 0.0, 1.0

    low, high = np.nanpercentile(values, [1, 99])
    if not np.isfinite(low) or not np.isfinite(high) or low == high:
        low, high = np.nanmin(values), np.nanmax(values)

    pad = max((high - low) * pad_fraction, 1e-6)
    return float(low - pad), float(high + pad)


def metric_ylim(series: pd.Series, fallback: tuple[float, float], pad: float) -> tuple[float, float]:
    values = series.dropna().to_numpy(dtype=float)
    if len(values) == 0:
        return fallback

    low, high = np.nanpercentile(values, [2, 98])
    if not np.isfinite(low) or not np.isfinite(high) or low == high:
        low, high = np.nanmin(values), np.nanmax(values)

    return float(low - pad), float(high + pad)


def add_phases(ax, cfg: PlotConfig, *, show_phase_labels: bool = True) -> None:
    for start, end, label, color in cfg.phases:
        ax.axvspan(start, end, color=color, alpha=0.85, lw=0, label=label if show_phase_labels else None)

    if cfg.event_s is not None:
        ax.axvline(cfg.event_s, color="#555555", lw=1.0, alpha=0.65, ls="--")
        if cfg.event_label:
            ymin, ymax = ax.get_ylim()
            ax.text(
                cfg.event_s + 0.5,
                ymax - (ymax - ymin) * 0.08,
                cfg.event_label,
                color="#333333",
                fontsize=9,
                va="top",
            )


def stat_text(df: pd.DataFrame, start_s: float) -> str:
    window = df[df["t_plot"] >= start_s]
    bpm = window["bpm"].dropna()
    spo2 = window["spo2"].dropna()

    if len(bpm) == 0 or len(spo2) == 0:
        return "Ikke nok valide HR/SpO2-data"

    return (
        f"Middel efter {start_s:.0f} s: "
        f"HR = {bpm.mean():.1f} +/- {bpm.std():.1f} BPM, "
        f"SpO2 = {spo2.mean():.1f} +/- {spo2.std():.1f} %"
    )


def plot_measurement(cfg: PlotConfig) -> None:
    csv_path = DATA_DIR / f"{cfg.stem}.csv"
    df = pd.read_csv(csv_path)
    df["t_plot"] = df["t_s"] - df["t_s"].min()

    fig, axes = plt.subplots(
        2,
        1,
        figsize=(14.5, 7.9),
        dpi=150,
        sharex=True,
        constrained_layout=True,
    )
    ax_signal, ax_hr = axes
    ax_spo2 = ax_hr.twinx()

    ax_signal.plot(df["t_plot"], df["v_660_korr"], color="#e41a1c", lw=1.6, label="660 nm")
    ax_signal.plot(df["t_plot"], df["v_940_korr"], color="#179c2e", lw=1.6, label="940 nm")
    ax_signal.set_title(cfg.title, fontsize=14, pad=8)
    ax_signal.set_ylabel("Mørkekorrigeret spænding [V]")
    ax_signal.set_ylim(robust_ylim(df["v_660_korr"], df["v_940_korr"]))
    ax_signal.grid(True, color="#b5b5b5", alpha=0.28, linewidth=0.8)
    add_phases(ax_signal, cfg)
    ax_signal.legend(frameon=False, loc="upper right")

    ax_hr.plot(df["t_plot"], df["bpm"], color="#1f78c8", lw=1.8, label="HR")
    ax_spo2.plot(df["t_plot"], df["spo2"], color="#9467d0", lw=1.4, label="SpO2")

    ax_hr.set_ylabel("HR [BPM]")
    ax_spo2.set_ylabel("SpO2 [%]")
    ax_hr.set_xlabel("Tid [s]")
    ax_hr.set_ylim(metric_ylim(df["bpm"], fallback=(40, 90), pad=2.0))
    ax_spo2.set_ylim(metric_ylim(df["spo2"], fallback=(80, 102), pad=1.0))
    ax_hr.grid(True, color="#b5b5b5", alpha=0.28, linewidth=0.8)
    add_phases(ax_hr, cfg, show_phase_labels=False)

    max_t = max(60.0, float(np.nanmax(df["t_plot"])))
    ax_hr.set_xlim(0, max_t)
    ax_hr.set_xticks(np.arange(0, max_t + 0.1, 10))

    handles_hr, labels_hr = ax_hr.get_legend_handles_labels()
    handles_spo2, labels_spo2 = ax_spo2.get_legend_handles_labels()
    ax_hr.legend(handles_hr + handles_spo2, labels_hr + labels_spo2, frameon=False, loc="upper right")

    ax_hr.text(
        0.01,
        0.04,
        stat_text(df, cfg.stats_start_s),
        transform=ax_hr.transAxes,
        fontsize=9.5,
        va="bottom",
        ha="left",
        bbox={"facecolor": "white", "edgecolor": "#bdbdbd", "alpha": 0.9, "pad": 4},
    )

    for ax in (ax_signal, ax_hr):
        ax.spines["top"].set_color("#333333")
        ax.spines["right"].set_color("#333333")
        ax.spines["bottom"].set_color("#333333")
        ax.spines["left"].set_color("#333333")

    PLOT_DIR.mkdir(parents=True, exist_ok=True)
    for suffix in ("png", "pdf"):
        fig.savefig(PLOT_DIR / f"{cfg.stem}.{suffix}", bbox_inches="tight")

    plt.close(fig)


def main() -> None:
    for cfg in PLOTS:
        plot_measurement(cfg)
        print(f"Gemte {cfg.stem}.png og {cfg.stem}.pdf")


if __name__ == "__main__":
    main()
