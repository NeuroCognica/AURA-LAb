from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import matplotlib.pyplot as plt
import numpy as np

from core.vacuum_chamber import VacuumChamber
from flight_recorder.mission_logger import FlightRecorder


class LangevinVacuumChamber(VacuumChamber):
    """High-fidelity Langevin chamber with FDT compliance."""
    
    def __init__(
        self,
        nx: int,
        dx: float,
        dt: float,
        gamma: float = 0.001,
        temperature: float = 0.0,
    ):
        super().__init__(nx, dx)
        self.gamma = gamma
        self.temp = temperature
        self.dt = dt

        # FDT noise scale
        if self.temp > 0 and self.gamma > 0:
            self.noise_scale = float(np.sqrt(2 * self.gamma * self.temp / self.dt))
        else:
            self.noise_scale = 0.0

    def step_damped(self, *, c: float, v_potential: np.ndarray) -> None:
        """Advance field one timestep with damping and FDT noise."""
        # 1. Laplacian
        laplacian = (
            np.roll(self.phi, -1) - 2 * self.phi + np.roll(self.phi, 1)
        ) / (self.dx**2)

        # 2. Forces
        interaction = v_potential * self.phi
        noise = np.zeros(self.nx)
        if self.noise_scale > 0:
            noise = np.random.normal(0, self.noise_scale, self.nx)

        forces = (c**2) * laplacian - interaction + noise

        # 3. Damped Verlet
        denom = 1.0 + (self.gamma * self.dt / 2.0)
        term1 = 2.0 * self.phi
        term2 = self.phi_prev * (1.0 - (self.gamma * self.dt / 2.0))
        term3 = (self.dt**2) * forces

        self.phi_next = (term1 - term2 + term3) / denom

        # Boundaries
        self.phi_next[0] = 0.0
        self.phi_next[-1] = 0.0

        # 4. Force calculation
        grad_v = np.gradient(v_potential, self.dx)
        force = -float(np.sum((self.phi**2) * grad_v) * self.dx)
        self.mirror_force.append(force)

        # 5. Energy
        dphi_dt = (self.phi_next - self.phi_prev) / (2 * self.dt)
        dphi_dx = np.gradient(self.phi, self.dx)
        energy = 0.5 * float(
            np.sum(dphi_dt**2 + (c**2) * dphi_dx**2 + v_potential * self.phi**2)
            * self.dx
        )
        self.total_energy_field.append(energy)

        # Cycle
        self.phi_prev = np.copy(self.phi)
        self.phi = np.copy(self.phi_next)


@dataclass(frozen=True)
class Experiment4EConfig:
    # Grid parameters (from 4D)
    grid_size: int = 1000
    dx: float = 0.1
    dt: float = 0.02
    c: float = 1.0

    # High-Q damping (from 4D)
    gamma: float = 0.001

    # High-power drive (from 4D)
    g0: float = 5.0
    g1: float = 3.75
    omega: float = 1.0
    phi: float = np.pi / 2

    # Long integration (from 4D)
    n_cycles: int = 200

    # Coupler geometry
    coupler_separation: float = 20.0
    coupler_width: float = 1.0

    # Temperature sweep
    temp_min: float = 0.0
    temp_max: float = 0.025
    temp_steps: int = 6

    @property
    def period(self) -> int:
        return int(2 * np.pi / (self.omega * self.dt))

    @property
    def total_steps(self) -> int:
        return self.period * self.n_cycles

    @property
    def transient_fraction(self) -> float:
        return 0.2


