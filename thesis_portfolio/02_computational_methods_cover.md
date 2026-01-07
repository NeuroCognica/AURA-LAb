# Thesis 02: Computational Methods

---

## Formal Title

**AURA-Lab: A Framework for Reproducible, AI-Orchestrated Computational Physics Research with Immutable Provenance and Multi-Agent Validation**

---

## Author Information

**Author:** Michael Holt  
**Institution:** NeuroCognica Research Initiative  
**Department:** Computer Science / Computational Science  
**Date:** January 2026  
**Contact:** [Redacted]

---

## Layman's Description

Science has a reproducibility crisis. When researchers publish computational results, other scientists often can't recreate them—the code is lost, the parameters are undocumented, the random seeds are forgotten, and the exact sequence of decisions that led to the discovery is buried in someone's memory.

This thesis presents a solution: a "Flight Recorder" for scientific computing. Just like the black box on an airplane records everything that happens during a flight, the AURA-Lab system automatically captures every simulation run, every parameter choice, every piece of code, and every AI conversation that contributed to a discovery.

But it goes further. Instead of relying on one AI assistant to help with research, the system uses *multiple* AI models simultaneously—checking each other's work, catching bugs, and validating results. When one AI suggests code, another AI tries to break it. When one AI interprets results, another AI plays devil's advocate.

The result: 98% reproducibility (compared to ~30% for typical published computational papers), 90% bug detection (compared to 55% with a single AI), and 4.6× faster development cycles. The physics discoveries in Thesis 01 were made using this system—and anyone can verify exactly how by examining the immutable logs.

---

## Position in Portfolio

### This Thesis Is:
- The **methodological foundation** that enabled all other computational work
- The **software engineering** contribution (how to build auditable AI-assisted research)
- A **meta-thesis** about *how to do science* with AI partners

### Dependencies:
| Thesis | Relationship |
|--------|--------------|
| **04: EGD** | The Flight Recorder *implements* EGD's provenance requirements. Governance principles from EGD informed the design of immutable logging and intervention tracking. |
| **03: Cognitive Sovereignty** | The multi-LLM orchestration system treats AI assistants as *collaborators with agency*, not tools. This aligns with Thesis 03's framework for respecting AI contributions. |

### What This Enables:
- **Thesis 01 (Floquet Physics):** All 847 simulation runs are fully reproducible because of this framework
- **Thesis 03 (Cognitive Sovereignty):** The conversation logs are "Witness Artifacts"—proof that AI-human collaboration occurred under principled conditions
- **sentinel_core:** The Rust reference implementation uses Flight Recorder patterns

---

## Core Documents

- **Full Thesis:** [02_computational_methods.md](02_computational_methods.md)
- **Flight Recorder Code:** flight_recorder/mission_logger.py
- **Mission Logs:** mission_logs/ (847+ experiment records)

---

## Key Metrics

| Metric | AURA-Lab | Industry Baseline |
|--------|----------|-------------------|
| Reproducibility | 98% | ~30% |
| Bug Detection | 90% | 55% (single LLM) |
| Development Speed | 4.6× faster | Baseline |
| Runtime Overhead | <2% | N/A |
| Post-Processing | ~30 seconds | Manual (hours) |

---

## Status

| Metric | Value |
|--------|-------|
| Completion | ~95% |
| Line Count | ~1,800 |
| Chapters | 8 |
| Code Artifacts | Flight Recorder, lab.py, experiment runners |
| Validation | 847 logged experiments with full provenance |
