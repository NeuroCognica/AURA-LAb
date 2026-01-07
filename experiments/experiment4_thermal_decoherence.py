from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import matplotlib.pyplot as plt
import numpy as np

from core.vacuum_chamber import VacuumChamber
from flight_recorder.mission_logger import FlightRecorder


class NoisyVacuumChamber(VacuumChamber):
    """Extends VacuumChamber to include Langevin thermal noise.
    
    Equation: d²φ/dt² - c² d²φ/dx² = -V(x)φ + ξ(t)
    
    where ξ(t) is Gaussian white noise representing thermal phonon coupling.
    """
    
    def __init__(self, nx: int, dx: float, noise_amplitude: float = 0.0):
        super().__init__(nx, dx)
        self.noise_amp = noise_amplitude

    def step(self, *, dt: float, c: float, v_potential: np.ndarray) -> None:
        """Advance field one timestep with thermal noise injection."""
        # 1. Deterministic wave equation update
        laplacian = (
            np.roll(self.phi, -1) - 2 * self.phi + np.roll(self.phi, 1)
        ) / (self.dx**2)
        interaction = v_potential * self.phi

        self.phi_next = 2 * self.phi - self.phi_prev + (dt**2) * (
            (c**2) * laplacian - interaction
        )

        # 2. INJECT THERMAL NOISE (stochastic Langevin kick)
        # Simulates coupling to thermal phonon bath at temperature T
        if self.noise_amp > 0:
            thermal_kick = np.random.normal(0, self.noise_amp, self.nx) * (dt**2)
            self.phi_next += thermal_kick

        # 3. Boundary conditions
        self.phi_next[0] = 0.0
        self.phi_next[-1] = 0.0

        # 4. Calculate force (back-reaction)
        grad_v = np.gradient(v_potential, self.dx)
        force = -float(np.sum((self.phi**2) * grad_v) * self.dx)
        self.mirror_force.append(force)

        # 5. Calculate field energy
        dphi_dt = (self.phi_next - self.phi_prev) / (2 * dt)
        dphi_dx = np.gradient(self.phi, self.dx)
        energy = 0.5 * float(
            np.sum(dphi_dt**2 + (c**2) * dphi_dx**2 + v_potential * self.phi**2)
            * self.dx
        )
        self.total_energy_field.append(energy)

        # Cycle buffers
        self.phi_prev = np.copy(self.phi)
        self.phi = np.copy(self.phi_next)


@dataclass(frozen=True)
class Experiment4Config:
    grid_size: int = 1000
    time_steps: int = 3000
    dt: float = 0.05
    dx: float = 0.1
    c: float = 1.0

    mirror_width: float = 5.0
    mirror_height_solid: float = 50.0
    mirror_height_ghost: float = 5.0

    amplitude: float = 15.0
    start_time: int = 500
    rise_time: int = 100
    fall_time: int = 1000

    # Temperature sweep
    temp_min: float = 0.0
    temp_max: float = 0.05
    temp_steps: int = 10


def _smoothstep(progress: float) -> float:
    return (3.0 * progress**2) - (2.0 * progress**3)


