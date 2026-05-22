from __future__ import annotations

from dataclasses import dataclass
import argparse
import time

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.signal import butter, find_peaks, sosfiltfilt

import dwfpy as dwf
from dwfpy.constants import TriggerSource


DURATION_S = 60
ANALOG_CHANNEL = 0
DIO_660 = 1
DIO_940 = 0

MIN_BPM = 40
MAX_BPM = 140
PLOT_WINDOW_S = 15
HR_WINDOW_S = 30
SPO2_WINDOW_S = 30
MIN_METRIC_WINDOW_S = 12


@dataclass
class MåleConfig:
    cycle_rate_hz: float = 7.41
    analog_range_v: float = 10.0
    spo2_a: float = -24.87
    spo2_b: float = 113.8
    bp_low_hz: float = 0.5
    bp_high_hz: float = 2.0
    peak_prominence: float = 0.3

    sample_rate_hz: float = 20_000
    settle_s: float = 0.005
    trim_fraction: float = 0.10

    def __post_init__(self):
        self.measure_s = 1 / (3 * self.cycle_rate_hz) - self.settle_s
        if self.measure_s <= 0:
            raise ValueError("cycle-rate er for høj i forhold til settle-tiden")


def setup_scope(device, cfg):
    scope = device.analog_input
    scope.reset()
    scope.trigger.source = TriggerSource.NONE

    for channel_index, _ in enumerate(scope.channels):
        scope.setup_channel(
            channel_index,
            range=cfg.analog_range_v,
            offset=0.0,
            coupling="dc",
            filter="average",
            enabled=(channel_index == ANALOG_CHANNEL),
        )


def set_leds(device, led_660=False, led_940=False):
    pattern = device.digital_output
    pattern[DIO_660].setup_constant(
        "high" if led_660 else "low",
        output_mode="push-pull",
        idle_state="low",
    )
    pattern[DIO_940].setup_constant(
        "high" if led_940 else "low",
        output_mode="push-pull",
        idle_state="low",
    )
    pattern.configure(start=True)


def measure_voltage(device, cfg):
    recorder = device.analog_input.record(
        sample_rate=cfg.sample_rate_hz,
        length=cfg.measure_s,
        buffer_size=8192,
        configure=True,
        start=True,
    )
    values = np.asarray(recorder.channels[ANALOG_CHANNEL].data_samples, dtype=float)
    values = values[np.isfinite(values)]

    return float(np.mean(values))


def measure_cycle(device, cfg):
    set_leds(device, led_660=True)
    time.sleep(cfg.settle_s)
    v_660 = measure_voltage(device, cfg)

    set_leds(device, led_940=True)
    time.sleep(cfg.settle_s)
    v_940 = measure_voltage(device, cfg)

    set_leds(device)
    time.sleep(cfg.settle_s)
    v_dark = measure_voltage(device, cfg)

    return {
        "v_660": v_660,
        "v_940": v_940,
        "v_dark": v_dark,
        "v_660_korr": v_660 - v_dark,
        "v_940_korr": v_940 - v_dark,
    }


def bandpass(y, t, low_hz, high_hz):
    y = np.asarray(y, dtype=float)
    t = np.asarray(t, dtype=float)

    dt = np.median(np.diff(t))

    fs = 1 / dt
    nyq = 0.5 * fs
    high = min(high_hz, 0.95 * nyq)

    sos = butter(2, [low_hz / nyq, high / nyq], btype="band", output="sos")
    return sosfiltfilt(sos, y, padlen=min(3 * (sos.shape[0] + 1), len(y) - 1))


def normalized_ppg(y):
    y = np.asarray(y, dtype=float)
    if len(y) == 0 or np.any(~np.isfinite(y)) or np.any(y <= 1e-3):
        return None

    dc = np.median(y)
    if not np.isfinite(dc) or dc <= 1e-3:
        return None
    return np.log(y / dc)


