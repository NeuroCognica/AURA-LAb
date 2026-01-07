from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Literal

import matplotlib.pyplot as plt
import numpy as np

from core.vacuum_chamber import VacuumChamber
from flight_recorder.mission_logger import FlightRecorder


class LangevinVacuumChamber(VacuumChamber):
    """High-fidelity Langevin chamber with energy accounting."""
    
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

    def step_damped(
        self,
        *,
        c: float,
        v_potential: np.ndarray,
        v_potential_prev: Optional[np.ndarray] = None,
    ) -> float:
        """Advance field and return switching work done.
        
        Returns:
            Switching work if v_potential changed, else 0.0
        """
        # Calculate switching work if potential changed
        switching_work = 0.0
        if v_potential_prev is not None:
            # Work done by changing potential while field is present
            # W = integral of phi^2 * (V_new - V_old) * dx
            delta_V = v_potential - v_potential_prev
            switching_work = float(0.5 * np.sum((self.phi**2) * delta_V) * self.dx)

        # Physics step
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

        return switching_work


@dataclass(frozen=True)
class Experiment5BConfig:
    # Grid parameters
    grid_size: int = 1000
    dx: float = 0.1
    dt: float = 0.02
    c: float = 1.0

    # Physics
    gamma: float = 0.001
    temperature: float = 0.05  # High temp from Exp 5

    # Drive
    omega: float = 1.0
    phi: float = np.pi / 2
    g_solid: float = 5.0
    g_ghost: float = 0.1

    # Integration
    n_cycles: int = 200

    # Coupler geometry
    coupler_separation: float = 20.0
    coupler_width: float = 1.0

    # Control modes
    control_modes: tuple[str, ...] = (
        "informed",      # Original demon (force-conditioned)
        "random",        # Random switching (same duty cycle)
        "delayed",       # Delayed demon (½ period lag)
        "zero_bath",     # No thermal noise
        "blind",         # Fixed work injection (no conditioning)
    )

    @property
    def period(self) -> int:
        return int(2 * np.pi / (self.omega * self.dt))

    @property
    def total_steps(self) -> int:
        return self.period * self.n_cycles

    @property
    def transient_fraction(self) -> float:
        return 0.2


