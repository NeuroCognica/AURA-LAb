from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import matplotlib.pyplot as plt
import numpy as np

from flight_recorder.mission_logger import FlightRecorder


class FloquetLangevinChamber:
    """Floquet pump with FDT-compliant Langevin dynamics.
    
    Two delta scatterers at fixed positions with sinusoidal coupling:
        g₀(t) = g₀[1 + cos(Ωt)]
        g₁(t) = g₁[1 + cos(Ωt + φ)]
    
    Field equation: d²φ/dt² + γ∂φ/∂t - c²∂²φ/∂x² = -V(x,t)φ + ξ(t)
    with FDT: σ_noise = sqrt(2γkT/dt)
    """
    
    def __init__(
        self,
        nx: int,
        dx: float,
        dt: float,
        gamma: float,
        temperature: float,
        coupler_positions: tuple[float, float],
        coupler_widths: tuple[float, float],
    ):
        self.nx = nx
        self.dx = dx
        self.dt = dt
        self.gamma = gamma
        self.temp = temperature
        
        self.x = np.arange(nx) * dx
        self.phi = np.zeros(nx)
        self.phi_prev = np.zeros(nx)
        self.phi_next = np.zeros(nx)
        
        # Coupler spatial profiles (Gaussian delta approximations)
        x0, x1 = coupler_positions
        w0, w1 = coupler_widths
        self.coupler0_profile = np.exp(-((self.x - x0) ** 2) / (2 * w0**2))
        self.coupler1_profile = np.exp(-((self.x - x1) ** 2) / (2 * w1**2))
        
        # FDT noise scale
        if self.temp > 0 and self.gamma > 0:
            self.noise_scale = float(np.sqrt(2 * self.gamma * self.temp / self.dt))
        else:
            self.noise_scale = 0.0
        
        # Telemetry
        self.force_history = []
        self.time_history = []
    
    def step(self, *, t: float, c: float, g0: float, g1: float) -> None:
        """Advance field one timestep with time-dependent Floquet coupling."""
        # 1. Laplacian
        laplacian = (
            np.roll(self.phi, -1) - 2 * self.phi + np.roll(self.phi, 1)
        ) / (self.dx**2)
        
        # 2. Time-dependent coupling potential
        V = g0 * self.coupler0_profile + g1 * self.coupler1_profile
        interaction = V * self.phi
        
        # 3. Thermal noise (FDT-compliant)
        noise = np.zeros(self.nx)
        if self.noise_scale > 0:
            noise = np.random.normal(0, self.noise_scale, self.nx)
        
        # 4. Damped Verlet integration
        forces = (c**2) * laplacian - interaction + noise
        
        denom = 1.0 + (self.gamma * self.dt / 2.0)
        term1 = 2.0 * self.phi
        term2 = self.phi_prev * (1.0 - (self.gamma * self.dt / 2.0))
        term3 = (self.dt**2) * forces
        
        self.phi_next = (term1 - term2 + term3) / denom
        
        # Boundary conditions
        self.phi_next[0] = 0.0
        self.phi_next[-1] = 0.0
        
        # 5. Calculate force (back-reaction from both couplers)
        grad_V = np.gradient(V, self.dx)
        force = -float(np.sum((self.phi**2) * grad_V) * self.dx)
        self.force_history.append(force)
        self.time_history.append(t)
        
        # Cycle buffers
        self.phi_prev = np.copy(self.phi)
        self.phi = np.copy(self.phi_next)


@dataclass(frozen=True)
class Experiment4CConfig:
    # Grid parameters
    grid_size: int = 1000
    dx: float = 0.1
    dt: float = 0.02
    c: float = 1.0
    
    # Damping
    gamma: float = 0.01
    
    # Floquet drive parameters (from Experiment 3)
    omega: float = 1.0
    g0_amp: float = 2.0
    g1_amp: float = 1.5
    
    # Coupler geometry
    coupler_separation: float = 20.0  # Distance between barriers
    coupler_width: float = 2.0
    
    # Time evolution
    n_cycles: int = 20  # Number of drive cycles
    transient_cycles: int = 5  # Cycles to skip for transient decay
    
    # Temperature sweep
    temp_min: float = 0.0
    temp_max: float = 0.05
    temp_steps: int = 6
    
    # Phase sweep (for φ-reversal test)
    phi_test_values: tuple[float, ...] = (0.0, np.pi/2, -np.pi/2)
    
    # Ensemble statistics
    ensemble_size: int = 20
    
    @property
    def total_time(self) -> float:
        return (2 * np.pi / self.omega) * self.n_cycles
    
    @property
    def n_steps(self) -> int:
        return int(self.total_time / self.dt)
    
    @property
    def lock_in_start_time(self) -> float:
        return (2 * np.pi / self.omega) * self.transient_cycles


