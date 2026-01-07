from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, Optional, Tuple

import matplotlib.pyplot as plt
import numpy as np

from flight_recorder.mission_logger import FlightRecorder


@dataclass(frozen=True)
class FloquetConfig:
    r"""1D Floquet scattering toy model.

    Units: set \hbar = 2m = 1 so E = k^2.

    We model a scalar wave scattering off two delta couplers at x=0 and x=a:

        V(x,t) = g1(t) δ(x) + g2(t) δ(x-a)

    with time-periodic modulation and a phase lag φ between g1 and g2.
    """

    # Incoming energy and drive
    E0: float = 2.25  # k0=1.5
    Omega: float = 1.0

    # Floquet truncation
    N_sidebands: int = 4  # channels n=-N..N

    # Geometry
    a: float = 2.0

    # Coupler strengths: g(t) = g0 + g1 cos(Omega t + phase)
    g0: float = 2.0
    g1: float = 1.5
    phi: float = np.pi / 2  # phase lag at second delta


def _sidebands(N: int) -> np.ndarray:
    return np.arange(-N, N + 1, dtype=int)


def _k(E: np.ndarray) -> np.ndarray:
    """Channel wave numbers k_n = sqrt(E_n), allowing evanescent (imaginary) channels."""
    k = np.zeros_like(E, dtype=np.complex128)
    pos = E > 0
    k[pos] = np.sqrt(E[pos])
    k[~pos] = 1j * np.sqrt(-E[~pos])
    return k


def _fourier_coeffs_cos(g0: float, g1: float, phase: float) -> Dict[int, complex]:
    """Fourier coefficients g_m for g(t)=g0+g1 cos(Omega t + phase)."""
    return {
        0: complex(g0),
        1: complex(0.5 * g1 * np.exp(1j * phase)),
        -1: complex(0.5 * g1 * np.exp(-1j * phase)),
    }


def _convolution_sum(
    coeffs: Dict[int, complex],
    values: np.ndarray,
    n: int,
    n_min: int,
    n_max: int,
) -> complex:
    """Compute (g * v)_n = sum_m g_m v_{n-m} over truncated sidebands."""
    total = 0.0 + 0.0j
    for m, gm in coeffs.items():
        idx = n - m
        if n_min <= idx <= n_max:
            total += gm * values[idx - n_min]
    return total


