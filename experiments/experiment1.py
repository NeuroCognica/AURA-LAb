from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import matplotlib.pyplot as plt
import numpy as np

from core.vacuum_chamber import VacuumChamber
from flight_recorder.mission_logger import FlightRecorder


@dataclass(frozen=True)
class Experiment1Config:
    grid_size: int = 1000
    time_steps: int = 2000
    c: float = 1.0
    dx: float = 0.1
    dt: float = 0.05
    mirror_width: float = 5.0
    mirror_height: float = 50.0

    # Gaussian jerk profile
    center_time: float = 0.3
    width: float = 0.05
    amplitude: float = 10.0


def mirror_position(*, t_step: int, total_steps: int, cfg: Experiment1Config) -> float:
    t = t_step / total_steps
    x_center = (cfg.grid_size / 2.0) * cfg.dx + cfg.amplitude * np.exp(
        -((t - cfg.center_time) ** 2) / (2 * cfg.width**2)
    )
    return float(x_center)


def run(*, seed: int = 42, cfg: Optional[Experiment1Config] = None) -> str:
    """Runs Experiment 1 (Gaussian jerk baseline) and returns path to report."""
    cfg = cfg or Experiment1Config()

    with FlightRecorder("experiment1_gaussian_jerk_baseline") as flight:
        flight.log_metric("Jerk Profile", "Gaussian")
        flight.log_metric("GRID_SIZE", cfg.grid_size)
        flight.log_metric("TIME_STEPS", cfg.time_steps)
        flight.log_metric("DX", cfg.dx)
        flight.log_metric("DT", cfg.dt)

        chamber = VacuumChamber(cfg.grid_size, cfg.dx)
        chamber.seed_vacuum_noise(seed=seed, sigma=0.001)

        v_potentials_last = None
        for t in range(cfg.time_steps):
            x_center = mirror_position(t_step=t, total_steps=cfg.time_steps, cfg=cfg)
            chamber.mirror_pos_history.append(x_center)

            V = cfg.mirror_height * np.exp(
                -((chamber.x - x_center) ** 2) / (2 * cfg.mirror_width**2)
            )
            v_potentials_last = V
            chamber.step(dt=cfg.dt, c=cfg.c, v_potential=V)

        times = np.linspace(0, cfg.time_steps * cfg.dt, cfg.time_steps)
        force_arr = np.asarray(chamber.mirror_force)
        # NumPy 2.x removed np.trapz; use trapezoid and keep a fallback.
        integrate = getattr(np, "trapezoid", None) or getattr(np, "trapz")
        net_impulse = float(integrate(force_arr, dx=cfg.dt))
        flight.log_metric("Net Impulse", net_impulse)
        flight.log_metric(
            "Status",
            "NON-CONSERVATIVE (Thrust!)" if abs(net_impulse) > 1e-4 else "CONSERVATIVE (No Net Thrust)",
        )

        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 8))

        ax1.set_title("The Quantum Wake: Field Excitations emitted by Jerk")
        ax1.plot(chamber.x, chamber.phi, label="Vacuum Field (Phi)")
        if v_potentials_last is not None:
            ax1.plot(chamber.x, v_potentials_last / 10.0, linestyle="--", label="Mirror Position (scaled)")
        ax1.legend()
        ax1.set_ylim(-0.05, 0.05)

        ax2.set_title("Thrust vs. Time")
        ax2.plot(times, chamber.mirror_force, label="Back-Reaction Force")
        ax2.plot(times, np.gradient(chamber.mirror_pos_history), alpha=0.5, label="Mirror Velocity")
        ax2.axhline(0, linewidth=0.5)
        ax2.legend()

        plt.tight_layout()
        flight.save_plot(fig, filename="visual_telemetry.png")
        flight.log_metric("Plot Filename", "visual_telemetry.png")
        plt.close(fig)

        # The recorder writes the report in __exit__.
        # Return the expected path for convenience.
        return "COUNCIL_REPORT.md"