def _compute_lock_in_amplitude(
    force: np.ndarray,
    time: np.ndarray,
    omega: float,
    transient_time: float,
    phase_offset: float = 0.0,
) -> tuple[float, float]:
    """Extract coherent pump current via lock-in detection.
    
    Returns (I_sin, I_cos) components:
        I_sin = (2/T) * integral(F(t) * sin(Ωt + θ))
        I_cos = (2/T) * integral(F(t) * cos(Ωt + θ))
    """
    # Filter out transient
    mask = time >= transient_time
    t_filtered = time[mask]
    f_filtered = force[mask]
    
    if len(t_filtered) == 0:
        return 0.0, 0.0
    
    T_integration = t_filtered[-1] - t_filtered[0]
    if T_integration <= 0:
        return 0.0, 0.0
    
    # Lock-in reference signals
    ref_sin = np.sin(omega * t_filtered + phase_offset)
    ref_cos = np.cos(omega * t_filtered + phase_offset)
    
    # Integrate
    integrate = getattr(np, "trapezoid", None) or getattr(np, "trapz")
    I_sin = (2.0 / T_integration) * float(integrate(f_filtered * ref_sin, t_filtered))
    I_cos = (2.0 / T_integration) * float(integrate(f_filtered * ref_cos, t_filtered))
    
    return I_sin, I_cos


