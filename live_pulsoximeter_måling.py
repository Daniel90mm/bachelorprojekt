from __future__ import annotations

from dataclasses import dataclass
import argparse
import time

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.signal import find_peaks

import dwfpy as dwf
from dwfpy.constants import TriggerSource


@dataclass
class MåleConfig:
    cycle_rate_hz: float = 10.0
    max_cycle_rate_hz: float = 20.0
    sample_rate_hz: float = 20_000
    settle_s: float = 0.005
    min_fase_varighed_s: float = 0.005
    fase_varighed_s: float = 0.0
    total_varighed_s: float = 90
    analog_channel: int = 0
    analog_range_v: float = 2.0
    dio_660: int = 0
    dio_940: int = 1
    spo2_a: float = -24.87
    spo2_b: float = 113.8
    puls_vindue_s: float = 60
    min_puls_tid_s: float = 15
    spo2_vindue_s: float = 30
    spo2_min_dc_v: float = 1e-3
    spo2_min_ac_v: float = 1e-5
    min_bpm: float = 40
    max_bpm: float = 140
    peak_prominence_fraction: float = 0.3
    smoothing_window_s: float = 0.35
    plot_window_s: float = 15

    def __post_init__(self):
        self.configure_cycle_rate(self.cycle_rate_hz)

    def configure_cycle_rate(self, cycle_rate_hz):
        if cycle_rate_hz <= 0:
            raise ValueError("cycle_rate_hz skal være positiv")
        if cycle_rate_hz > self.max_cycle_rate_hz:
            raise ValueError(
                f"Valgt cyklusfrekvens {cycle_rate_hz:g} Hz er over sikkerhedsloftet "
                f"på {self.max_cycle_rate_hz:g} Hz. Hæv kun max_cycle_rate_hz, hvis "
                "LED-strøm, duty cycle og analog settling er kontrolleret."
            )

        phase_total_s = 1 / (3 * cycle_rate_hz)
        fase_varighed_s = phase_total_s - self.settle_s
        if fase_varighed_s < self.min_fase_varighed_s:
            raise ValueError(
                f"Cyklusfrekvens {cycle_rate_hz:g} Hz giver kun {fase_varighed_s * 1000:.2f} ms "
                "til måling efter settling. Sænk --cycle-rate eller --settle."
            )

        self.cycle_rate_hz = cycle_rate_hz
        self.fase_varighed_s = fase_varighed_s

    @property
    def phase_total_s(self):
        return self.fase_varighed_s + self.settle_s

    @property
    def active_led_duty(self):
        return self.fase_varighed_s * self.cycle_rate_hz


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
            enabled=(channel_index == cfg.analog_channel),
        )


def set_leds(device, cfg, led_660=False, led_940=False):
    pattern = device.digital_output
    pattern[cfg.dio_660].setup_constant(
        "high" if led_660 else "low",
        output_mode="push-pull",
        idle_state="low",
    )
    pattern[cfg.dio_940].setup_constant(
        "high" if led_940 else "low",
        output_mode="push-pull",
        idle_state="low",
    )
    pattern.configure(start=True)


def measure_voltage(device, cfg):
    scope = device.analog_input
    recorder = scope.record(
        sample_rate=cfg.sample_rate_hz,
        length=cfg.fase_varighed_s,
        buffer_size=8192,
        configure=True,
        start=True,
    )
    samples = recorder.channels[cfg.analog_channel].data_samples
    return float(np.mean(samples))


def measure_cycle(device, cfg):
    set_leds(device, cfg, led_660=True, led_940=False)
    time.sleep(cfg.settle_s)
    v_660 = measure_voltage(device, cfg)

    set_leds(device, cfg, led_660=False, led_940=True)
    time.sleep(cfg.settle_s)
    v_940 = measure_voltage(device, cfg)

    set_leds(device, cfg, led_660=False, led_940=False)
    time.sleep(cfg.settle_s)
    v_dark = measure_voltage(device, cfg)

    return {
        "v_660": v_660,
        "v_940": v_940,
        "v_dark": v_dark,
        "v_660_korr": v_660 - v_dark,
        "v_940_korr": v_940 - v_dark,
    }


