from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import matplotlib.pyplot as plt
import numpy as np

from core.vacuum_chamber import VacuumChamber
from flight_recorder.mission_logger import FlightRecorder


class LangevinVacuumChamber(VacuumChamber):
    """Damped wave equation with FDT compliance (reusable from 4B/4C)."""
    
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

        # 3. Damped Verlet integration
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
class Experiment4DConfig:
    # Grid parameters
    grid_size: int = 1000
    dx: float = 0.1
    dt: float = 0.02  # Finer timestep
    c: float = 1.0

    # High-Q damping (10x lower than 4B/4C)
    gamma: float = 0.001

    # High-power drive (2.5x stronger than Exp 3)
    g0: float = 5.0
    g1: float = 3.75
    omega: float = 1.0
    phi: float = np.pi / 2  # Optimal geometric phase

    # Long integration (10x longer than 4C)
    n_cycles: int = 200

    # Coupler geometry (Floquet 2-delta configuration)
    coupler_separation: float = 20.0
    coupler_width: float = 1.0  # Narrow delta approximation

    @property
    def period(self) -> int:
        """Steps per drive cycle."""
        return int(2 * np.pi / (self.omega * self.dt))

    @property
    def total_steps(self) -> int:
        """Total integration steps."""
        return self.period * self.n_cycles

    @property
    def transient_fraction(self) -> float:
        """Fraction of data to discard as transient."""
        return 0.2


