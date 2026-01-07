from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import matplotlib.pyplot as plt
import numpy as np

from core.vacuum_chamber import VacuumChamber
from flight_recorder.mission_logger import FlightRecorder


class LangevinVacuumChamber(VacuumChamber):
    """Damped wave equation with Fluctuation-Dissipation Theorem compliance.
    
    Equation: d²φ/dt² + γ∂φ/∂t - c²∂²φ/∂x² = -V(x)φ + ξ(t)
    
    where ξ(t) obeys FDT: σ_noise = sqrt(2γkT/dt)
    """
    
    def __init__(
        self,
        nx: int,
        dx: float,
        dt: float,
        gamma: float = 0.01,
        temperature: float = 0.0,
    ):
        super().__init__(nx, dx)
        self.gamma = gamma
        self.temp = temperature
        self.dt = dt

        # Calculate noise scale according to FDT
        # σ = sqrt(2 * γ * k_B * T / dt)
        # Assume k_B = 1.0 in simulation units
        if self.temp > 0 and self.gamma > 0:
            self.noise_scale = float(np.sqrt(2 * self.gamma * self.temp / self.dt))
        else:
            self.noise_scale = 0.0

    def step_damped(self, *, c: float, v_potential: np.ndarray) -> None:
        """Advance field one timestep with damping and FDT-compliant noise."""
        # 1. Laplacian
        laplacian = (
            np.roll(self.phi, -1) - 2 * self.phi + np.roll(self.phi, 1)
        ) / (self.dx**2)

        # 2. Interaction
        interaction = v_potential * self.phi

        # 3. Thermal noise force (stochastic, FDT-linked)
        noise = np.zeros(self.nx)
        if self.noise_scale > 0:
            noise = np.random.normal(0, self.noise_scale, self.nx)

        # 4. Damped Verlet integration
        # Solve: (φ_next - 2φ + φ_prev)/dt² + γ(φ_next - φ_prev)/(2dt) = Forces
        # Rearranging for φ_next:
        # φ_next(1 + γdt/2) = 2φ - φ_prev(1 - γdt/2) + dt²·Forces

        forces = (c**2) * laplacian - interaction + noise

        denom = 1.0 + (self.gamma * self.dt / 2.0)
        term1 = 2.0 * self.phi
        term2 = self.phi_prev * (1.0 - (self.gamma * self.dt / 2.0))
        term3 = (self.dt**2) * forces

        self.phi_next = (term1 - term2 + term3) / denom

        # Boundary conditions
        self.phi_next[0] = 0.0
        self.phi_next[-1] = 0.0

        # 5. Calculate force on mirror (back-reaction)
        grad_v = np.gradient(v_potential, self.dx)
        force = -float(np.sum((self.phi**2) * grad_v) * self.dx)
        self.mirror_force.append(force)

        # 6. Calculate field energy
        dphi_dt = (self.phi_next - self.phi_prev) / (2 * self.dt)
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
class Experiment4BConfig:
    grid_size: int = 1000
    time_steps: int = 3000
    dt: float = 0.05
    dx: float = 0.1
    c: float = 1.0

    gamma: float = 0.02  # Viscous damping coefficient

    mirror_width: float = 5.0
    mirror_height_solid: float = 50.0

    amplitude: float = 15.0
    start_time: int = 500
    rise_time: int = 100
    fall_time: int = 1000

    # Temperature sweep
    temp_min: float = 0.0
    temp_max: float = 0.1
    temp_steps: int = 10

    # Statistical averaging
    sub_runs: int = 3


def _smoothstep(progress: float) -> float:
    return (3.0 * progress**2) - (2.0 * progress**3)