def run(*, seed: int = 42, cfg: Optional[Experiment4CConfig] = None) -> str:
    """Floquet pump under Langevin dynamics with lock-in detection.
    
    Tests whether φ-reversal sign flip survives thermal decoherence
    when using proper phase-sensitive measurement.
    """
    cfg = cfg or Experiment4CConfig()
    
    with FlightRecorder("experiment4c_floquet_langevin") as flight:
        flight.log_metric("Test Protocol", "Floquet + Langevin + Lock-in")
        flight.log_metric("Drive Frequency (Ω)", cfg.omega)
        flight.log_metric("Damping (γ)", cfg.gamma)
        flight.log_metric("Cycles", cfg.n_cycles)
        flight.log_metric("Transient Skip", cfg.transient_cycles)
        flight.log_metric("Ensemble Size", cfg.ensemble_size)
        flight.log_metric("Temp Range", f"{cfg.temp_min} - {cfg.temp_max}")
        
        print(f"Floquet Lock-in Test: {cfg.n_cycles} cycles, {cfg.ensemble_size} seeds per (T,φ)")
        
        temp_levels = np.linspace(cfg.temp_min, cfg.temp_max, cfg.temp_steps)
        
        # Results structure: results[temp_idx][phi_idx] = (mean, std, ensemble_data)
        results = {}
        
        # Coupler positions (centered, separated)
        x_center = (cfg.grid_size / 2.0) * cfg.dx
        coupler_positions = (
            x_center - cfg.coupler_separation / 2,
            x_center + cfg.coupler_separation / 2,
        )
        coupler_widths = (cfg.coupler_width, cfg.coupler_width)
        
        for i_temp, temp in enumerate(temp_levels):
            print(f"\n=== Temperature {temp:.4f} ===")
            results[temp] = {}
            
            for phi in cfg.phi_test_values:
                ensemble_lock_in = []
                
                for i_seed in range(cfg.ensemble_size):
                    # Initialize chamber
                    sim = FloquetLangevinChamber(
                        nx=cfg.grid_size,
                        dx=cfg.dx,
                        dt=cfg.dt,
                        gamma=cfg.gamma,
                        temperature=float(temp),
                        coupler_positions=coupler_positions,
                        coupler_widths=coupler_widths,
                    )
                    
                    # Seed vacuum state (ensure non-negative seed)
                    phi_hash = abs(int(phi * 1000)) % 10000
                    rng = np.random.default_rng(seed + i_temp * 1000 + phi_hash + i_seed)
                    sim.phi = rng.normal(0, 0.001, cfg.grid_size)
                    sim.phi_prev = np.copy(sim.phi)
                    
                    # Time evolution with Floquet drive
                    for step in range(cfg.n_steps):
                        t = step * cfg.dt
                        
                        # Sinusoidal coupling modulation
                        g0_t = cfg.g0_amp * (1.0 + np.cos(cfg.omega * t))
                        g1_t = cfg.g1_amp * (1.0 + np.cos(cfg.omega * t + phi))
                        
                        sim.step(t=t, c=cfg.c, g0=g0_t, g1=g1_t)
                    
                    # Lock-in detection (extract coherent component at Ω)
                    force_arr = np.asarray(sim.force_history)
                    time_arr = np.asarray(sim.time_history)
                    
                    I_sin, I_cos = _compute_lock_in_amplitude(
                        force_arr,
                        time_arr,
                        cfg.omega,
                        cfg.lock_in_start_time,
                        phase_offset=0.0,
                    )
                    
                    # Magnitude of lock-in signal
                    lock_in_amp = np.sqrt(I_sin**2 + I_cos**2)
                    # Use signed amplitude (I_sin as proxy for pump direction)
                    signed_amp = I_sin
                    
                    ensemble_lock_in.append(signed_amp)
                
                # Statistics
                mean_lock_in = float(np.mean(ensemble_lock_in))
                std_lock_in = float(np.std(ensemble_lock_in))
                results[temp][phi] = (mean_lock_in, std_lock_in, ensemble_lock_in)
                
                snr = abs(mean_lock_in / std_lock_in) if std_lock_in > 0 else np.inf
                print(f"  φ={phi:+.3f}: I_lock = {mean_lock_in:+.3e} ± {std_lock_in:.2e} [SNR={snr:.1f}]")
        
        # === ANALYSIS: φ-Reversal Test ===
        print("\n=== φ-REVERSAL TEST ===")
        phi_plus = np.pi / 2
        phi_minus = -np.pi / 2
        phi_zero = 0.0
        
        reversal_test_passed = []
        
        for temp in temp_levels:
            mean_plus, std_plus, _ = results[temp][phi_plus]
            mean_minus, std_minus, _ = results[temp][phi_minus]
            mean_zero, std_zero, _ = results[temp][phi_zero]
            
            # Test: I(+φ) and I(-φ) should have opposite signs
            sign_flip = (mean_plus * mean_minus) < 0
            # Test: I(0) should be small compared to I(±φ)
            zero_suppressed = abs(mean_zero) < 0.5 * max(abs(mean_plus), abs(mean_minus))
            
            test_pass = sign_flip and zero_suppressed
            reversal_test_passed.append(test_pass)
            
            status = "✓ PASS" if test_pass else "✗ FAIL"
            print(f"  T={temp:.4f}: {status} | I(+φ)={mean_plus:+.2e}, I(-φ)={mean_minus:+.2e}, I(0)={mean_zero:+.2e}")
        
        # Critical temperature = first temp where reversal test fails
        critical_temp = None
        for temp, passed in zip(temp_levels, reversal_test_passed, strict=False):
            if not passed and temp > 0:
                critical_temp = float(temp)
                break
        
        if critical_temp is None:
            tc_str = f"> {cfg.temp_max:.4f} (Robust)"
            robustness = "PASS"
        else:
            tc_str = f"{critical_temp:.4f} (Reversal Lost)"
            robustness = f"FAIL at T={critical_temp:.4f}"
        
        flight.log_metric("Critical Temp (Tc)", tc_str)
        flight.log_metric("Thermal Robustness", robustness)
        flight.log_metric("φ-Reversal at T=0", "PASS" if reversal_test_passed[0] else "FAIL")
        
        # Baseline metrics
        baseline_lock_in, baseline_std, _ = results[temp_levels[0]][phi_plus]
        baseline_snr = abs(baseline_lock_in / baseline_std) if baseline_std > 0 else np.inf
        flight.log_metric("Baseline Lock-in (T=0, φ=π/2)", baseline_lock_in)
        flight.log_metric("Baseline SNR", baseline_snr)
        
        # === VISUALIZATION ===
        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 10))
        
        # Plot 1: Lock-in amplitude vs Temperature (φ sweep)
        for phi in cfg.phi_test_values:
            means = [results[T][phi][0] for T in temp_levels]
            stds = [results[T][phi][1] for T in temp_levels]
            label = f"φ = {phi:.3f} ({phi*180/np.pi:.0f}°)"
            ax1.errorbar(temp_levels, means, yerr=stds, fmt="-o", capsize=3, label=label)
        
        ax1.axhline(0, color="gray", linestyle="--", alpha=0.3)
        if critical_temp is not None:
            ax1.axvline(critical_temp, color="red", linestyle="--", alpha=0.5, label=f"Tc={critical_temp:.4f}")
        ax1.set_title(f"Floquet Pump Lock-in vs Temperature (γ={cfg.gamma}, Ω={cfg.omega})")
        ax1.set_xlabel("Temperature (Simulation Units)")
        ax1.set_ylabel("Lock-in Amplitude I(Ω)")
        ax1.legend()
        ax1.grid(True, alpha=0.3)
        
        # Plot 2: φ-Reversal Signature vs Temperature
        asymmetry = []
        asymmetry_err = []
        for temp in temp_levels:
            mean_plus, std_plus, _ = results[temp][phi_plus]
            mean_minus, std_minus, _ = results[temp][phi_minus]
            
            delta = mean_plus - mean_minus
            delta_err = np.sqrt(std_plus**2 + std_minus**2)
            
            asymmetry.append(delta)
            asymmetry_err.append(delta_err)
        
        ax2.errorbar(temp_levels, asymmetry, yerr=asymmetry_err, fmt="-s", capsize=3, color="cyan", label="I(+φ) - I(-φ)")
        ax2.axhline(0, color="gray", linestyle="--", alpha=0.3)
        ax2.set_title("φ-Reversal Asymmetry vs Temperature")
        ax2.set_xlabel("Temperature")
        ax2.set_ylabel("ΔI = I(+π/2) - I(-π/2)")
        ax2.legend()
        ax2.grid(True, alpha=0.3)
        
        plt.tight_layout()
        flight.save_plot(fig, filename="visual_telemetry.png")
        plt.close(fig)
        
        return "COUNCIL_REPORT.md"