def calculate_spo2(data, cfg):
    recent = data[data["t_s"] >= data["t_s"].max() - cfg.spo2_vindue_s]
    if len(recent) < 8:
        return np.nan, np.nan, "venter på mere data"

    ac_660 = np.percentile(recent["v_660_korr"], 95) - np.percentile(recent["v_660_korr"], 5)
    ac_940 = np.percentile(recent["v_940_korr"], 95) - np.percentile(recent["v_940_korr"], 5)
    dc_660 = abs(recent["v_660_korr"].mean())
    dc_940 = abs(recent["v_940_korr"].mean())

    if dc_660 < cfg.spo2_min_dc_v or dc_940 < cfg.spo2_min_dc_v:
        return np.nan, np.nan, "SpO2 ikke gyldig: DC-led for lavt"
    if ac_660 < cfg.spo2_min_ac_v or ac_940 < cfg.spo2_min_ac_v:
        return np.nan, np.nan, "SpO2 ikke gyldig: AC-led for lavt"

    r_value = (ac_660 / dc_660) / (ac_940 / dc_940)
    spo2 = cfg.spo2_a * r_value + cfg.spo2_b

    if not np.isfinite(r_value) or not np.isfinite(spo2) or spo2 < 50 or spo2 > 100:
        return r_value, np.nan, "SpO2 uden for gyldigt område"

    return r_value, spo2, "ok"


def smooth(y, width):
    if len(y) < width:
        return y
    kernel = np.ones(width) / width
    return np.convolve(y, kernel, mode="same")


def find_pulse_points(t, y, cfg, polarity=1):
    if len(y) >= 4:
        trend = np.polyval(np.polyfit(t - t[0], y, 1), t - t[0])
        y = y - trend
    y = polarity * (y - np.median(y))

    if len(y) < 3 or np.std(y) < 1e-12:
        return np.array([], dtype=int)

    fs = 1 / np.median(np.diff(t))
    smooth_width = max(1, int(round(cfg.smoothing_window_s * fs)))
    y = smooth(y, smooth_width)

    min_distance_s = 60 / cfg.max_bpm
    min_distance_samples = max(1, int(round(min_distance_s * fs)))
    prominence = cfg.peak_prominence_fraction * np.ptp(y)
    if prominence <= 0:
        return np.array([], dtype=int)

    points, _ = find_peaks(y, distance=min_distance_samples, prominence=prominence)
    return points


def bpm_from_points(t, points, cfg):
    if len(points) < 3:
        return np.nan, np.inf

    intervals = np.diff(t[points])
    valid = (intervals >= 60 / cfg.max_bpm) & (intervals <= 60 / cfg.min_bpm)
    intervals = intervals[valid]
    if len(intervals) < 2:
        return np.nan, np.inf

    bpm = 60 / np.median(intervals)
    regularity = np.std(intervals) / np.median(intervals)
    if bpm < cfg.min_bpm or bpm > cfg.max_bpm:
        return np.nan, np.inf
    return bpm, regularity


def calculate_bpm(data, cfg):
    recent = data[data["t_s"] >= data["t_s"].max() - cfg.puls_vindue_s]
    if len(recent) < 6 or recent["t_s"].max() - recent["t_s"].min() < cfg.min_puls_tid_s:
        return np.nan, np.array([], dtype=int), "", "venter på flere pulsslag"

    t = recent["t_s"].to_numpy()
    y = recent["v_940_korr"].to_numpy()

    peak_local = find_pulse_points(t, y, cfg, polarity=1)
    trough_local = find_pulse_points(t, y, cfg, polarity=-1)
    peak_bpm, peak_regularity = bpm_from_points(t, peak_local, cfg)
    trough_bpm, trough_regularity = bpm_from_points(t, trough_local, cfg)

    if np.isfinite(trough_bpm) and (not np.isfinite(peak_bpm) or trough_regularity < peak_regularity):
        chosen = trough_local
        bpm = trough_bpm
        kind = "dale"
        regularity = trough_regularity
    else:
        chosen = peak_local
        bpm = peak_bpm
        kind = "toppe"
        regularity = peak_regularity

    if not np.isfinite(bpm):
        return np.nan, np.array([], dtype=int), "", "ingen stabile toppe/dale"
    if regularity > 0.35:
        return np.nan, recent.index.to_numpy()[chosen], kind, "pulsen er for ujævn"

    return bpm, recent.index.to_numpy()[chosen], kind, "ok"


def fmt(value, suffix=""):
    return "--" if not np.isfinite(value) else f"{value:.1f}{suffix}"


