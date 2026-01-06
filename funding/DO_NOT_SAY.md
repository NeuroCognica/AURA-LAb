# DO NOT SAY — Exclusion List for All Outreach

**Purpose:** Phrases, claims, and topics to avoid in any funding, consulting, or public communication.

---

## Absolute Exclusions (Never Use)

### Defense / Military
- DARPA
- Defense applications
- Military
- Weapons
- National security (in the defense sense)
- DoD, Department of Defense
- Classified
- Dual-use (in military context)

### Physics / Propulsion Work
- Propulsion
- Floquet
- Quantum (in the physics sense)
- Vacuum
- Momentum
- Scattering
- Thermal ratchet
- Maxwell demon
- Any reference to Papers 1-3 or physics experiments

### Overclaims
- "Unhackable"
- "Impossible to break"
- "Impossible encryption"
- "Quantum-safe" (unless specifically discussing post-quantum crypto, which we are not)
- "Unbreakable"
- "Foolproof"
- "Bulletproof"
- "Nation-state proof"
- "APT-resistant" (without qualification)
- "Guarantees safety"
- "Prevents all attacks"
- "Solves alignment"
- "Solves AI safety"
- "Prevents misuse"
- "Makes AI safe"

### Grand Claims
- "Revolutionary"
- "Paradigm shift"
- "World-changing"
- "First-ever"
- "Unprecedented"
- "Groundbreaking"
- "Game-changing"
- "Disruptive"
- "TCP/IP of governance"
- "Operating system for AI"
- "Universal governance"
- "Superintelligence-proof"

### Misleading Technical Claims
- "Quantum integer" (meaningless)
- "Warp" (unless discussing UI)
- "Perpetual" anything
- "Zero latency"
- "Zero overhead"
- "Perfect detection"
- "100% accuracy"

---

## Conditional Exclusions (Use Only With Qualification)

### Implementation Status
- ❌ "We have built..." → ✅ "We have built a skeleton/prototype..."
- ❌ "Production-ready" → ✅ "Reference implementation"
- ❌ "Battle-tested" → ✅ "Tested against simulated workloads"
- ❌ "Deployed at scale" → (Do not claim; we haven't)

### Security Claims
- ❌ "Secure" → ✅ "Increases security" or "reduces attack surface"
- ❌ "Prevents" → ✅ "Reduces probability of" or "makes difficult"
- ❌ "Detects all" → ✅ "Improves detectability of"
- ❌ "Blocks" → ✅ "Creates friction for"

### Novelty Claims
- ❌ "Novel" → ✅ "Addresses a gap in existing frameworks"
- ❌ "Invented" → ✅ "Synthesized from" or "adapted from"
- ❌ "First" → ✅ "One of the first" or avoid entirely

---

## Topic Boundaries

### Do Discuss
- Execution governance for AI agents
- Behavioral trajectory monitoring
- Graduated intervention mechanisms
- Context binding for capabilities
- Rate shaping for oversight
- Audit logging and tamper evidence
- The agency gap between authorization and execution

### Do NOT Discuss
- AI alignment (except to say EGD is orthogonal to it)
- Consciousness or sentience
- AGI or superintelligence (except to note EGD doesn't address it)
- Autonomous weapons
- Surveillance applications
- Political or ideological positions
- Specific companies or their failures (unless public and relevant)
- Pricing or business model details beyond what's in materials

---

## Code Status Honesty

**Always say:**
- "Skeleton implementation"
- "Reference implementation"
- "Proof of concept"
- "~3,000 lines of Rust with 27 passing tests"
- "Not production-hardened"
- "Not adversarially tested"

**Never say:**
- "Production-ready"
- "Battle-tested"
- "Enterprise-grade"
- "Fully implemented"
- "Complete"

---

## Verification Rule

Before sending any external communication, search for:
1. Any word from the "Absolute Exclusions" list
2. Any unqualified claim from the "Conditional Exclusions" list
3. Any superlative (best, most, only, first, unique) without evidence

If found, revise or remove.
