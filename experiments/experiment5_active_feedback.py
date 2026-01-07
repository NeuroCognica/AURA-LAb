from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import matplotlib.pyplot as plt
import numpy as np

from core.vacuum_chamber import VacuumChamber
from flight_recorder.mission_logger import FlightRecorder


class LangevinVacuumChamber(VacuumChamber):
    """High-fidelity Langevin chamber (from 4E)."""
    
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

        if self.temp > 0 and self.gamma > 0:
            self.noise_scale = float(np.sqrt(2 * self.gamma * self.temp / self.dt))
        else:
            self.noise_scale = 0.0

    def step_damped(self, *, c: float, v_potential: np.ndarray) -> None:
        """Advance field with damping and FDT noise."""
        laplacian = (
            np.roll(self.phi, -1) - 2 * self.phi + np.roll(self.phi, 1)
        ) / (self.dx**2)
        interaction = v_potential * self.phi
        noise = np.zeros(self.nx)
        if self.noise_scale > 0:
            noise = np.random.normal(0, self.noise_scale, self.nx)

        forces = (c**2) * laplacian - interaction + noise

        denom = 1.0 + (self.gamma * self.dt / 2.0)
        term1 = 2.0 * self.phi
        term2 = self.phi_prev * (1.0 - (self.gamma * self.dt / 2.0))
        term3 = (self.dt**2) * forces

        self.phi_next = (term1 - term2 + term3) / denom
        self.phi_next[0] = 0.0
        self.phi_next[-1] = 0.0

        grad_v = np.gradient(v_potential, self.dx)
        force = -float(np.sum((self.phi**2) * grad_v) * self.dx)
        self.mirror_force.append(force)

        dphi_dt = (self.phi_next - self.phi_prev) / (2 * self.dt)
        dphi_dx = np.gradient(self.phi, self.dx)
        energy = 0.5 * float(
            np.sum(dphi_dt**2 + (c**2) * dphi_dx**2 + v_potential * self.phi**2)
            * self.dx
        )
        self.total_energy_field.append(energy)

        self.phi_prev = np.copy(self.phi)
        self.phi = np.copy(self.phi_next)


@dataclass(frozen=True)
class Experiment5Config:
    # Grid parameters (from 4D/4E)
    grid_size: int = 1000
    dx: float = 0.1
    dt: float = 0.02
    c: float = 1.0

    # High-Q damping
    gamma: float = 0.001

    # HIGH TEMPERATURE (beyond passive limit)
    temperature: float = 0.05  # This killed passive ratchet in 4E

    # Drive parameters
    omega: float = 1.0
    phi: float = np.pi / 2

    # Feedback control parameters
    g_solid: float = 5.0  # Full grip
    g_ghost: float = 0.1  # Decloak

    # Integration
    n_cycles: int = 200

    # Coupler geometry
    coupler_separation: float = 20.0
    coupler_width: float = 1.0

    # Feedback strategy
    force_threshold: float = 0.0  # Switch at zero crossing
    feedback_gain_boost: float = 1.0  # Multiplier when thrusting
    feedback_gain_suppress: float = 0.1  # Multiplier when dragging

    @property
    def period(self) -> int:
        return int(2 * np.pi / (self.omega * self.dt))

    @property
    def total_steps(self) -> int:
        return self.period * self.n_cycles

    @property
    def transient_fraction(self) -> float:
        return 0.2


