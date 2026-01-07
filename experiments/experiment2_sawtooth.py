from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import matplotlib.pyplot as plt
import numpy as np

from core.vacuum_chamber import VacuumChamber
from flight_recorder.mission_logger import FlightRecorder


@dataclass(frozen=True)
class Experiment2Config:
    grid_size: int = 1000
    time_steps: int = 3000
    dt: float = 0.05
    dx: float = 0.1
    c: float = 1.0

    mirror_width: float = 5.0
    mirror_height: float = 50.0

    amplitude: float = 15.0
    start_time: int = 500
    rise_time: int = 100
    fall_time: int = 1000


def _smoothstep(progress: float) -> float:
    # 3x^2 - 2x^3
    return (3.0 * progress**2) - (2.0 * progress**3)


def mirror_displacement(*, t: int, cfg: Experiment2Config) -> float:
    """Sawtooth: fast-out then slow-back with smooth corners."""
    if t < cfg.start_time:
        return 0.0

    if t < cfg.start_time + cfg.rise_time:
        progress = (t - cfg.start_time) / cfg.rise_time
        return float(cfg.amplitude * _smoothstep(progress))

    if t < cfg.start_time + cfg.rise_time + cfg.fall_time:
        progress = (t - (cfg.start_time + cfg.rise_time)) / cfg.fall_time
        return float(cfg.amplitude * (1.0 - _smoothstep(progress)))

    return 0.0


def run(*, seed: int = 42, cfg: Optional[Experiment2Config] = None) -> str:
    """Runs Experiment 2 (sawtooth asymmetric break) and returns report filename."""
    cfg = cfg or Experiment2Config()

    with FlightRecorder("experiment2_sawtooth_asymmetric_break") as flight:
        flight.log_metric("Driver Profile", "Sawtooth (Fast-Out / Slow-Back)")
        flight.log_metric("Asymmetry Ratio", f"{cfg.fall_time / cfg.rise_time:.1f}:1")
        flight.log_metric("TIME_STEPS", cfg.time_steps)
        flight.log_metric("DT", cfg.dt)
        flight.log_metric("Amplitude", cfg.amplitude)

        sim = VacuumChamber(cfg.grid_size, cfg.dx)
        sim.seed_vacuum_noise(seed=seed, sigma=0.001)

        v_potentials_last = None
        for t in range(cfg.time_steps):
            displacement = mirror_displacement(t=t, cfg=cfg)
            x_center = (cfg.grid_size / 2.0) * cfg.dx + displacement
            sim.mirror_pos_history.append(float(x_center))

            V = cfg.mirror_height * np.exp(
                -((sim.x - x_center) ** 2) / (2 * cfg.mirror_width**2)
            )
            v_potentials_last = V

            sim.step(dt=cfg.dt, c=cfg.c, v_potential=V)

        force_arr = np.asarray(sim.mirror_force)
        integrate = getattr(np, "trapezoid", None) or getattr(np, "trapz")
        net_impulse = float(integrate(force_arr, dx=cfg.dt))

        flight.log_metric("Net Impulse", net_impulse)
        if abs(net_impulse) > 1e-4:
            flight.log_metric("Regime", "NON-CONSERVATIVE (Asymmetry Detected)")
        else:
            flight.log_metric("Regime", "Conservative (Symmetry Dominates)")

        fig, (ax1, ax2, ax3) = plt.subplots(3, 1, figsize=(10, 12))

        ax1.set_title("Vacuum Wake State (Final)")
        ax1.plot(sim.x, sim.phi, linewidth=1)
        if v_potentials_last is not None:
            ax1.plot(sim.x, v_potentials_last / 10.0, linestyle="--")

        ax2.set_title("Mirror Trajectory (Sawtooth)")
        ax2.plot(sim.mirror_pos_history)

        ax3.set_title(f"Force Budget (Net Impulse: {net_impulse:.2e})")
        ax3.plot(sim.mirror_force, label="Vacuum Force")
        ax3.axhline(0, linewidth=0.5, linestyle="--")
        ax3.legend()

        plt.tight_layout()
        flight.save_plot(fig, filename="visual_telemetry.png")
        flight.log_metric("Plot Filename", "visual_telemetry.png")
        plt.close(fig)

        return "COUNCIL_REPORT.md"