def _run_control_mode(
    mode: str,
    cfg: Experiment5BConfig,
    seed: int,
    coupler1_profile: np.ndarray,
    coupler2_profile: np.ndarray,
    reference_duty_cycle: Optional[float] = None,
) -> tuple[float, float, float, float, list[int]]:
    """Run single control mode and return metrics.
    
    Returns:
        (net_impulse, switching_work_total, snr, duty_cycle, state_history)
    """
    sim = LangevinVacuumChamber(
        cfg.grid_size,
        cfg.dx,
        cfg.dt,
        gamma=cfg.gamma,
        temperature=cfg.temperature if mode != "zero_bath" else 0.0,
    )

    rng = np.random.default_rng(seed)
    sim.phi = rng.normal(0, 0.001, cfg.grid_size)
    sim.phi_prev = np.copy(sim.phi)

    force_history = []
    state_history = []
    switching_work_total = 0.0

    # For delayed demon, store force history
    force_buffer = []
    delay_steps = cfg.period // 2 if mode == "delayed" else 0

    # For random demon, pre-generate states matching reference duty
    if mode == "random" and reference_duty_cycle is not None:
        random_states = rng.random(cfg.total_steps) < reference_duty_cycle
    else:
        random_states = None

    v_potential_prev = None

    for step in range(cfg.total_steps):
        t = step * cfg.dt

        # === CONTROL LOGIC (MODE-DEPENDENT) ===
        if mode == "informed":
            # Original demon: force-conditioned switching
            last_force = sim.mirror_force[-1] if len(sim.mirror_force) > 0 else 0.0
            state = 1 if last_force >= 0 else 0

        elif mode == "random":
            # Random switching with matched duty cycle
            state = int(random_states[step])

        elif mode == "delayed":
            # Delayed demon: use force from delay_steps ago
            force_buffer.append(
                sim.mirror_force[-1] if len(sim.mirror_force) > 0 else 0.0
            )
            if len(force_buffer) > delay_steps:
                delayed_force = force_buffer[-delay_steps]
                state = 1 if delayed_force >= 0 else 0
            else:
                state = 1  # Default until buffer fills

        elif mode == "zero_bath":
            # Same as informed but no thermal noise (T=0 in init)
            last_force = sim.mirror_force[-1] if len(sim.mirror_force) > 0 else 0.0
            state = 1 if last_force >= 0 else 0

        elif mode == "blind":
            # Fixed periodic switching (no conditioning)
            # Inject same total work but blindly
            state = 1 if (step // cfg.period) % 2 == 0 else 0

        else:
            raise ValueError(f"Unknown mode: {mode}")

        state_history.append(state)

        # === MODULATED DRIVE ===
        gain = 1.0 if state == 1 else 0.1
        g0_modulated = cfg.g_solid * gain
        g1_modulated = cfg.g_solid * 0.75 * gain

        g1_t = g0_modulated + g1_modulated * np.cos(cfg.omega * t)
        g2_t = g0_modulated + g1_modulated * np.cos(cfg.omega * t + cfg.phi)

        v_potential = g1_t * coupler1_profile + g2_t * coupler2_profile

        # === STEP WITH SWITCHING WORK ACCOUNTING ===
        work_this_step = sim.step_damped(
            c=cfg.c,
            v_potential=v_potential,
            v_potential_prev=v_potential_prev,
        )
        switching_work_total += work_this_step

        force_history.append(sim.mirror_force[-1])
        v_potential_prev = np.copy(v_potential)

    # === ANALYSIS ===
    transient_idx = int(cfg.total_steps * cfg.transient_fraction)
    force_arr = np.asarray(force_history)
    steady_force = force_arr[transient_idx:]

    net_impulse = float(np.mean(steady_force) * cfg.dt * len(steady_force))
    std_err = float(np.std(steady_force) / np.sqrt(len(steady_force)))
    snr = abs(net_impulse / (std_err * cfg.dt * len(steady_force))) if std_err > 0 else 0.0

    states = np.asarray(state_history)
    duty_cycle = float(np.mean(states))

    return net_impulse, switching_work_total, snr, duty_cycle, state_history


def run(*, seed: int = 42, cfg: Optional[Experiment5BConfig] = None) -> str:
    """Control experiment suite to prosecute the demon hypothesis.
    
    Tests:
    1. Informed (original demon)
    2. Random (same duty cycle, uninformed)
    3. Delayed (decorrelated timing)
    4. Zero bath (no thermal noise)
    5. Blind (fixed work injection)
    
    Critical test: Does informed switching show advantage AFTER
    accounting for switching work?
    """
    cfg = cfg or Experiment5BConfig()

    with FlightRecorder("experiment5b_demon_controls") as flight:
        flight.log_metric("Protocol", "Demon Control Suite")
        flight.log_metric("Temperature", cfg.temperature)
        flight.log_metric("Control Modes", len(cfg.control_modes))

        print(f"=== DEMON CONTROL SUITE ===")
        print(f"Prosecuting the parametric actuation hypothesis")
        print(f"Temperature: {cfg.temperature}")
        print(f"Testing {len(cfg.control_modes)} control modes\n")

        # Setup coupler geometry (shared across all modes)
        x_center = (cfg.grid_size / 2.0) * cfg.dx
        x1 = x_center - cfg.coupler_separation / 2
        x2 = x_center + cfg.coupler_separation / 2

        x_grid = np.arange(cfg.grid_size) * cfg.dx
        coupler1_profile = np.exp(-((x_grid - x1) ** 2) / (2 * cfg.coupler_width**2))
        coupler2_profile = np.exp(-((x_grid - x2) ** 2) / (2 * cfg.coupler_width**2))

        coupler1_profile /= np.sum(coupler1_profile) * cfg.dx
        coupler2_profile /= np.sum(coupler2_profile) * cfg.dx

        # === RUN ALL CONTROL MODES ===
        results = {}

        # First pass: run informed to get reference duty cycle
        print("Running INFORMED (original demon)...")
        impulse, work, snr, duty, states = _run_control_mode(
            "informed", cfg, seed, coupler1_profile, coupler2_profile
        )
        results["informed"] = (impulse, work, snr, duty)
        reference_duty = duty
        print(f"  Impulse: {impulse:+.2e}, Work: {work:.2e}, SNR: {snr:.1f}, Duty: {duty:.1%}\n")

        # Run other modes
        for mode in cfg.control_modes:
            if mode == "informed":
                continue  # Already ran

            print(f"Running {mode.upper()}...")
            impulse, work, snr, duty, states = _run_control_mode(
                mode,
                cfg,
                seed,
                coupler1_profile,
                coupler2_profile,
                reference_duty_cycle=reference_duty,
            )
            results[mode] = (impulse, work, snr, duty)
            print(f"  Impulse: {impulse:+.2e}, Work: {work:.2e}, SNR: {snr:.1f}, Duty: {duty:.1%}\n")

        # === CRITICAL ANALYSIS ===
        print("=== CRITICAL ANALYSIS ===\n")

        # Test 1: Random demon comparison
        imp_informed, work_informed, snr_informed, _ = results["informed"]
        imp_random, work_random, snr_random, _ = results["random"]

        ratio_impulse_random = imp_informed / imp_random if imp_random != 0 else np.inf
        ratio_work_random = work_informed / work_random if work_random != 0 else 1.0

        print(f"Test 1: INFORMED vs RANDOM (same duty cycle)")
        print(f"  Impulse ratio:  {ratio_impulse_random:.2f}× (informed/random)")
        print(f"  Work ratio:     {ratio_work_random:.2f}× (informed/random)")

        if ratio_impulse_random < 1.5:
            verdict_random = "✗ ACTUATOR (information doesn't help)"
        else:
            verdict_random = "✓ POTENTIAL DEMON (information adds value)"
        print(f"  Verdict: {verdict_random}\n")

        # Test 2: Efficiency (impulse per unit work)
        eff_informed = imp_informed / work_informed if work_informed > 0 else np.inf
        eff_random = imp_random / work_random if work_random > 0 else np.inf
        eff_blind = results["blind"][0] / results["blind"][1] if results["blind"][1] > 0 else np.inf

        print(f"Test 2: EFFICIENCY (impulse / switching work)")
        print(f"  Informed:  {eff_informed:.3e}")
        print(f"  Random:    {eff_random:.3e}")
        print(f"  Blind:     {eff_blind:.3e}")

        if eff_informed > eff_random * 1.2:
            verdict_eff = "✓ Information improves efficiency"
        else:
            verdict_eff = "✗ No efficiency advantage"
        print(f"  Verdict: {verdict_eff}\n")

        # Test 3: Delayed demon
        imp_delayed = results["delayed"][0]
        ratio_delayed = imp_informed / imp_delayed if imp_delayed != 0 else np.inf

        print(f"Test 3: DELAYED DEMON (decorrelated timing)")
        print(f"  Impulse ratio:  {ratio_delayed:.2f}× (informed/delayed)")

        if ratio_delayed > 2.0:
            verdict_delayed = "✓ Timing matters (genuine correlation)"
        else:
            verdict_delayed = "✗ Insensitive to delay (resonance artifact)"
        print(f"  Verdict: {verdict_delayed}\n")

        # Test 4: Zero bath
        imp_zero = results["zero_bath"][0]
        ratio_zero = imp_informed / imp_zero if imp_zero != 0 else np.inf

        print(f"Test 4: ZERO BATH (no thermal noise)")
        print(f"  Impulse ratio:  {ratio_zero:.2f}× (T={cfg.temperature}/T=0)")

        if abs(imp_zero) < abs(imp_informed) * 0.1:
            verdict_zero = "✓ Effect requires thermal bath"
        else:
            verdict_zero = "✗ Hidden motor (works without noise)"
        print(f"  Verdict: {verdict_zero}\n")

        # === FINAL VERDICT ===
        tests_passed = sum([
            "DEMON" in verdict_random,
            "improves" in verdict_eff,
            "matters" in verdict_delayed,
            "requires" in verdict_zero,
        ])

        print(f"=== FINAL VERDICT ===")
        print(f"Tests passed: {tests_passed}/4\n")

        if tests_passed >= 3:
            final_verdict = "✓ DEMON HYPOTHESIS SURVIVES (with caveats)"
            outcome = "DEMON_VALIDATED"
        elif tests_passed >= 2:
            final_verdict = "⚠ MIXED RESULTS (partial demon behavior)"
            outcome = "MIXED"
        else:
            final_verdict = "✗ PARAMETRIC ACTUATOR (demon hypothesis rejected)"
            outcome = "ACTUATOR"

        print(final_verdict)

        flight.log_metric("Final Verdict", final_verdict)
        flight.log_metric("Outcome", outcome)
        flight.log_metric("Tests Passed", f"{tests_passed}/4")

        # Log all results
        for mode, (imp, work, snr, duty) in results.items():
            flight.log_metric(f"{mode}_impulse", imp)
            flight.log_metric(f"{mode}_work", work)
            flight.log_metric(f"{mode}_snr", snr)
            flight.log_metric(f"{mode}_duty", duty)
            flight.log_metric(f"{mode}_efficiency", imp / work if work > 0 else 0)

        # === VISUALIZATION ===
        fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=(14, 10))

        modes = list(results.keys())
        impulses = [results[m][0] for m in modes]
        works = [results[m][1] for m in modes]
        snrs = [results[m][2] for m in modes]
        efficiencies = [results[m][0] / results[m][1] if results[m][1] > 0 else 0 for m in modes]

        # Plot 1: Impulse comparison
        colors = ['cyan', 'orange', 'green', 'purple', 'red']
        ax1.bar(modes, impulses, color=colors[:len(modes)], alpha=0.7)
        ax1.set_ylabel("Net Impulse")
        ax1.set_title("Impulse by Control Mode")
        ax1.tick_params(axis='x', rotation=45)
        ax1.axhline(0, color='gray', linestyle='--', alpha=0.5)
        ax1.grid(True, alpha=0.3)

        # Plot 2: Switching work
        ax2.bar(modes, works, color=colors[:len(modes)], alpha=0.7)
        ax2.set_ylabel("Total Switching Work")
        ax2.set_title("Energy Cost by Control Mode")
        ax2.tick_params(axis='x', rotation=45)
        ax2.grid(True, alpha=0.3)

        # Plot 3: Efficiency (impulse/work)
        ax3.bar(modes, efficiencies, color=colors[:len(modes)], alpha=0.7)
        ax3.set_ylabel("Efficiency (Impulse/Work)")
        ax3.set_title("Control Efficiency")
        ax3.tick_params(axis='x', rotation=45)
        ax3.grid(True, alpha=0.3)

        # Plot 4: SNR comparison
        ax4.bar(modes, snrs, color=colors[:len(modes)], alpha=0.7)
        ax4.set_ylabel("SNR")
        ax4.set_title("Signal-to-Noise Ratio")
        ax4.tick_params(axis='x', rotation=45)
        ax4.axhline(2.0, color='red', linestyle='--', label='Detection Threshold')
        ax4.legend()
        ax4.grid(True, alpha=0.3)

        plt.tight_layout()
        flight.save_plot(fig, filename="visual_telemetry.png")
        plt.close(fig)

        return "COUNCIL_REPORT.md"