def run(*, seed: int = 42, cfg: Optional[Experiment5Config] = None) -> str:
    """Active feedback (Maxwell's Demon) test at high temperature.
    
    Tests whether information-driven coupling modulation can rectify
    thermal noise beyond the passive thermal limit (Tc ~ 0.02).
    
    Strategy: Monitor instantaneous force. If dragging, reduce coupling.
    If thrusting, increase coupling. Trade CPU cycles for impulse.
    """
    cfg = cfg or Experiment5Config()

    with FlightRecorder("experiment5_active_feedback") as flight:
        flight.log_metric("Protocol", "Active Feedback (Maxwell's Demon)")
        flight.log_metric("Temperature", cfg.temperature)
        flight.log_metric("Passive Limit (Tc)", "0.020 (from Exp 4E)")
        flight.log_metric("Logic", "Instantaneous Drag Veto")
        flight.log_metric("Drive Modulation", f"{cfg.g_ghost} ← {cfg.g_solid}")

        print(f"=== ACTIVE FEEDBACK TEST ===")
        print(f"Temperature: {cfg.temperature} (2.5× passive limit)")
        print(f"Control Logic: Force-dependent coupling modulation")
        print(f"Hypothesis: Information processing can entropy-dump thermal noise\n")

        # === INITIALIZE ===
        sim = LangevinVacuumChamber(
            cfg.grid_size,
            cfg.dx,
            cfg.dt,
            gamma=cfg.gamma,
            temperature=cfg.temperature,
        )

        rng = np.random.default_rng(seed)
        sim.phi = rng.normal(0, 0.001, cfg.grid_size)
        sim.phi_prev = np.copy(sim.phi)

        # Coupler geometry
        x_center = (cfg.grid_size / 2.0) * cfg.dx
        x1 = x_center - cfg.coupler_separation / 2
        x2 = x_center + cfg.coupler_separation / 2

        x_grid = np.arange(cfg.grid_size) * cfg.dx
        coupler1_profile = np.exp(-((x_grid - x1) ** 2) / (2 * cfg.coupler_width**2))
        coupler2_profile = np.exp(-((x_grid - x2) ** 2) / (2 * cfg.coupler_width**2))

        coupler1_profile /= np.sum(coupler1_profile) * cfg.dx
        coupler2_profile /= np.sum(coupler2_profile) * cfg.dx

        force_history = []
        coupling_state_history = []
        gain_history = []

        # === TIME EVOLUTION WITH FEEDBACK ===
        for step in range(cfg.total_steps):
            t = step * cfg.dt

            # === FEEDBACK LOGIC ===
            # Use previous timestep force as predictor (Markov approximation)
            # If system was dragging, reduce coupling to "decloak"
            # If system was thrusting, increase coupling to "grip"

            if len(sim.mirror_force) > 0:
                last_force = sim.mirror_force[-1]
            else:
                last_force = 0.0

            # Decision: Drag veto
            if last_force < cfg.force_threshold:
                # Dragging → suppress coupling (decloak)
                gain = cfg.feedback_gain_suppress
                state = 0  # Ghost mode
            else:
                # Thrusting → boost coupling (grip)
                gain = cfg.feedback_gain_boost
                state = 1  # Solid mode

            coupling_state_history.append(state)
            gain_history.append(gain)

            # === MODULATED FLOQUET DRIVE ===
            # Base drive (carrier wave)
            base_g0 = cfg.g_solid
            base_g1 = cfg.g_solid * 0.75  # Maintain ratio from 4E

            # Apply feedback gain
            g0_modulated = base_g0 * gain
            g1_modulated = base_g1 * gain

            # Time-dependent coupling
            g1_t = g0_modulated + g1_modulated * np.cos(cfg.omega * t)
            g2_t = g0_modulated + g1_modulated * np.cos(cfg.omega * t + cfg.phi)

            # Construct potential
            V = g1_t * coupler1_profile + g2_t * coupler2_profile

            # Step physics
            sim.step_damped(c=cfg.c, v_potential=V)
            force_history.append(sim.mirror_force[-1])

            # Progress
            if step % (cfg.period * 20) == 0 and step > 0:
                progress_pct = 100 * step / cfg.total_steps
                duty = np.mean(coupling_state_history[-1000:]) if len(coupling_state_history) > 1000 else 0
                print(f"  Progress: {progress_pct:.0f}% | Duty Cycle: {duty:.2f}")

        # === ANALYSIS ===
        transient_idx = int(cfg.total_steps * cfg.transient_fraction)
        force_arr = np.asarray(force_history)
        steady_force = force_arr[transient_idx:]

        net_thrust = float(np.mean(steady_force))
        std_dev = float(np.std(steady_force))
        std_err = std_dev / np.sqrt(len(steady_force))
        snr = abs(net_thrust / std_err) if std_err > 0 else 0.0

        # Duty cycle (fraction of time in "grip" mode)
        states = np.asarray(coupling_state_history)
        duty_cycle = float(np.mean(states))

        flight.log_metric("Net Thrust", net_thrust)
        flight.log_metric("SNR", snr)
        flight.log_metric("Duty Cycle (Grip)", duty_cycle)
        flight.log_metric("Std Deviation", std_dev)

        # Compare to passive baseline at this temperature
        # (In 4E, T=0.025 showed SNR~14, but T=0.02 showed SNR~0.5)
        # At T=0.05, passive would likely have SNR << 1

        if snr > 2.0:
            outcome = f"✓ DEMON SUCCESS (SNR={snr:.1f})"
            flight.log_metric("Outcome", "DEMON_SUCCESS")
        else:
            outcome = f"✗ DEMON FAILED (SNR={snr:.1f})"
            flight.log_metric("Outcome", "DEMON_FAILED")

        print(f"\n=== DEMON TEST RESULT ===")
        print(f"Net Thrust:  {net_thrust:+.3e}")
        print(f"SNR:         {snr:.2f}")
        print(f"Duty Cycle:  {duty_cycle:.2%} (grip mode)")
        print(f"Status:      {outcome}")

        # === VISUALIZATION ===
        fig = plt.figure(figsize=(12, 10))
        gs = fig.add_gridspec(3, 2, hspace=0.3)

        # Plot 1: Force time series (zoomed to steady state)
        ax1 = fig.add_subplot(gs[0, :])
        zoom_idx = max(0, len(force_arr) - 2000)
        ax1.plot(force_arr[zoom_idx:], linewidth=0.5, alpha=0.8)
        ax1.axhline(net_thrust, color="cyan", linestyle="--", label=f"Mean = {net_thrust:.2e}")
        ax1.axhline(0, color="gray", linestyle=":", alpha=0.5)
        ax1.set_title(f"Force with Active Feedback (T={cfg.temperature}, Last 2k Steps)")
        ax1.set_xlabel("Step")
        ax1.set_ylabel("Force")
        ax1.legend()
        ax1.grid(True, alpha=0.3)

        # Plot 2: Coupling state (demon decisions)
        ax2 = fig.add_subplot(gs[1, 0])
        states_zoom = states[zoom_idx:]
        ax2.fill_between(range(len(states_zoom)), 0, states_zoom, alpha=0.5, color="magenta", label="Grip Mode")
        ax2.set_title("Demon Coupling State (1=Grip, 0=Slip)")
        ax2.set_xlabel("Step")
        ax2.set_ylabel("State")
        ax2.set_ylim(-0.1, 1.1)
        ax2.legend()
        ax2.grid(True, alpha=0.3)

        # Plot 3: Duty cycle (running average)
        ax3 = fig.add_subplot(gs[1, 1])
        window = 500
        duty_running = np.convolve(states, np.ones(window) / window, mode="same")
        ax3.plot(duty_running, color="lime", linewidth=2)
        ax3.axhline(duty_cycle, color="white", linestyle="--", label=f"Mean = {duty_cycle:.2%}")
        ax3.set_title(f"Duty Cycle (Running Avg, Window={window})")
        ax3.set_xlabel("Step")
        ax3.set_ylabel("Grip Fraction")
        ax3.set_ylim(0, 1)
        ax3.legend()
        ax3.grid(True, alpha=0.3)

        # Plot 4: Force histogram
        ax4 = fig.add_subplot(gs[2, 0])
        ax4.hist(steady_force, bins=60, alpha=0.7, edgecolor="black")
        ax4.axvline(net_thrust, color="red", linestyle="--", linewidth=2, label="Mean")
        ax4.axvline(0, color="gray", linestyle=":", linewidth=2)
        ax4.set_title("Force Distribution (Steady State)")
        ax4.set_xlabel("Force")
        ax4.set_ylabel("Count")
        ax4.legend()
        ax4.grid(True, alpha=0.3)

        # Plot 5: Metrics summary
        ax5 = fig.add_subplot(gs[2, 1])
        ax5.axis("off")
        metric_text = f"""
        === DEMON TEST METRICS ===
        
        Temperature:      {cfg.temperature:.4f}
        Passive Limit:    0.020 (from 4E)
        Test/Limit:       {cfg.temperature/0.020:.1f}×
        
        Net Thrust:       {net_thrust:+.3e}
        SNR:              {snr:.2f}
        Duty Cycle:       {duty_cycle:.1%}
        
        Drive Modulation:
          Grip (1):       g={cfg.g_solid:.1f}
          Slip (0):       g={cfg.g_ghost:.1f}
        
        Status:           {outcome}
        """
        ax5.text(
            0.1,
            0.5,
            metric_text,
            fontsize=10,
            family="monospace",
            verticalalignment="center",
        )

        plt.tight_layout()
        flight.save_plot(fig, filename="visual_telemetry.png")
        plt.close(fig)

        return "COUNCIL_REPORT.md"