def run(*, seed: int = 42, cfg: Optional[Experiment4EConfig] = None) -> str:
    """High-fidelity thermal stress test with optimized parameters.
    
    Tests thermal robustness of the high-power Floquet pump (SNR=21 at T=0).
    Critical question: Does strong drive preserve coherence at higher T?
    """
    cfg = cfg or Experiment4EConfig()

    with FlightRecorder("experiment4e_thermal_stress_optimized") as flight:
        flight.log_metric("Protocol", "High-Fidelity Thermal Sweep")
        flight.log_metric("Drive", f"g₀={cfg.g0}, g₁={cfg.g1}")
        flight.log_metric("Damping (γ)", cfg.gamma)
        flight.log_metric("Integration", f"{cfg.n_cycles} cycles")
        flight.log_metric("Temp Range", f"{cfg.temp_min} - {cfg.temp_max}")

        print(f"High-Fidelity Thermal Sweep: {cfg.temp_steps} temperatures")
        print(f"Previous baseline: SNR=21.1 at T=0 (Run 9f05efed)")
        print(f"Previous Tc: 0.01 (weak drive)")
        print(f"Hypothesis: Strong drive (g₀={cfg.g0}) stiffens geometric phase\n")

        temp_levels = np.linspace(cfg.temp_min, cfg.temp_max, cfg.temp_steps)
        results_mean = []
        results_err = []
        results_snr = []

        # Floquet coupler setup
        x_center = (cfg.grid_size / 2.0) * cfg.dx
        x1 = x_center - cfg.coupler_separation / 2
        x2 = x_center + cfg.coupler_separation / 2

        x_grid = np.arange(cfg.grid_size) * cfg.dx
        coupler1_profile = np.exp(-((x_grid - x1) ** 2) / (2 * cfg.coupler_width**2))
        coupler2_profile = np.exp(-((x_grid - x2) ** 2) / (2 * cfg.coupler_width**2))

        coupler1_profile /= np.sum(coupler1_profile) * cfg.dx
        coupler2_profile /= np.sum(coupler2_profile) * cfg.dx

        for i_temp, temp in enumerate(temp_levels):
            # Initialize chamber
            sim = LangevinVacuumChamber(
                cfg.grid_size,
                cfg.dx,
                cfg.dt,
                gamma=cfg.gamma,
                temperature=float(temp),
            )

            # Seed
            rng = np.random.default_rng(seed + i_temp * 500)
            sim.phi = rng.normal(0, 0.001, cfg.grid_size)
            sim.phi_prev = np.copy(sim.phi)

            force_history = []

            # Time evolution
            for step in range(cfg.total_steps):
                t = step * cfg.dt

                # Floquet drive
                g1_t = cfg.g0 + cfg.g1 * np.cos(cfg.omega * t)
                g2_t = cfg.g0 + cfg.g1 * np.cos(cfg.omega * t + cfg.phi)

                # Construct potential
                V = g1_t * coupler1_profile + g2_t * coupler2_profile

                sim.step_damped(c=cfg.c, v_potential=V)
                force_history.append(sim.mirror_force[-1])

            # Lock-in analysis (steady state)
            transient_idx = int(cfg.total_steps * cfg.transient_fraction)
            steady_force = np.asarray(force_history[transient_idx:])

            net_thrust = float(np.mean(steady_force))
            std_dev = float(np.std(steady_force))
            std_err = std_dev / np.sqrt(len(steady_force))

            results_mean.append(net_thrust)
            results_err.append(std_err)

            snr = abs(net_thrust / std_err) if std_err > 0 else 0.0
            results_snr.append(snr)

            status = "✓ LOCKED" if snr > 2.0 else "✗ DECOHERED"
            print(f"  T={temp:.4f}: Thrust={net_thrust:+.2e}, SNR={snr:5.1f} [{status}]")

        # === ANALYSIS ===
        baseline_thrust = results_mean[0]
        baseline_snr = results_snr[0]

        flight.log_metric("Baseline Thrust (T=0)", baseline_thrust)
        flight.log_metric("Baseline SNR (T=0)", baseline_snr)

        # Determine Tc (where SNR drops below 2.0)
        critical_temp = None
        for T, snr in zip(temp_levels[1:], results_snr[1:], strict=False):
            if snr < 2.0:
                critical_temp = float(T)
                break

        if critical_temp is None:
            tc_str = f"> {cfg.temp_max:.4f} (Robust)"
            robustness = "PASS"
        else:
            tc_str = f"{critical_temp:.4f} (Signal Lost)"
            robustness = f"FAIL at T={critical_temp:.4f}"

        flight.log_metric("Critical Temp (Tc)", tc_str)
        flight.log_metric("Thermal Robustness", robustness)

        # Determine T_50% (where thrust drops to 50% of baseline)
        threshold_50 = baseline_thrust * 0.5
        temp_50 = None
        for T, thrust in zip(temp_levels[1:], results_mean[1:], strict=False):
            if abs(thrust) < abs(threshold_50):
                temp_50 = float(T)
                break

        if temp_50:
            flight.log_metric("T_50% (Half Efficiency)", temp_50)

        print(f"\n=== THERMAL STRESS SUMMARY ===")
        print(f"Baseline SNR:       {baseline_snr:.1f}")
        print(f"Critical Temp (Tc): {tc_str}")
        print(f"Robustness:         {robustness}")

        # === VISUALIZATION ===
        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 10))

        # Plot 1: Thrust vs Temperature
        ax1.errorbar(
            temp_levels,
            results_mean,
            yerr=results_err,
            fmt="-o",
            color="cyan",
            ecolor="magenta",
            capsize=5,
            label="Net Thrust",
        )
        ax1.axhline(0, color="gray", linestyle="--", alpha=0.3)
        ax1.axhline(
            baseline_thrust * 0.5,
            color="yellow",
            linestyle=":",
            label="50% Efficiency",
        )
        if critical_temp is not None:
            ax1.axvline(
                critical_temp,
                color="red",
                linestyle="--",
                alpha=0.5,
                label=f"Tc = {critical_temp:.4f}",
            )
        ax1.set_title(
            f"Thermal Decoherence Profile (Optimized Drive) | Tc = {tc_str}"
        )
        ax1.set_xlabel("Temperature (Simulation Units)")
        ax1.set_ylabel("Net Thrust")
        ax1.legend()
        ax1.grid(True, alpha=0.3)

        # Plot 2: SNR vs Temperature
        ax2.plot(temp_levels, results_snr, marker="s", linewidth=2, label="SNR")
        ax2.axhline(2.0, color="red", linestyle="--", label="Detectability Threshold")
        ax2.axhline(10.0, color="green", linestyle=":", label="High Confidence")
        if critical_temp is not None:
            ax2.axvline(critical_temp, color="red", linestyle="--", alpha=0.5)
        ax2.set_title("Signal-to-Noise Ratio vs Temperature")
        ax2.set_xlabel("Temperature")
        ax2.set_ylabel("SNR")
        ax2.set_yscale("log")
        ax2.legend()
        ax2.grid(True, alpha=0.3, which="both")

        plt.tight_layout()
        flight.save_plot(fig, filename="visual_telemetry.png")
        plt.close(fig)

        return "COUNCIL_REPORT.md"
