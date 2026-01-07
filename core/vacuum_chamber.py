from __future__ import annotations

from dataclasses import dataclass, field
from typing import List

import numpy as np


@dataclass
class VacuumChamber:
    """1D scalar-field FDTD chamber with a moving potential barrier."""

    nx: int
    dx: float

    x: np.ndarray = field(init=False)
    phi: np.ndarray = field(init=False)
    phi_prev: np.ndarray = field(init=False)
    phi_next: np.ndarray = field(init=False)

    total_energy_field: List[float] = field(default_factory=list, init=False)
    mirror_force: List[float] = field(default_factory=list, init=False)
    mirror_pos_history: List[float] = field(default_factory=list, init=False)

    def __post_init__(self) -> None:
        self.x = np.linspace(0, self.nx * self.dx, self.nx)
        self.phi = np.zeros(self.nx)
        self.phi_prev = np.zeros(self.nx)
        self.phi_next = np.zeros(self.nx)

    def seed_vacuum_noise(self, *, seed: int = 42, sigma: float = 0.001) -> None:
        rng = np.random.default_rng(seed)
        self.phi = rng.normal(0.0, sigma, self.nx)
        self.phi_prev = np.copy(self.phi)

    def step(self, *, dt: float, c: float, v_potential: np.ndarray) -> None:
        """Advance the field one timestep and record force/energy telemetry."""
        laplacian = (
            np.roll(self.phi, -1) - 2 * self.phi + np.roll(self.phi, 1)
        ) / (self.dx**2)
        interaction = v_potential * self.phi

        self.phi_next = 2 * self.phi - self.phi_prev + (dt**2) * (
            (c**2) * laplacian - interaction
        )

        # Hard-wall boundaries
        self.phi_next[0] = 0.0
        self.phi_next[-1] = 0.0

        grad_v = np.gradient(v_potential, self.dx)
        force = -float(np.sum((self.phi**2) * grad_v) * self.dx)
        self.mirror_force.append(force)

        dphi_dt = (self.phi_next - self.phi_prev) / (2 * dt)
        dphi_dx = np.gradient(self.phi, self.dx)
        energy = 0.5 * float(
            np.sum(dphi_dt**2 + (c**2) * dphi_dx**2 + v_potential * self.phi**2)
            * self.dx
        )
        self.total_energy_field.append(energy)

        self.phi_prev = np.copy(self.phi)
        self.phi = np.copy(self.phi_next)
