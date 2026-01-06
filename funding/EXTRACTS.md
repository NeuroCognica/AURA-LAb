# EGD Source Extracts

**Purpose:** Canonical statements extracted from EGD chapters for consistent use across funding materials.

---

## 5 Problem Statements

1. **The Agency Gap:** When an authorized agent generates actions at runtime—rather than selecting from enumerated options—traditional authorization sees the gate but not the path. The specific actions along the trajectory are emergent, not specified at authorization time.

2. **Authorization as Insufficient:** Authorization at the request boundary is inadequate when execution is a process, not an event. A request authorized at $t_0$ generates a sequence of states through $t_n$, and the trajectory is path-dependent, context-sensitive, and unknown at authorization time.

3. **Identity vs. Behavior:** Traditional access control answers "Who is this?" when the salient question is "What is this doing?" ACLs and RBAC govern identity, not trajectory. They provide a certificate of identity when what is needed is a constraint on behavior.

4. **Compounding Trajectories:** Individual actions, each permissible, can combine into impermissible outcomes. An agent operating within policy bounds may, through a sequence of individually reasonable steps, evolve into state-space regions that no human anticipated and no policy explicitly forbids.

5. **Velocity Exceeds Oversight:** Machine-speed execution outpaces human observation. By the time a governance system detects anomalous behavior, the trajectory may have reached an irrecoverable state. An adversary who compromises an authorized agent can cause damage at rates that exceed human response capacity.

---

## 5 Mechanism Statements

1. **CBIG (Context-Bound Integrity Gate):** A cryptographic primitive that derives execution capabilities from environmental state rather than stored secrets alone. The key required to perform an operation is computed from a master secret and a context signature; the computation yields a valid key only when current context matches issuance conditions. Capabilities become non-transferable, environment-locked, and automatically expiring.

2. **VDF Rate Shaping:** Verifiable Delay Functions impose minimum time costs per protected operation through sequential computation requirements. An adversary with a million machines cannot evaluate the VDF faster than a single processor. Time becomes a governance resource that cannot be parallelized away.

3. **Gamma Score (Γ):** A composite proxy metric measuring governance difficulty—how hard it would be to maintain human sovereignty if current trends continue. Components: action entropy (predictability), resource velocity (consumption rate), scope expansion (boundary drift), reversibility index (undo cost), human latency (time since checkpoint). Conservative by design: false positives are preferable to false negatives.

4. **Simplex-style Graduated Intervention:** A hierarchy of responses replacing binary kill switches. Level 0: logging. Level 1: friction (delays). Level 2: confirmation (policy check). Level 3: restriction (capability invalidation). Level 4: supervision (human review queue). Level 5: suspension. Bidirectional: escalation when Γ rises, de-escalation when trajectories normalize.

5. **Flight Recorder:** Append-only, hash-chained logs with Merkle root anchoring to external transparency services. Provides local completeness, tamper evidence, non-repudiation, and offline resilience. The agent's "black box"—a complete, verifiable record of what happened, what Gamma scores were produced, and what interventions occurred.

---

## 5 Limitations / Non-Claims

1. **EGD does not solve alignment.** Alignment concerns whether an agent's objectives match human values. EGD concerns whether behavior stays within acceptable bounds. A misaligned agent may comply with governance. EGD is orthogonal to alignment, not a substitute.

2. **EGD does not guarantee safety.** It reduces the probability of harm and increases the detectability of harmful trajectories. It does not make harm impossible. An agent may cause harm within governance bounds, or faster than governance can respond.

3. **EGD does not replace human judgment.** Graduated intervention includes human-in-the-loop levels, but the framework cannot force good judgment. Humans may approve harmful actions, ignore alerts, or misconfigure policies.

4. **EGD does not scale to superintelligence.** The framework assumes governance mechanisms can observe and intervene in agent behavior. A sufficiently capable agent might predict governance responses, deceive monitoring, or manipulate operators. EGD addresses current and near-term systems.

5. **EGD can fail.** Over-governance destroys utility. Under-governance provides false assurance. Governance capture by adversaries or operators subverts mechanisms. False positives require contestability. Ethical misuse is possible. These are boundaries to acknowledge, not problems to hide.

---

## Source Files

- [EGD_Chapter1_The_Death_of_Determinism.md](../CBIG/EGD_Chapter1_The_Death_of_Determinism.md)
- [EGD_Chapter2_Context_as_Cryptographic_Primitive.md](../CBIG/EGD_Chapter2_Context_as_Cryptographic_Primitive.md)
- [EGD_Chapter3_Trajectory_Control_Theory.md](../CBIG/EGD_Chapter3_Trajectory_Control_Theory.md)
- [EGD_Chapter4_The_Sentinel_Protocol.md](../CBIG/EGD_Chapter4_The_Sentinel_Protocol.md)
- [EGD_Chapter5_Generalization_Beyond_AURA.md](../CBIG/EGD_Chapter5_Generalization_Beyond_AURA.md)
- [EGD_Chapter6_Related_Work_and_Differentiation.md](../CBIG/EGD_Chapter6_Related_Work_and_Differentiation.md)
- [EGD_Chapter7_Limitations_Ethics_Failure_Modes.md](../CBIG/EGD_Chapter7_Limitations_Ethics_Failure_Modes.md)
- [EGD_Chapter8_Conclusion.md](../CBIG/EGD_Chapter8_Conclusion.md)