def calculate_spo2(data, cfg):
    recent = data[data["t_s"] >= data["t_s"].max() - SPO2_WINDOW_S]
    t = recent["t_s"].to_numpy()

    red = normalized_ppg(recent["v_660_korr"].to_numpy())
    ir = normalized_ppg(recent["v_940_korr"].to_numpy())

    red_bp = bandpass(red, t, cfg.bp_low_hz, cfg.bp_high_hz)
    ir_bp = bandpass(ir, t, cfg.bp_low_hz, cfg.bp_high_hz)

    ac_red = np.percentile(red_bp, 95) - np.percentile(red_bp, 5)
    ac_ir = np.percentile(ir_bp, 95) - np.percentile(ir_bp, 5)

    r_value = ac_red / ac_ir
    spo2 = cfg.spo2_a * r_value + cfg.spo2_b

    return float(r_value), float(spo2)


def calculate_hr(data, cfg):
    recent = data[data["t_s"] >= data["t_s"].max() - HR_WINDOW_S]
    t = recent["t_s"].to_numpy()

    y = normalized_ppg(recent["v_940_korr"].to_numpy())
    y = bandpass(y, t, cfg.bp_low_hz, cfg.bp_high_hz)

    y = y - np.median(y)

    dt = np.median(np.diff(t))

    fs = 1 / dt
    min_distance = max(1, int(round(fs * 60 / MAX_BPM)))
    prominence = cfg.peak_prominence * np.ptp(y)

    best_bpm = np.nan
    best_points = np.array([], dtype=int)
    best_regularity = np.inf
    for polarity in (1, -1):
        points, _ = find_peaks(polarity * y, distance=min_distance, prominence=prominence)
        intervals = np.diff(t[points])
        intervals = intervals[(intervals >= 60 / MAX_BPM) & (intervals <= 60 / MIN_BPM)]
        if len(intervals) < 2:
            continue

        bpm = 60 / np.median(intervals)
        regularity = np.std(intervals) / np.median(intervals)
        if regularity < best_regularity:
            best_bpm = bpm
            best_points = recent.index.to_numpy()[points]
            best_regularity = regularity

    return float(best_bpm), best_points


def fmt(value, suffix="", decimals=1):
    return "--" if not np.isfinite(value) else f"{value:.{decimals}f}{suffix}"


def make_plot(cfg):
    plt.ion()
    fig, axes = plt.subplots(2, 1, figsize=(13, 7), dpi=300, constrained_layout=True)
    fig.canvas.manager.set_window_title("Live pulsoximeter")

    line_660, = axes[0].plot([], [], color="tab:red", label="660 nm")
    line_940, = axes[0].plot([], [], color="tab:green", label="940 nm")
    pulse_points = axes[0].scatter([], [], color="black", s=24, label="Puls")
    line_hr, = axes[1].plot([], [], color="tab:blue", label="HR [BPM]")
    ax_spo2 = axes[1].twinx()
    line_spo2, = ax_spo2.plot([], [], color="tab:purple", label="SpO2 [%]")

    axes[0].set_xlabel("Tid [s]")
    axes[0].set_ylabel("Mørkekorrigeret spænding [V]")
    axes[0].grid(True, alpha=0.35)
    axes[0].legend(frameon=False, loc="upper right")

    axes[1].set_xlabel("Tid [s]")
    axes[1].set_ylabel("HR [BPM]")
    axes[1].set_xlim(0, DURATION_S)
    axes[1].set_ylim(MIN_BPM - 10, MAX_BPM + 10)
    axes[1].grid(True, alpha=0.35)

    ax_spo2.set_ylabel("SpO2 [%]")
    ax_spo2.set_xlim(0, DURATION_S)
    ax_spo2.set_ylim(80, 100)

    h1, l1 = axes[1].get_legend_handles_labels()
    h2, l2 = ax_spo2.get_legend_handles_labels()
    axes[1].legend(h1 + h2, l1 + l2, frameon=False, loc="upper right")

    return fig, axes, ax_spo2, line_660, line_940, pulse_points, line_hr, line_spo2


