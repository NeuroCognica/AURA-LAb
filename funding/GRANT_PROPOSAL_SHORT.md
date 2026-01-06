# EGD Grant Proposal (Short Form)
## Execution Governance Dynamics: A Framework for Governing Agentic AI Systems

**Principal Investigator:** Michael Holt  
**Affiliation:** NeuroCognica Research Initiative (Independent Researcher)  
**Requested Amount:** $25,000 – $75,000 (see budget tiers)  
**Duration:** 90 days (extendable to 6 months at higher funding levels)

---

## 1. Problem Statement

AI agents deployed in production environments now generate their own action sequences. An agent authorized to "manage files" or "optimize systems" decides at runtime which specific operations to perform. Traditional access control evaluated the authorization request—"Can this agent manage files?"—but never saw the specific file operations that followed.

This creates what we term the **Agency Gap**: the interval between what is authorized and what is executed when the executor is capable of generating its own actions.

The consequences are already visible. Authorized agents delete compliance-critical data while optimizing storage. They send emails that trigger downstream automated systems. They modify configurations in ways that individually seem reasonable but collectively create vulnerabilities. Every action is logged. Every permission is valid. Every credential check passes. The harm occurs anyway.

Existing security frameworks—RBAC, ABAC, Zero Trust—were designed for a different computational model: one where authorized entities perform enumerated operations with predictable outcomes. They are not obsolete, but they are mismatched. They govern identity and permissions. They do not govern trajectories.

---

## 2. Proposed Solution: Execution Governance Dynamics (EGD)

EGD reframes agent governance from a permission problem to a trajectory problem. If execution is a process (not an event), governance must be a dynamic system (not a gate).

The framework provides four mechanisms:

**Context-Bound Integrity Gate (CBIG):** Capabilities derived from environmental state via HKDF. A capability key can only be computed when current context (hardware attestation, software state, temporal bounds) matches issuance conditions. Capabilities cannot be exfiltrated or exercised in unauthorized environments.

**VDF Rate Shaping:** Verifiable Delay Functions impose minimum time costs per protected operation through sequential computation. Cannot be parallelized. Creates mandatory friction that slows adversarial action sequences.

**Gamma Score (Γ):** A composite metric measuring governance difficulty in real time. Components include action entropy, resource velocity, scope expansion, reversibility index, and human latency. Higher Γ indicates harder-to-govern state, triggering escalation.

**Graduated Intervention:** Six levels from logging-only (Level 0) to execution suspension (Level 5). Responses scale with Γ. De-escalation occurs when trajectories normalize. Replaces binary kill switches with proportional control.

**Flight Recorder:** Hash-chained, Merkle-anchored logs providing tamper-evident, non-repudiable audit trails.

---

## 3. Scope and Non-Claims

To be explicit about what EGD does and does not address:

| What EGD Does | What EGD Does NOT Do |
|---------------|----------------------|
| Governs agent behavior during execution | Solve AI alignment |
| Makes misuse expensive, detectable, slow | Guarantee safety |
| Provides trajectory awareness | Replace human judgment |
| Increases cost of adversarial exploitation | Prevent all attacks |
| Supports human oversight with graduated response | Scale to superintelligent systems |

EGD is a **behavioral governance framework**, not an alignment solution. It assumes agents may drift into harmful trajectories (whether through adversarial compromise, misconfiguration, or emergent behavior) and provides mechanisms to detect and respond. It does not address whether agents have correct objectives.

EGD can fail through over-governance (destroying utility), under-governance (false assurance), or governance capture. Calibration is non-trivial. The framework is designed for current and near-term agentic systems, not hypothetical superintelligent agents.

---

## 4. Current Status

**Framework:** Documented in 8 chapters (~15,000 words) covering theory, implementation, generalization, related work, and limitations.

**Implementation:** Sentinel Protocol skeleton in Rust. ~3,000 lines. 27 passing tests. Modules: context binding, Gamma scoring, intervention control, VDF rate shaping, flight recorder. Published to GitHub for provenance.

**What Exists:** Working code structure with test coverage. Cryptographic primitives implemented (HKDF, SHA-256, Merkle roots). Intervention state machine. Log chain integrity verification.

