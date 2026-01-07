# Thesis 01: Floquet Physics

---

## Formal Title

**Non-Reciprocal Transport and Information-Enhanced Rectification in Driven Scalar Fields: A Unified Theory of Geometric Momentum Pumping, Thermal Decoherence, and Active Fluctuation Harvesting**

---

## Author Information

**Author:** Michael Holt  
**Institution:** NeuroCognica Research Initiative  
**Department:** Theoretical and Computational Physics  
**Date:** January 2026  
**Contact:** [Redacted]

---

## Layman's Description

Imagine a one-way valve for heat—a device that lets thermal energy flow in one direction but blocks it from flowing back, like a turnstile that only spins one way. This thesis explains how to build such a device using nothing but carefully timed oscillations in a material's properties.

The core discovery is that by "wiggling" a system in just the right pattern—following a loop in parameter space—you can create a pumping effect that moves energy in one direction without any moving parts. This is called a "Floquet pump," named after the mathematician who studied periodic systems.

But there's a problem: heat itself fights back. Random thermal vibrations scramble the delicate timing that makes the pump work. This thesis identifies exactly how hot is "too hot" for these devices to function, and then proposes a solution: use a smart feedback system (a "Sentinel") that watches the thermal fluctuations and times its interventions to harvest energy from the randomness itself, rather than fighting against it.

Think of it like surfing: instead of trying to calm the ocean, you learn to ride the waves. The result is a device that works 2.5× better in hot environments and extracts 6.9× more useful work from thermal chaos than random operation would achieve.

---

## Position in Portfolio

### This Thesis Is:
- The **physics discovery** that validates the computational methods
- The **experimental substrate** for testing EGD-governed simulations
- A **pure science** contribution (condensed matter / statistical mechanics)

### Dependencies:
| Thesis | Relationship |
|--------|--------------|
| **02: Computational Methods** | This physics was *discovered using* the Flight Recorder and multi-LLM methodology described in Thesis 02. The reproducibility infrastructure made these simulations tractable. |
| **04: EGD** | The "Sentinel" feedback demon in this thesis is a *physical instantiation* of EGD's intervention hierarchy—governance applied to thermodynamic trajectories rather than software execution. |

### What This Enables:
- Proves the Computational Methods framework can produce publishable physics
- Provides a non-software domain where EGD principles apply (thermodynamics)
- Demonstrates that "governance as trajectory control" works in physical systems

---

## Core Documents

- **Full Thesis:** [01_floquet_physics.md](01_floquet_physics.md)
- **PRB Paper 1:** Paper1_PRB_Format.tex (Non-Reciprocal Floquet Mechanism)
- **Experiment Code:** experiments/experiment3_floquet_scattering.py

---

## Key Equations

**Thermal Death Threshold:**
$$T_c = \frac{\hbar \omega_0}{k_B} \cdot \frac{\Gamma}{\gamma}$$

**Rectification Efficiency:**
$$\eta = \frac{\langle P \rangle_{\text{Sentinel}}}{\langle P \rangle_{\text{random}}} = 6.9 \pm 0.3$$

---

## Status

| Metric | Value |
|--------|-------|
| Completion | 100% |
| Line Count | ~3,800 |
| Papers Included | 3 (PRB format) |
| Simulations Run | 847 logged experiments |
| Reproducibility | 98% (via Flight Recorder) |