def update_plot(plot_state, data, pulse_indices):
    fig, axes, ax_spo2, line_660, line_940, pulse_points, line_hr, line_spo2 = plot_state
    recent = data[data["t_s"] >= data["t_s"].max() - PLOT_WINDOW_S]
    last = data.iloc[-1]

    line_660.set_data(recent["t_s"], recent["v_660_korr"])
    line_940.set_data(recent["t_s"], recent["v_940_korr"])

    visible = [idx for idx in pulse_indices if idx in recent.index]
    if visible:
        pulse_points.set_offsets(np.c_[data.loc[visible, "t_s"], data.loc[visible, "v_940_korr"]])

    line_hr.set_data(data["t_s"], data["bpm"])
    line_spo2.set_data(data["t_s"], data["spo2"])

    axes[0].set_xlim(max(0, data["t_s"].max() - PLOT_WINDOW_S), data["t_s"].max() + 0.5)
    ymin = np.nanmin([recent["v_660_korr"].min(), recent["v_940_korr"].min()])
    ymax = np.nanmax([recent["v_660_korr"].max(), recent["v_940_korr"].max()])
    pad = max((ymax - ymin) * 0.15, 1e-6)
    axes[0].set_ylim(ymin - pad, ymax + pad)
    axes[0].set_title(f"HR {fmt(last['bpm'], ' BPM')} | SpO2 {fmt(last['spo2'], ' %')} | R {fmt(last['R'], decimals=3)}")

    fig.canvas.draw_idle()
    fig.canvas.flush_events()


def save_measurement(rows_df):
    raw_path = f"pulsoximeter_{time.strftime('%Y%m%d_%H%M%S')}.csv"
    rows_df.to_csv(raw_path, index=False)
    print(f"Gemte rådata:  {raw_path}")


def parse_args():
    parser = argparse.ArgumentParser(description="60 sekunders live pulsoximeter-måling")
    parser.add_argument("--cycle-rate", type=float, default=7.41)
    parser.add_argument("--range", dest="analog_range_v", type=float, default=10.0)
    parser.add_argument("--bp-low", type=float, default=0.5)
    parser.add_argument("--bp-high", type=float, default=2.0)
    parser.add_argument("--peak-prominence", type=float, default=0.3)
    parser.add_argument("--spo2-a", type=float, default=-24.87)
    parser.add_argument("--spo2-b", type=float, default=113.8)
    return parser.parse_args()


def main():
    args = parse_args()
    cfg = MåleConfig(
        cycle_rate_hz=args.cycle_rate,
        analog_range_v=args.analog_range_v,
        bp_low_hz=args.bp_low,
        bp_high_hz=args.bp_high,
        peak_prominence=args.peak_prominence,
        spo2_a=args.spo2_a,
        spo2_b=args.spo2_b,
    )

    rows = []
    plot_state = make_plot(cfg)
    start = time.monotonic()

    print("Starter 60 sek måling.")

    with dwf.Device() as device:
        setup_scope(device, cfg)
        set_leds(device)

        try:
            while time.monotonic() - start < DURATION_S:
                row = measure_cycle(device, cfg)
                row["t_s"] = time.monotonic() - start
                rows.append(row)

                data = pd.DataFrame(rows)
                bpm, pulse_indices = calculate_hr(data, cfg)
                r_value, spo2 = calculate_spo2(data, cfg)
                rows[-1]["bpm"] = bpm
                rows[-1]["R"] = r_value
                rows[-1]["spo2"] = spo2
                update_plot(plot_state, pd.DataFrame(rows), pulse_indices)
        except KeyboardInterrupt:
            pass
        finally:
            set_leds(device)

    rows_df = pd.DataFrame(rows)
    save_measurement(rows_df)

    plt.ioff()
    plt.show()


if __name__ == "__main__":
    main()