def run(*, seed: int = 42, cfg: Optional[Experiment4Config] = None) -> str:
    """Thermal decoherence stress test: sweep temperature to find Tc.
    
    Subjects the proven sawtooth ratchet mechanism to Langevin thermal noise
    and measures thrust degradation as a function of temperature.
    """
    cfg = cfg or Experiment4Config()

    with FlightRecorder("experiment4_thermal_decoherence") as flight:
        flight.log_metric("Test Protocol", "Langevin Thermal Sweep")
        flight.log_metric("Driver", "Sawtooth (Fast-Out / Slow-Back)")
        flight.log_metric("TIME_STEPS", cfg.time_steps)
        flight.log_metric("Temp Range", f"{cfg.temp_min} - {cfg.temp_max}")
        flight.log_metric("Temp Steps", cfg.temp_steps)

        temp_levels = np.linspace(cfg.temp_min, cfg.temp_max, cfg.temp_steps)
        thrust_results = []
        
        print(f"Starting Thermal Stress Test on {len(temp_levels)} setpoints...")

        for i, temp in enumerate(temp_levels):
            # Initialize noisy chamber with current temperature
            sim = NoisyVacuumChamber(cfg.grid_size, cfg.dx, noise_amplitude=float(temp))

            # Seed vacuum with ZPF baseline + slight variation per run
            rng = np.random.default_rng(seed + i)
            sim.phi = rng.normal(0, 0.001, cfg.grid_size)
            sim.phi_prev = np.copy(sim.phi)

            # Run simulation loop with thermal noise
            for t in range(cfg.time_steps):
                # Sawtooth trajectory with coupling modulation
                coupling = 1.0
                displacement = 0.0

                if t < cfg.start_time:
                    displacement = 0.0
                    coupling = 1.0
                elif t < cfg.start_time + cfg.rise_time:
                    # FAST OUT (Slip - low coupling)
                    progress = (t - cfg.start_time) / cfg.rise_time
                    displacement = cfg.amplitude * _smoothstep(progress)
                    coupling = 0.1
                elif t < cfg.start_time + cfg.rise_time + cfg.fall_time:
                    # SLOW BACK (Grip - high coupling)
                    progress = (t - (cfg.start_time + cfg.rise_time)) / cfg.fall_time
                    displacement = cfg.amplitude * (1.0 - _smoothstep(progress))
                    coupling = 1.0
                else:
                    displacement = 0.0
                    coupling = 1.0

                x_center = (cfg.grid_size / 2.0) * cfg.dx + displacement
                sim.mirror_pos_history.append(float(x_center))

                # Modulate potential (grip/slip)
                V_amp = cfg.mirror_height_solid * coupling
                V = V_amp * np.exp(
                    -((sim.x - x_center) ** 2) / (2 * cfg.mirror_width**2)
                )

                # Step physics (now with thermal noise)
                sim.step(dt=cfg.dt, c=cfg.c, v_potential=V)

            # Measure net impulse (rectified thrust)
            force_arr = np.asarray(sim.mirror_force)
            integrate = getattr(np, "trapezoid", None) or getattr(np, "trapz")
            net_impulse = float(integrate(force_arr, dx=cfg.dt))
            thrust_results.append(net_impulse)

            status = "STABLE" if abs(net_impulse) > 1e-4 else "COLLAPSED"
            print(f"  > Temp {temp:.4f}: Impulse = {net_impulse:.2e} [{status}]")

        # === ANALYSIS: Find Critical Temperature ===
        baseline_thrust = thrust_results[0]
        critical_temp = "UNDEFINED (Robust to T_max)"
        critical_temp_value = None
        
        for T, thrust in zip(temp_levels, thrust_results):
            if abs(thrust) < abs(baseline_thrust) * 0.5:
                critical_temp = f"{T:.4f} (Sim Units)"
                critical_temp_value = float(T)
                break

        flight.log_metric("Baseline Thrust (T=0)", baseline_thrust)
        flight.log_metric("Critical Temp (Tc)", critical_temp)
        flight.log_metric("Thermal Robustness", "PASS" if critical_temp_value is None or critical_temp_value > cfg.temp_max * 0.5 else "FAIL")

        # === VISUALIZATION ===
        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 10))

        # Plot 1: Thrust vs Temperature (Thermal Stability Curve)
        ax1.plot(temp_levels, thrust_results, marker="o", linewidth=2, label="Net Impulse")
        ax1.axhline(0, color="gray", linestyle="--", alpha=0.3)
        ax1.axhline(
            baseline_thrust * 0.5,
            color="red",
            linestyle=":",
            label="50% Efficiency Threshold",
        )
        if critical_temp_value is not None:
            ax1.axvline(
                critical_temp_value,
                color="red",
                linestyle="--",
                alpha=0.5,
                label=f"Tc = {critical_temp_value:.4f}",
            )
        ax1.set_title(f"Thermal Stability Profile (Tc = {critical_temp})")
        ax1.set_xlabel("Noise Amplitude (Temperature)")
        ax1.set_ylabel("Net Rectified Impulse")
        ax1.legend()
        ax1.grid(True, alpha=0.3)

        # Plot 2: Vacuum State at Max Temperature
        ax2.plot(sim.x, sim.phi, linewidth=0.8, label=f"Field State at T={cfg.temp_max:.4f}")
        ax2.set_title("Vacuum Field State at Maximum Temperature")
        ax2.set_xlabel("Position x")
        ax2.set_ylabel("Field φ(x)")
        ax2.legend()
        ax2.grid(True, alpha=0.3)

        plt.tight_layout()
        flight.save_plot(fig, filename="visual_telemetry.png")
        flight.log_metric("Plot Filename", "visual_telemetry.png")
        plt.close(fig)

        flight.log_metric("Net Impulse", float(baseline_thrust))
        return "COUNCIL_REPORT.md"