def make_plot(cfg):
    plt.ion()
    fig, axes = plt.subplots(2, 1, figsize=(13, 7), constrained_layout=True)
    fig.canvas.manager.set_window_title("Live pulsoximeter")

    line_660, = axes[0].plot([], [], color="tab:red", label="660 nm")
    line_940, = axes[0].plot([], [], color="tab:green", label="940 nm")
    peak_scatter = axes[0].scatter([], [], color="black", s=28, label="Puls")

    line_bpm, = axes[1].plot([], [], color="tab:blue", label="HR [BPM]")
    ax_spo2 = axes[1].twinx()
    line_spo2, = ax_spo2.plot([], [], color="tab:purple", label="SpO2 [%]")

    axes[0].set_xlabel("Tid [s]")
    axes[0].set_ylabel("Mørkekorrigeret spænding [V]")
    axes[0].grid(True, alpha=0.35)
    axes[0].legend(frameon=False, loc="upper right")

    axes[1].set_xlabel("Tid [s]")
    axes[1].set_ylabel("HR [BPM]")
    axes[1].set_ylim(cfg.min_bpm - 10, cfg.max_bpm + 10)
    axes[1].grid(True, alpha=0.35)

    ax_spo2.set_ylabel("SpO2 [%]")
    ax_spo2.set_ylim(80, 100)

    handles1, labels1 = axes[1].get_legend_handles_labels()
    handles2, labels2 = ax_spo2.get_legend_handles_labels()
    axes[1].legend(handles1 + handles2, labels1 + labels2, frameon=False, loc="upper right")

    status_text = axes[0].text(
        0.01,
        0.98,
        "",
        transform=axes[0].transAxes,
        va="top",
        ha="left",
        fontsize=10,
        bbox={"facecolor": "white", "alpha": 0.8, "edgecolor": "0.8"},
    )

    return fig, axes, ax_spo2, line_660, line_940, peak_scatter, line_bpm, line_spo2, status_text


def update_plot(plot_state, data, metrics, pulse_indices, pulse_kind, cfg):
    fig, axes, ax_spo2, line_660, line_940, peak_scatter, line_bpm, line_spo2, status_text = plot_state
    recent = data[data["t_s"] >= data["t_s"].max() - cfg.plot_window_s]
    metrics_df = pd.DataFrame(metrics)
    last = metrics[-1]

    line_660.set_data(recent["t_s"], recent["v_660_korr"])
    line_940.set_data(recent["t_s"], recent["v_940_korr"])

    visible = [idx for idx in pulse_indices if idx in recent.index]
    if visible:
        peak_scatter.set_offsets(np.c_[data.loc[visible, "t_s"], data.loc[visible, "v_940_korr"]])
        peak_scatter.set_label(f"Puls-{pulse_kind}")
    else:
        peak_scatter.set_offsets(np.empty((0, 2)))

    line_bpm.set_data(metrics_df["t_s"], metrics_df["bpm"])
    line_spo2.set_data(metrics_df["t_s"], metrics_df["spo2"])

    axes[0].set_xlim(max(0, data["t_s"].max() - cfg.plot_window_s), data["t_s"].max() + 0.5)
    ymin = np.nanmin([recent["v_660_korr"].min(), recent["v_940_korr"].min()])
    ymax = np.nanmax([recent["v_660_korr"].max(), recent["v_940_korr"].max()])
    pad = max((ymax - ymin) * 0.15, 1e-6)
    axes[0].set_ylim(ymin - pad, ymax + pad)

    axes[1].set_xlim(0, max(cfg.total_varighed_s, data["t_s"].max()))
    ax_spo2.set_xlim(axes[1].get_xlim())

    notes = []
    if last.get("bpm_note") != "ok":
        notes.append(f"HR: {last.get('bpm_note')}")
    if last.get("spo2_note") != "ok":
        notes.append(f"SpO2: {last.get('spo2_note')}")
    status_text.set_text("\n".join(notes))

    axes[0].set_title(f"Live signal | HR {fmt(last['bpm'], ' BPM')} | SpO2 {fmt(last['spo2'], ' %')}")
    fig.canvas.draw_idle()
    fig.canvas.flush_events()


def run_live(cfg):
    rows = []
    metrics = []
    start = time.monotonic()
    plot_state = make_plot(cfg)

    with dwf.Device() as device:
        setup_scope(device, cfg)
        set_leds(device, cfg, led_660=False, led_940=False)

        try:
            while time.monotonic() - start < cfg.total_varighed_s:
                row = measure_cycle(device, cfg)
                row["t_s"] = time.monotonic() - start
                rows.append(row)

                data = pd.DataFrame(rows)
                r_value, spo2, spo2_note = calculate_spo2(data, cfg)
                bpm, pulse_indices, pulse_kind, bpm_note = calculate_bpm(data, cfg)

                metrics.append(
                    {
                        "t_s": row["t_s"],
                        "R": r_value,
                        "spo2": spo2,
                        "bpm": bpm,
                        "spo2_note": spo2_note,
                        "bpm_note": bpm_note,
                    }
                )
                update_plot(plot_state, data, metrics, pulse_indices, pulse_kind, cfg)

        except KeyboardInterrupt:
            print("\nAfbrudt af bruger.")
        finally:
            set_leds(device, cfg, led_660=False, led_940=False)
            plt.ioff()
            plt.show()

    return pd.DataFrame(rows), pd.DataFrame(metrics)