def run(*, seed: int = 42, cfg: Optional[Experiment4BConfig] = None) -> str:
    """FDT-compliant thermal decoherence test with proper damping.
    
    Tests whether the sawtooth ratchet survives when thermal noise
    comes with its mandatory entropy tax (damping term).
    """
    cfg = cfg or Experiment4BConfig()

    with FlightRecorder("experiment4b_langevin_damping") as flight:
        flight.log_metric("Test Protocol", "Damped Langevin Sweep (FDT Compliant)")
        flight.log_metric("Driver", "Sawtooth (Fast-Out / Slow-Back)")
        flight.log_metric("Damping (Gamma)", cfg.gamma)
        flight.log_metric("TIME_STEPS", cfg.time_steps)
        flight.log_metric("Temp Range", f"{cfg.temp_min} - {cfg.temp_max}")
        flight.log_metric("Temp Steps", cfg.temp_steps)
        flight.log_metric("Sub-runs per temp", cfg.sub_runs)

        temp_levels = np.linspace(cfg.temp_min, cfg.temp_max, cfg.temp_steps)
        thrust_mean = []
        thrust_std = []

        print(f"Igniting Damped Thermal Test with Gamma={cfg.gamma}...")

        for i, temp in enumerate(temp_levels):
            # Run multiple sub-runs per temperature to compute statistics
            # (thermal noise causes jitter in the impulse measurement)
            batch_impulses = []

            for sub in range(cfg.sub_runs):
                sim = LangevinVacuumChamber(
                    cfg.grid_size,
                    cfg.dx,
                    cfg.dt,
                    gamma=cfg.gamma,
                    temperature=float(temp),
                )

                # Seed vacuum with ZPF baseline + variation
                rng = np.random.default_rng(seed + i * 100 + sub)
                sim.phi = rng.normal(0, 0.001, cfg.grid_size)
                sim.phi_prev = np.copy(sim.phi)

                # Time evolution loop
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
                        progress = (
                            t - (cfg.start_time + cfg.rise_time)
                        ) / cfg.fall_time
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

                    # Step physics with damping
                    sim.step_damped(c=cfg.c, v_potential=V)

                # Measure net impulse
                force_arr = np.asarray(sim.mirror_force)
                integrate = getattr(np, "trapezoid", None) or getattr(np, "trapz")
                net_impulse = float(integrate(force_arr, dx=cfg.dt))
                batch_impulses.append(net_impulse)

            # Compute statistics over sub-runs
            avg_impulse = float(np.mean(batch_impulses))
            std_impulse = float(np.std(batch_impulses))
            thrust_mean.append(avg_impulse)
            thrust_std.append(std_impulse)

            snr = abs(avg_impulse / std_impulse) if std_impulse > 0 else np.inf
            print(
                f"  > Temp {temp:.3f}: Mean Impulse = {avg_impulse:.2e} +/- {std_impulse:.2e} [SNR={snr:.1f}]"
            )

        # === ANALYSIS: Find Critical Temperature ===
        baseline_thrust = thrust_mean[0]
        baseline_std = thrust_std[0]
        
        flight.log_metric("Baseline Thrust (T=0)", baseline_thrust)
        flight.log_metric("Baseline StdDev", baseline_std)

        # Determine Tc (where signal is lost to noise)
        # Definition: Mean < 2 * StdDev (Signal-to-Noise Ratio < 2)
        critical_temp = "> Max Tested (Robust)"
        critical_temp_value = None

        for T, mean, std in zip(temp_levels[1:], thrust_mean[1:], thrust_std[1:], strict=False):
            if std > 0 and abs(mean) < 2 * std:
                critical_temp = f"{T:.3f} (SNR Collapse)"
                critical_temp_value = float(T)
                break

        flight.log_metric("Critical Temp (Tc)", critical_temp)
        flight.log_metric(
            "Thermal Robustness",
            "PASS" if critical_temp_value is None else f"FAIL at T={critical_temp_value:.3f}",
        )

        # === VISUALIZATION ===
        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 10))

        # Plot 1: Thrust vs Temperature with error bars
        ax1.errorbar(
            temp_levels,
            thrust_mean,
            yerr=thrust_std,
            fmt="-o",
            ecolor="red",
            capsize=5,
            label="Net Thrust ± 1σ",
        )
        ax1.axhline(0, color="gray", linestyle="--", alpha=0.3)
        ax1.axhline(
            baseline_thrust,
            color="cyan",
            linestyle=":",
            alpha=0.5,
            label=f"Baseline (T=0) = {baseline_thrust:.2e}",
        )
        if critical_temp_value is not None:
            ax1.axvline(
                critical_temp_value,
                color="red",
                linestyle="--",
                alpha=0.5,
                label=f"Tc = {critical_temp_value:.3f}",
            )
        ax1.set_title(f"FDT-Compliant Decoherence Profile (γ={cfg.gamma}, Tc={critical_temp})")
        ax1.set_xlabel("Temperature (Simulation Units)")
        ax1.set_ylabel("Net Rectified Impulse")
        ax1.legend()
        ax1.grid(True, alpha=0.3)

        # Plot 2: Signal-to-Noise Ratio vs Temperature
        snr_values = [
            abs(m / s) if s > 0 else 100.0 for m, s in zip(thrust_mean, thrust_std, strict=False)
        ]
        ax2.plot(temp_levels, snr_values, marker="s", linewidth=2, label="SNR")
        ax2.axhline(2.0, color="red", linestyle="--", label="Detectability Threshold (SNR=2)")
        ax2.set_title("Signal-to-Noise Ratio vs Temperature")
        ax2.set_xlabel("Temperature")
        ax2.set_ylabel("SNR = |Mean| / StdDev")
        ax2.set_yscale("log")
        ax2.legend()
        ax2.grid(True, alpha=0.3, which="both")

        plt.tight_layout()
        flight.save_plot(fig, filename="visual_telemetry.png")
        plt.close(fig)

        flight.log_metric("Net Impulse (T=0)", baseline_thrust)
        return "COUNCIL_REPORT.md"