**What Does Not Exist:** Production hardening. Adversarial testing. Empirical evaluation against simulated workloads. Formal security audit.

---

## 5. Proposed Work (90-Day Plan)

### Milestone 1: Evaluation Harness (Days 1–30)
- Build simulated agent workloads with controlled behavior patterns
- Inject adversarial trajectories (data exfiltration, scope expansion, velocity spikes)
- Instrument Gamma scoring and intervention triggering
- **Deliverable:** Evaluation harness code + baseline measurements

### Milestone 2: Quantified Metrics (Days 31–60)
- Measure VDF abuse cost ratio (time-to-harm with/without rate shaping)
- Measure Gamma detection latency (actions between onset and detection)
- Measure log verification performance
- Characterize false positive rates across threshold configurations
- **Deliverable:** Evaluation report with empirical data

### Milestone 3: Technical Writeup (Days 61–90)
- Consolidate framework documentation, implementation notes, and evaluation results
- Prepare preprint-style technical report suitable for arXiv or workshop
- Publish evaluation harness and results for reproducibility
- **Deliverable:** Technical report + public code release

---

## 6. Budget

### Tier 1: $25,000 (Minimum Viable)
| Item | Amount |
|------|--------|
| Researcher runway (3 months: housing, food, health insurance) | $18,000 |
| Cloud compute (evaluation workloads) | $2,000 |
| Legal (entity formation, basic IP review) | $3,000 |
| Contingency | $2,000 |

### Tier 2: $50,000 (Recommended)
| Item | Amount |
|------|--------|
| Researcher runway (3 months) | $18,000 |
| Cloud compute | $3,000 |
| Legal + provisional patent filing | $8,000 |
| Security review contractor (40 hours @ $200/hr) | $8,000 |
| Test automation contractor (40 hours @ $150/hr) | $6,000 |
| Conference travel (1 venue) | $3,000 |
| Contingency | $4,000 |

### Tier 3: $75,000 (Extended)
| Item | Amount |
|------|--------|
| Researcher runway (6 months) | $36,000 |
| Cloud compute | $5,000 |
| Legal + provisional patent | $8,000 |
| Security review contractor | $8,000 |
| Part-time collaborator (3 months @ $3k/month) | $9,000 |
| Conference travel (2 venues) | $5,000 |
| Contingency | $4,000 |

All budgets assume independent researcher with no institutional overhead.

---

## 7. Evaluation Criteria (Self-Measurable)

The following metrics can be evaluated using the proposed evaluation harness without external partners:

1. **VDF Abuse Cost Ratio**  
   Metric: Wall-clock time to execute N adversarial operations with VDF rate shaping vs. without.  
   Target: ≥10x slowdown for adversarial patterns; <2x overhead for legitimate patterns.

2. **Gamma Detection Latency**  
   Metric: Number of actions between simulated trajectory drift onset and Γ threshold crossing.  
   Target: Detection within 5 actions of anomaly injection.

3. **Intervention Accuracy**  
   Metric: False positive rate (legitimate behavior flagged) and false negative rate (adversarial behavior missed) across Γ threshold configurations.  
   Target: Identify Pareto-optimal threshold range.

4. **Log Integrity Verification**  
   Metric: Time to verify hash chain and Merkle root for 10,000 logged actions.  
   Target: <1 second verification time.

---

## 8. Why Fund This Work

Agentic AI is deploying now. Governance frameworks are not keeping pace. The research community has focused heavily on alignment (correct objectives) and less on behavioral governance (acceptable execution). Both are necessary.

EGD addresses a specific, tractable problem: how to maintain human oversight of autonomous agents that generate their own actions. It does not claim to solve alignment or guarantee safety. It provides concrete mechanisms—implementable today—that increase the cost of misuse and improve detectability.

The framework is documented. The implementation exists (in skeleton form). What is needed is empirical validation and public dissemination.

---

## 9. Contact

**Michael Holt**  
Founder, NeuroCognica  
founder@neurocognica.com  

**Repository:** https://github.com/NeuroCognica/AURA-LAb