def led_pulse_only_test(cfg, cycles=20, fase_varighed_s=None):
    if fase_varighed_s is None:
        fase_varighed_s = cfg.phase_total_s

    print("Starter LED-test")
    print(f"DIO{cfg.dio_660}/Lead 0: 660 nm")
    print(f"DIO{cfg.dio_940}/Lead 1: 940 nm")
    print(f"Cyklusfrekvens: {cfg.cycle_rate_hz:.2f} Hz ({fase_varighed_s * 1000:.1f} ms pr. tilstand)")

    with dwf.Device() as device:
        try:
            for cycle in range(cycles):
                print(f"Cyklus {cycle + 1}/{cycles}: 660 nm ON, 940 nm OFF", end="\r")
                set_leds(device, cfg, led_660=True, led_940=False)
                time.sleep(fase_varighed_s)

                print(f"Cyklus {cycle + 1}/{cycles}: 660 nm OFF, 940 nm ON", end="\r")
                set_leds(device, cfg, led_660=False, led_940=True)
                time.sleep(fase_varighed_s)

                print(f"Cyklus {cycle + 1}/{cycles}: begge LED'er OFF       ", end="\r")
                set_leds(device, cfg, led_660=False, led_940=False)
                time.sleep(fase_varighed_s)
        except KeyboardInterrupt:
            print("\nAfbrudt af bruger.")
        finally:
            set_leds(device, cfg, led_660=False, led_940=False)
            print("\nLED-test færdig. Begge LED'er er slukket.")


def parse_args():
    parser = argparse.ArgumentParser(description="Live pulsoximeter-demo med Discovery 3")
    parser.add_argument("--duration", type=float, default=90, help="Måletid i sekunder")
    parser.add_argument("--range", dest="analog_range_v", type=float, default=2.0, help="Scope-område i volt")
    parser.add_argument(
        "--cycle-rate",
        type=float,
        default=10.0,
        help="Komplette 660/940/mørke-cyklusser pr. sekund",
    )
    parser.add_argument(
        "--max-cycle-rate",
        type=float,
        default=20.0,
        help="Sikkerhedsloft for --cycle-rate i komplette cyklusser pr. sekund",
    )
    parser.add_argument(
        "--settle",
        type=float,
        default=0.005,
        help="Ventetid efter hvert LED-skift i sekunder",
    )
    parser.add_argument(
        "--peak-prominence",
        type=float,
        default=0.3,
        help="Peak-prominence som andel af seneste peak-to-peak-signal til HR-detektion",
    )
    parser.add_argument(
        "--smooth-window",
        type=float,
        default=0.35,
        help="Udglatningsvindue i sekunder før HR-peak-detektion",
    )
    parser.add_argument("--led-test", action="store_true", help="Kør kun 660/940/off LED-test")
    parser.add_argument("--led-test-cycles", type=int, default=20)
    parser.add_argument(
        "--led-test-phase",
        type=float,
        default=None,
        help="Sekunder pr. LED-testtilstand. Standard er fasetiden fra --cycle-rate.",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    try:
        cfg = MåleConfig(
            total_varighed_s=args.duration,
            analog_range_v=args.analog_range_v,
            cycle_rate_hz=args.cycle_rate,
            max_cycle_rate_hz=args.max_cycle_rate,
            settle_s=args.settle,
            peak_prominence_fraction=args.peak_prominence,
            smoothing_window_s=args.smooth_window,
        )
    except ValueError as exc:
        raise SystemExit(f"Konfigurationsfejl: {exc}") from exc

    if args.led_test:
        led_pulse_only_test(cfg, cycles=args.led_test_cycles, fase_varighed_s=args.led_test_phase)
        return

    print(f"Starter live-måling i {cfg.total_varighed_s:.0f} s")
    print(
        f"Cyklusfrekvens: {cfg.cycle_rate_hz:.2f} Hz | "
        f"målefase: {cfg.fase_varighed_s * 1000:.1f} ms | "
        f"settle: {cfg.settle_s * 1000:.1f} ms | "
        f"aktiv LED-duty: {100 * cfg.active_led_duty:.1f}%"
    )
    print("Luk plotvinduet eller tryk Ctrl+C for at stoppe.")
    run_live(cfg)


if __name__ == "__main__":
    main()