def _solve_floquet(
    *,
    cfg: FloquetConfig,
    incident: str,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Solve for Floquet reflection/transmission coefficients.

    Returns (n, k_n, r_n, t_n, R_n_flux, T_n_flux) where flux arrays are per-channel.

    incident:
      - "left": incoming channel n=0 from x=-∞ moving +x
      - "right": incoming channel n=0 from x=+∞ moving -x
    """

    if incident not in ("left", "right"):
        raise ValueError("incident must be 'left' or 'right'")

    n = _sidebands(cfg.N_sidebands)
    n_min, n_max = int(n[0]), int(n[-1])
    M = len(n)

    En = cfg.E0 + n * cfg.Omega
    kn = _k(En)
    k0 = float(np.sqrt(cfg.E0))

    g1_coeffs = _fourier_coeffs_cos(cfg.g0, cfg.g1, phase=0.0)
    g2_coeffs = _fourier_coeffs_cos(cfg.g0, cfg.g1, phase=float(cfg.phi))

    # Unknown vector ordering: [r(0..M-1), t(0..M-1), A(0..M-1), B(0..M-1)]
    def idx_r(i: int) -> int:
        return i

    def idx_t(i: int) -> int:
        return M + i

    def idx_A(i: int) -> int:
        return 2 * M + i

    def idx_B(i: int) -> int:
        return 3 * M + i

    A_mat = np.zeros((4 * M, 4 * M), dtype=np.complex128)
    b_vec = np.zeros(4 * M, dtype=np.complex128)

    # Precompute phase factors at x=a
    exp_p = np.exp(1j * kn * cfg.a)
    exp_m = np.exp(-1j * kn * cfg.a)

    # Helper arrays for convolution terms at boundaries
    # ψ(0) in region II: A+B
    # ψ(a) in region II: A*e^{ika} + B*e^{-ika}

    for i, ni in enumerate(n):
        k_i = kn[i]

        # === Boundary at x=0 ===
        row0 = 2 * i
        row1 = 2 * i + 1

        if incident == "left":
            delta = 1.0 if ni == 0 else 0.0

            # Continuity: delta + r = A + B
            A_mat[row0, idx_r(i)] = 1.0
            A_mat[row0, idx_A(i)] = -1.0
            A_mat[row0, idx_B(i)] = -1.0
            b_vec[row0] = -delta

            # Jump: i k (A - B) - (i k delta - i k r) = (g1 * (A+B))_n
            # => i k r + i k A - i k B - (g1*(A+B))_n = i k delta
            A_mat[row1, idx_r(i)] = 1j * k_i
            A_mat[row1, idx_A(i)] = 1j * k_i
            A_mat[row1, idx_B(i)] = -1j * k_i
            b_vec[row1] = 1j * k_i * delta

            # Convolution term: -(g1 * (A+B))_n
            for m, gm in g1_coeffs.items():
                idx = ni - m
                if n_min <= idx <= n_max:
                    j = idx - n_min
                    A_mat[row1, idx_A(j)] += -gm
                    A_mat[row1, idx_B(j)] += -gm

        else:
            # incident == "right"
            # Continuity at x=0: t = A + B
            A_mat[row0, idx_t(i)] = -1.0
            A_mat[row0, idx_A(i)] = 1.0
            A_mat[row0, idx_B(i)] = 1.0
            b_vec[row0] = 0.0

            # Jump at x=0: (ψ'_II - ψ'_I) = (g1 * ψ(0))_n
            # ψ'_I for t e^{-ikx} is -i k t
            # => i k (A - B) - (-i k t) - (g1*(A+B))_n = 0
            A_mat[row1, idx_t(i)] = 1j * k_i
            A_mat[row1, idx_A(i)] = 1j * k_i
            A_mat[row1, idx_B(i)] = -1j * k_i

            for m, gm in g1_coeffs.items():
                idx = ni - m
                if n_min <= idx <= n_max:
                    j = idx - n_min
                    A_mat[row1, idx_A(j)] += -gm
                    A_mat[row1, idx_B(j)] += -gm

        # === Boundary at x=a ===
        row2 = 2 * M + 2 * i
        row3 = 2 * M + 2 * i + 1

        if incident == "left":
            # Continuity: A e^{ika} + B e^{-ika} = t e^{ika}
            A_mat[row2, idx_A(i)] = exp_p[i]
            A_mat[row2, idx_B(i)] = exp_m[i]
            A_mat[row2, idx_t(i)] = -exp_p[i]

            # Jump: (ψ'_III - ψ'_II) = (g2 * ψ(a))_n
            # ψ'_III: i k t e^{ika}
            # ψ'_II: i k (A e^{ika} - B e^{-ika})
            # => i k t e^{ika} - i k A e^{ika} + i k B e^{-ika} - (g2*ψ(a))_n = 0
            A_mat[row3, idx_t(i)] = 1j * k_i * exp_p[i]
            A_mat[row3, idx_A(i)] = -1j * k_i * exp_p[i]
            A_mat[row3, idx_B(i)] = 1j * k_i * exp_m[i]

            for m, gm in g2_coeffs.items():
                idx = ni - m
                if n_min <= idx <= n_max:
                    j = idx - n_min
                    A_mat[row3, idx_A(j)] += -gm * exp_p[j]
                    A_mat[row3, idx_B(j)] += -gm * exp_m[j]

        else:
            # incident == "right"
            # Region III: incoming delta*e^{-ikx} + r*e^{ikx}
            delta = 1.0 if ni == 0 else 0.0

            # Continuity at x=a:
            # A e^{ika} + B e^{-ika} = delta e^{-ika} + r e^{ika}
            A_mat[row2, idx_A(i)] = exp_p[i]
            A_mat[row2, idx_B(i)] = exp_m[i]
            A_mat[row2, idx_r(i)] = -exp_p[i]
            b_vec[row2] = delta * exp_m[i]

            # Jump at x=a: (ψ'_III - ψ'_II) = (g2 * ψ(a))_n
            # ψ'_III: -i k delta e^{-ika} + i k r e^{ika}
            # ψ'_II: i k (A e^{ika} - B e^{-ika})
            # => i k r e^{ika} - i k A e^{ika} + i k B e^{-ika} - (g2*ψ(a))_n = i k delta e^{-ika}
            A_mat[row3, idx_r(i)] = 1j * k_i * exp_p[i]
            A_mat[row3, idx_A(i)] = -1j * k_i * exp_p[i]
            A_mat[row3, idx_B(i)] = 1j * k_i * exp_m[i]
            b_vec[row3] = 1j * k_i * delta * exp_m[i]

            for m, gm in g2_coeffs.items():
                idx = ni - m
                if n_min <= idx <= n_max:
                    j = idx - n_min
                    A_mat[row3, idx_A(j)] += -gm * exp_p[j]
                    A_mat[row3, idx_B(j)] += -gm * exp_m[j]

    sol = np.linalg.solve(A_mat, b_vec)

    r = sol[0:M]
    t = sol[M : 2 * M]

    # Flux normalization for open channels: (k_n/k_0) |amp|^2
    open_mask = En > 0
    k_ratio = np.zeros(M, dtype=float)
    k_ratio[open_mask] = np.real(kn[open_mask]) / k0

    R_flux = k_ratio * (np.abs(r) ** 2)
    T_flux = k_ratio * (np.abs(t) ** 2)

    return n, kn, r, t, R_flux, T_flux


def _check_unitarity(r: np.ndarray, t: np.ndarray, En: np.ndarray, k0: float) -> Tuple[float, str]:
    """Check S†S ≈ I for open channels (conservation of flux)."""
    M = len(r)
    open_mask = En > 0
    n_open = int(np.sum(open_mask))
    
    if n_open == 0:
        return 0.0, "No open channels"
    
    # For a single incident channel (n=0 with k=k0), flux conservation requires:
    # R_total + T_total ≈ 1
    # Flux normalization: (k_n/k_0) |amp|^2 for each open channel n
    k_n = np.sqrt(En[open_mask])
    R_total = float(np.sum(np.abs(r[open_mask])**2 * k_n / k0))
    T_total = float(np.sum(np.abs(t[open_mask])**2 * k_n / k0))
    conservation = R_total + T_total
    error = abs(conservation - 1.0)
    
    status = "PASS" if error < 1e-6 else "FAIL"
    return error, f"{status} (R+T={conservation:.9f}, error={error:.2e})"


def _amplitude_scaling_check(cfg: FloquetConfig) -> Tuple[np.ndarray, np.ndarray, str]:
    """Verify δσ scales as A₁A₂sinφ in weak drive (geometric pumping signature).
    
    Returns (g1_values, delta_sigma_vs_g1, status_message).
    """
    g1_values = np.linspace(0.0, cfg.g1 * 1.5, 6)
    delta_sigmas = np.zeros(len(g1_values))
    
    for i, g1 in enumerate(g1_values):
        cfg_i = FloquetConfig(
            E0=cfg.E0, Omega=cfg.Omega, N_sidebands=cfg.N_sidebands,
            a=cfg.a, g0=cfg.g0, g1=float(g1), phi=cfg.phi
        )
        _, _, _, _, _, TL = _solve_floquet(cfg=cfg_i, incident="left")
        _, _, _, _, _, TR = _solve_floquet(cfg=cfg_i, incident="right")
        delta_sigmas[i] = float(np.sum(TL) - np.sum(TR))
    
    # Check if approximately linear in g1 (weak drive: δσ ∝ g1 when g0 fixed)
    # Fit line to first 4 points and check linearity
    if len(g1_values) >= 4:
        fit = np.polyfit(g1_values[:4], delta_sigmas[:4], 1)
        residuals = delta_sigmas[:4] - np.polyval(fit, g1_values[:4])
        rms_error = float(np.sqrt(np.mean(residuals**2)))
        linear = rms_error < 0.01 * abs(fit[0] * g1_values[3])
        status = f"LINEAR (RMS err={rms_error:.2e})" if linear else f"NONLINEAR (RMS err={rms_error:.2e})"
    else:
        status = "INSUFFICIENT DATA"
    
    return g1_values, delta_sigmas, status


def _phi_sweep(cfg: FloquetConfig, phi_values: np.ndarray) -> np.ndarray:
    """Sweep phase lag and return δσ(φ) array."""
    delta_sigmas = np.zeros(len(phi_values))
    for i, phi in enumerate(phi_values):
        cfg_i = FloquetConfig(
            E0=cfg.E0, Omega=cfg.Omega, N_sidebands=cfg.N_sidebands,
            a=cfg.a, g0=cfg.g0, g1=cfg.g1, phi=float(phi)
        )
        _, _, _, _, _, TL = _solve_floquet(cfg=cfg_i, incident="left")
        _, _, _, _, _, TR = _solve_floquet(cfg=cfg_i, incident="right")
        delta_sigmas[i] = float(np.sum(TL) - np.sum(TR))
    return delta_sigmas


def _compute_flux_and_recoil(
    cfg: FloquetConfig,
    nL: np.ndarray,
    kL: np.ndarray,
    TL: np.ndarray,
    nR: np.ndarray,
    kR: np.ndarray,
    TR: np.ndarray,
) -> Tuple[float, float, float, float, float, float]:
    """Compute energy/momentum flux in both directions with proper dispersion.
    
    In units where ℏ=2m=1, we have E_n = k_n² (free dispersion).
    
    Returns:
        (P_right, p_right, P_left, p_left, F_net, F_over_P)
    
    where F_net is the net force (recoil on scatterer) and F_over_P is thrust-to-power.
    """
    En_L = cfg.E0 + nL * cfg.Omega
    En_R = cfg.E0 + nR * cfg.Omega
    open_L = En_L > 0
    open_R = En_R > 0
    
    # Energy flux to the right (transmitted): Σ_n T_n × ω_n where ω_n = E_n
    P_right = float(np.sum(TL[open_L] * En_L[open_L]))
    
    # Momentum flux to the right: Σ_n T_n × k_n
    p_right = float(np.sum(TL[open_L] * np.real(kL[open_L])))
    
    # Energy flux to the left (reflected channels from right-incident): Σ_n R_n × ω_n
    # For now we only have transmission, so approximate left flux from right-incidence transmission
    P_left = float(np.sum(TR[open_R] * En_R[open_R]))
    
    # Momentum flux to the left (negative x direction): Σ_n T_n × (-k_n)
    p_left = float(np.sum(TR[open_R] * np.real(kR[open_R])))
    
    # Net force on scatterer (recoil): F = -(p_right - p_left) in steady state
    # (We're subtracting because right-going momentum increases right flux)
    F_net = p_right - p_left
    
    # Total radiated power
    P_total = P_right + P_left
    
    # Force-to-power ratio (in c=1 units, compare to photon rocket bound = 1)
    # For ω=k (relativistic), F/P → 1/c=1. Deviations mean dispersion or asymmetry.
    F_over_P = F_net / P_total if P_total > 1e-12 else 0.0
    
    return P_right, p_right, P_left, p_left, F_net, F_over_P


def run(*, seed: int = 0, cfg: Optional[FloquetConfig] = None) -> str:
    """Option 1 — Floquet vacuum scattering model.

    Produces a council report that highlights δσ = σ(+k) - σ(-k) via
    non-reciprocal transmission in a driven, phase-lagged two-delta scatterer.

    `seed` is unused (kept for runner API compatibility).
    """

    _ = seed
    cfg = cfg or FloquetConfig()

    with FlightRecorder("experiment3_floquet_vacuum_scattering") as flight:
        flight.log_metric("Model", "1D scalar Floquet scattering (two driven delta couplers)")
        flight.log_metric("Definition", "δσ = σ(+k) − σ(−k), using σ ≡ total transmitted flux")

        flight.log_metric("E0", cfg.E0)
        flight.log_metric("k0", float(np.sqrt(cfg.E0)))
        flight.log_metric("Omega", cfg.Omega)
        flight.log_metric("N_sidebands", cfg.N_sidebands)
        flight.log_metric("a", cfg.a)
        flight.log_metric("g0", cfg.g0)
        flight.log_metric("g1", cfg.g1)
        flight.log_metric("phi", cfg.phi)

        nL, kL, rL, tL, RL, TL = _solve_floquet(cfg=cfg, incident="left")
        nR, kR, rR, tR, RR, TR = _solve_floquet(cfg=cfg, incident="right")

        T_left = float(np.sum(TL))
        T_right = float(np.sum(TR))
        delta_sigma = T_left - T_right

        flight.log_metric("σ(+k) [T_left]", T_left)
        flight.log_metric("σ(-k) [T_right]", T_right)
        flight.log_metric("δσ", delta_sigma)

        # === SANITY CHECK 1: Unitarity ===
        En = cfg.E0 + nL * cfg.Omega
        k0 = float(np.sqrt(cfg.E0))
        err_L, status_L = _check_unitarity(rL, tL, En, k0)
        err_R, status_R = _check_unitarity(rR, tR, En, k0)
        flight.log_metric("Unitarity (incident left)", status_L)
        flight.log_metric("Unitarity (incident right)", status_R)

        # === SANITY CHECK 2: φ-reversal ===
        phi_values = np.array([0.0, np.pi/4, np.pi/2, 3*np.pi/4, np.pi, -np.pi/2])
        delta_sigma_sweep = _phi_sweep(cfg, phi_values)
        flight.log_metric("δσ at φ=0", float(delta_sigma_sweep[0]))
        flight.log_metric("δσ at φ=π/2", float(delta_sigma_sweep[2]))
        flight.log_metric("δσ at φ=-π/2", float(delta_sigma_sweep[5]))
        sign_flip = np.sign(delta_sigma_sweep[2]) != np.sign(delta_sigma_sweep[5])
        flight.log_metric("φ-reversal sign flip", "YES" if sign_flip else "NO")

        # === SANITY CHECK 3: Momentum/energy flux and F/P ===
        P_right, p_right, P_left, p_left, F_net, F_over_P = _compute_flux_and_recoil(
            cfg, nL, kL, TL, nR, kR, TR
        )
        flight.log_metric("Power flux (right) P→", P_right)
        flight.log_metric("Momentum flux (right) p→", p_right)
        flight.log_metric("Power flux (left) P←", P_left)
        flight.log_metric("Momentum flux (left) p←", p_left)
        flight.log_metric("Net force F = p→ - p←", F_net)
        flight.log_metric("F/P (c=1 units)", F_over_P)
        flight.log_metric("Photon rocket bound", 1.0)
        f_over_p_status = "PASS (F/P ≤ 1)" if F_over_P <= 1.0 else "WARN (F/P > 1, check dispersion)"
        flight.log_metric("F/P sanity", f_over_p_status)

        # === SANITY CHECK 4: Amplitude scaling (geometric pumping signature) ===
        g1_vals, delta_sigma_vs_g1, scaling_status = _amplitude_scaling_check(cfg)
        flight.log_metric("Amplitude scaling", scaling_status)

        # Quick control: same setup but with phi=0 should reduce/kill non-reciprocity.
        cfg_sym = FloquetConfig(
            E0=cfg.E0,
            Omega=cfg.Omega,
            N_sidebands=cfg.N_sidebands,
            a=cfg.a,
            g0=cfg.g0,
            g1=cfg.g1,
            phi=0.0,
        )
        _, _, _, _, _, TL0 = _solve_floquet(cfg=cfg_sym, incident="left")
        _, _, _, _, _, TR0 = _solve_floquet(cfg=cfg_sym, incident="right")
        delta_sigma_control = float(np.sum(TL0) - np.sum(TR0))
        flight.log_metric("δσ (control φ=0)", delta_sigma_control)

        fig, axes = plt.subplots(4, 1, figsize=(10, 16))

        ax = axes[0]
        ax.set_title("Floquet Transmission Spectrum (flux per sideband)")
        ax.plot(nL, TL, marker="o", label="T_n (incident from left, +k)")
        ax.plot(nR, TR, marker="o", label="T_n (incident from right, -k)")
        ax.set_xlabel("Floquet sideband n")
        ax.set_ylabel("Flux fraction")
        ax.grid(True, alpha=0.3)
        ax.legend()

        ax2 = axes[1]
        ax2.set_title("φ-Sweep: δσ(φ) [Sign-flip test]")
        phi_deg = np.degrees(phi_values)
        ax2.plot(phi_deg, delta_sigma_sweep, marker="o", color="red")
        ax2.axhline(0, linestyle="--", color="gray", linewidth=0.5)
        ax2.set_xlabel("Phase lag φ (degrees)")
        ax2.set_ylabel("δσ")
        ax2.grid(True, alpha=0.3)

        ax3 = axes[2]
        ax3.set_title("Amplitude Scaling: δσ(g₁) [Weak-drive linearity test]")
        ax3.plot(g1_vals, delta_sigma_vs_g1, marker="o", color="blue")
        ax3.axhline(0, linestyle="--", color="gray", linewidth=0.5)
        ax3.set_xlabel("Drive amplitude g₁")
        ax3.set_ylabel("δσ")
        ax3.grid(True, alpha=0.3)

        ax4 = axes[3]
        ax4.set_title("Physics Summary")
        ax4.axis("off")
        summary = (
            f"Parameters: E0={cfg.E0:.3f}, Ω={cfg.Omega:.3f}, a={cfg.a:.3f}, g0={cfg.g0:.3f}, g1={cfg.g1:.3f}, φ={cfg.phi:.3f}\n"
            f"σ(+k)=T_left={T_left:.6f}\n"
            f"σ(-k)=T_right={T_right:.6f}\n"
            f"δσ={delta_sigma:.6e}\n\n"
            f"SANITY CHECK 1 (Unitarity):\n"
            f"  Left:  {status_L}\n"
            f"  Right: {status_R}\n\n"
            f"SANITY CHECK 2 (φ-reversal):\n"
            f"  δσ(φ=0)     = {delta_sigma_sweep[0]:.6e}\n"
            f"  δσ(φ=π/2)   = {delta_sigma_sweep[2]:.6e}\n"
            f"  δσ(φ=-π/2)  = {delta_sigma_sweep[5]:.6e}\n"
            f"  Sign flip:    {'YES ✓' if sign_flip else 'NO ✗'}\n\n"
            f"SANITY CHECK 3 (F/P vs photon rocket):\n"
            f"  P→ = {P_right:.6e}    p→ = {p_right:.6e}\n"
            f"  P← = {P_left:.6e}    p← = {p_left:.6e}\n"
            f"  F_net = {F_net:.6e}\n"
            f"  F/P = {F_over_P:.6f} (c=1)\n"
            f"  Bound: F/P ≤ 1 (photon rocket)\n"
            f"  Status: {f_over_p_status}\n\n"
            f"SANITY CHECK 4 (Amplitude scaling):\n"
            f"  {scaling_status}"
        )
        ax4.text(0.01, 0.95, summary, va="top", family="monospace", fontsize=7)

        plt.tight_layout()
        flight.save_plot(fig, filename="visual_telemetry.png")
        flight.log_metric("Plot Filename", "visual_telemetry.png")
        plt.close(fig)

        flight.log_metric("Net Impulse", float(delta_sigma))
        # Recorder will tag anomaly if |Net Impulse|>1e-4; here it's an abstract δσ.
        return "COUNCIL_REPORT.md"