def run(*, seed: int = 42, cfg: Optional[Experiment4DConfig] = None) -> str:
    """High-power Floquet optimization to achieve SNR > 10 at T=0.
    
    Goal: Establish strong baseline signal before thermal stress testing.
    Strategy: Lower damping, stronger drive, longer integration.
    """
    cfg = cfg or Experiment4DConfig()

    with FlightRecorder("experiment4d_high_power") as flight:
        flight.log_metric("Protocol", "High-Power SNR Optimization")
        flight.log_metric("Drive Strength", f"g₀={cfg.g0}, g₁={cfg.g1}")
        flight.log_metric("Damping (γ)", cfg.gamma)
        flight.log_metric("Integration", f"{cfg.n_cycles} cycles")
        flight.log_metric("Timestep (dt)", cfg.dt)
        flight.log_metric("Target SNR", "> 10.0")

        print(f"High-Power Optimization: {cfg.n_cycles} cycles, γ={cfg.gamma}")
        print(f"Drive: g₀={cfg.g0}, g₁={cfg.g1}, φ={cfg.phi:.3f}")

        # === INITIALIZE CHAMBER ===
        sim = LangevinVacuumChamber(
            cfg.grid_size,
            cfg.dx,
            cfg.dt,
            gamma=cfg.gamma,
            temperature=0.0,  # T=0 baseline
        )

        # Seed vacuum state
        rng = np.random.default_rng(seed)
        sim.phi = rng.normal(0, 0.001, cfg.grid_size)
        sim.phi_prev = np.copy(sim.phi)

        # === FLOQUET TWO-COUPLER GEOMETRY ===
        x_center = (cfg.grid_size / 2.0) * cfg.dx
        x1 = x_center - cfg.coupler_separation / 2
        x2 = x_center + cfg.coupler_separation / 2

        # Gaussian delta approximations
        x_grid = np.arange(cfg.grid_size) * cfg.dx
        coupler1_profile = np.exp(-((x_grid - x1) ** 2) / (2 * cfg.coupler_width**2))
        coupler2_profile = np.exp(-((x_grid - x2) ** 2) / (2 * cfg.coupler_width**2))

        # Normalize to conserve coupling strength
        coupler1_profile /= np.sum(coupler1_profile) * cfg.dx
        coupler2_profile /= np.sum(coupler2_profile) * cfg.dx

        force_history = []
        time_history = []

        # === TIME EVOLUTION ===
        for step in range(cfg.total_steps):
            t = step * cfg.dt

            # Floquet drive: g(t) = g₀ + g₁·cos(Ωt + φ)
            g1_t = cfg.g0 + cfg.g1 * np.cos(cfg.omega * t)
            g2_t = cfg.g0 + cfg.g1 * np.cos(cfg.omega * t + cfg.phi)

            # Construct time-dependent potential
            V = g1_t * coupler1_profile + g2_t * coupler2_profile

            # Step physics
            sim.step_damped(c=cfg.c, v_potential=V)

            force_history.append(sim.mirror_force[-1])
            time_history.append(t)

            # Progress indicator
            if step % (cfg.period * 20) == 0 and step > 0:
                progress_pct = 100 * step / cfg.total_steps
                print(f"  Progress: {progress_pct:.1f}% ({step}/{cfg.total_steps} steps)")

        # === ANALYSIS: STEADY-STATE THRUST ===
        force_arr = np.asarray(force_history)
        time_arr = np.asarray(time_history)

        # Discard transient (first 20%)
        transient_idx = int(len(force_arr) * cfg.transient_fraction)
        steady_force = force_arr[transient_idx:]

        # DC component (net thrust)
        net_thrust = float(np.mean(steady_force))

        # Noise floor (standard error of the mean)
        noise_floor = float(np.std(steady_force) / np.sqrt(len(steady_force)))

        # Signal-to-Noise Ratio
        snr = abs(net_thrust / noise_floor) if noise_floor > 0 else 0.0

        flight.log_metric("Net Thrust (DC)", net_thrust)
        flight.log_metric("Noise Floor (StdErr)", noise_floor)
        flight.log_metric("SNR", snr)

        if snr > 10.0:
            outcome = f"✓ SIGNAL LOCKED (SNR={snr:.1f})"
            flight.log_metric("Outcome", "HIGH_SNR")
        elif snr > 2.0:
            outcome = f"⚠ MARGINAL SIGNAL (SNR={snr:.1f})"
            flight.log_metric("Outcome", "MARGINAL_SNR")
        else:
            outcome = f"✗ WEAK SIGNAL (SNR={snr:.1f})"
            flight.log_metric("Outcome", "WEAK_SNR")

        print(f"\n=== OPTIMIZATION RESULT ===")
        print(f"Net Thrust:  {net_thrust:.3e}")
        print(f"Noise Floor: {noise_floor:.3e}")
        print(f"SNR:         {snr:.2f}")
        print(f"Status:      {outcome}")

        # === VISUALIZATION ===
        fig = plt.figure(figsize=(12, 10))
        gs = fig.add_gridspec(3, 2, hspace=0.3)

        # Plot 1: Full force time series
        ax1 = fig.add_subplot(gs[0, :])
        ax1.plot(time_arr, force_arr, linewidth=0.5, alpha=0.7)
        ax1.axvline(
            time_arr[transient_idx],
            color="red",
            linestyle="--",
            alpha=0.5,
            label="Transient Cutoff",
        )
        ax1.axhline(net_thrust, color="cyan", linestyle=":", label=f"Mean = {net_thrust:.2e}")
        ax1.set_title(f"Force Time Series ({cfg.n_cycles} cycles)")
        ax1.set_xlabel("Time")
        ax1.set_ylabel("Force")
        ax1.legend()
        ax1.grid(True, alpha=0.3)

        # Plot 2: Steady-state zoomed (last 2000 points)
        ax2 = fig.add_subplot(gs[1, 0])
        zoom_points = min(2000, len(steady_force))
        ax2.plot(steady_force[-zoom_points:], linewidth=0.8)
        ax2.axhline(net_thrust, color="cyan", linestyle="--")
        ax2.set_title(f"Steady State (Last {zoom_points} Steps)")
        ax2.set_xlabel("Step")
        ax2.set_ylabel("Force")
        ax2.grid(True, alpha=0.3)

        # Plot 3: Lock-in convergence (cumulative mean)
        ax3 = fig.add_subplot(gs[1, 1])
        cum_mean = np.cumsum(steady_force) / (np.arange(len(steady_force)) + 1)
        ax3.plot(cum_mean, color="lime", linewidth=2)
        ax3.axhline(net_thrust, color="white", linestyle="--", alpha=0.5)
        ax3.set_title("Lock-in Convergence")
        ax3.set_xlabel("Integration Steps")
        ax3.set_ylabel("Cumulative Mean")
        ax3.grid(True, alpha=0.3)

        # Plot 4: Force histogram (distribution)
        ax4 = fig.add_subplot(gs[2, 0])
        ax4.hist(steady_force, bins=50, alpha=0.7, edgecolor="black")
        ax4.axvline(net_thrust, color="red", linestyle="--", linewidth=2, label="Mean")
        ax4.set_title("Force Distribution (Steady State)")
        ax4.set_xlabel("Force")
        ax4.set_ylabel("Count")
        ax4.legend()
        ax4.grid(True, alpha=0.3)

        # Plot 5: SNR metric display
        ax5 = fig.add_subplot(gs[2, 1])
        ax5.axis("off")
        metric_text = f"""
        === OPTIMIZATION METRICS ===
        
        Net Thrust:    {net_thrust:.3e}
        Noise Floor:   {noise_floor:.3e}
        SNR:           {snr:.2f}
        
        Drive:         g₀={cfg.g0}, g₁={cfg.g1}
        Damping:       γ={cfg.gamma}
        Cycles:        {cfg.n_cycles}
        Phase:         φ={cfg.phi:.3f} rad
        
        Status:        {outcome}
        """
        ax5.text(
            0.1,
            0.5,
            metric_text,
            fontsize=11,
            family="monospace",
            verticalalignment="center",
        )

        plt.tight_layout()
        flight.save_plot(fig, filename="visual_telemetry.png")
        plt.close(fig)

        return "COUNCIL_REPORT.md"
