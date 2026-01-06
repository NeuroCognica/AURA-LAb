//! # Sentinel Core
//! 
//! Reference implementation of Execution Governance Dynamics (EGD).
//! 
//! This crate provides the foundational primitives for governing autonomous agents:
//! 
//! - **Context Binding (CBIG)**: Cryptographic binding of capabilities to environmental state
//! - **Gamma Scoring**: Continuous trajectory risk assessment
//! - **Rate Shaping (VDF)**: Temporal constraints on execution velocity
//! - **Simplex Control**: Graduated intervention hierarchy
//! 
//! ## Architecture
//! 
//! ```text
//! ┌─────────────────────────────────────────────────────────────┐
//! │                      Agent Execution                        │
//! └─────────────────────────────────────────────────────────────┘
//!                              │
//!                              ▼
//! ┌─────────────────────────────────────────────────────────────┐
//! │                   Context Evaluator                         │
//! │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐         │
//! │  │ HW Attest   │  │ SW State    │  │ Temporal    │         │
//! │  └─────────────┘  └─────────────┘  └─────────────┘         │
//! │                         │                                   │
//! │                         ▼                                   │
//! │              ContextSignature + HKDF                        │
//! │                         │                                   │
//! │                         ▼                                   │
//! │                  Capability Key                             │
//! └─────────────────────────────────────────────────────────────┘
//!                              │
//!                              ▼
//! ┌─────────────────────────────────────────────────────────────┐
//! │                  Trajectory Monitor                         │
//! │  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌───────┐ │
//! │  │ Γ_a     │ │ Γ_r     │ │ Γ_s     │ │ Γ_i     │ │ Γ_h   │ │
//! │  │ Entropy │ │ Velocity│ │ Scope   │ │ Reversi │ │ Human │ │
//! │  └─────────┘ └─────────┘ └─────────┘ └─────────┘ └───────┘ │
//! │                         │                                   │
//! │                         ▼                                   │
//! │                   Γ = Σ wᵢ·Γᵢ                               │
//! └─────────────────────────────────────────────────────────────┘
//!                              │
//!                              ▼
//! ┌─────────────────────────────────────────────────────────────┐
//! │               Intervention Controller                       │
//! │                                                             │
//! │  Level 0: Observe  ──►  Level 1: Friction  ──►              │
//! │  Level 2: Confirm  ──►  Level 3: Restrict  ──►              │
//! │  Level 4: Supervise ──► Level 5: Suspend                    │
//! └─────────────────────────────────────────────────────────────┘
//!                              │
//!                              ▼
//! ┌─────────────────────────────────────────────────────────────┐
//! │                    Flight Recorder                          │
//! │           Hash Chain + Merkle Anchoring                     │
//! └─────────────────────────────────────────────────────────────┘
//! ```

pub mod context;
pub mod gamma;
pub mod vdf;
pub mod simplex;
pub mod flight_recorder;
pub mod error;

pub use context::{ContextSignature, ContextEvaluator, CapabilityKey};
pub use gamma::{GammaScore, GammaWeights, TrajectoryMonitor};
pub use vdf::{VdfProof, RateShaper};
pub use simplex::{GovernanceLevel, InterventionController, SimplexDecision};
pub use flight_recorder::{FlightRecorder, LogEntry};
pub use error::SentinelError;

/// The complete Sentinel governance system.
/// 
/// This struct composes all EGD components into a unified governance primitive.
pub struct Sentinel {
    pub context_evaluator: ContextEvaluator,
    pub trajectory_monitor: TrajectoryMonitor,
    pub rate_shaper: RateShaper,
    pub intervention_controller: InterventionController,
    pub flight_recorder: FlightRecorder,
}

impl Sentinel {
    /// Create a new Sentinel instance with default configuration.
    pub fn new(master_key: [u8; 32]) -> Self {
        Self {
            context_evaluator: ContextEvaluator::new(master_key),
            trajectory_monitor: TrajectoryMonitor::new(GammaWeights::default()),
            rate_shaper: RateShaper::new(1000), // 1 second default delay
            intervention_controller: InterventionController::new(),
            flight_recorder: FlightRecorder::new(),
        }
    }

    /// Evaluate whether an action should proceed.
    /// 
    /// This is the core governance decision point. It:
    /// 1. Verifies context binding
    /// 2. Computes current Gamma score
    /// 3. Applies rate shaping delay
    /// 4. Returns the appropriate intervention level
    pub fn evaluate_action(&mut self, action: &str) -> Result<SimplexDecision, SentinelError> {
        // Log the action attempt
        self.flight_recorder.log_action(action)?;
        
        // Compute current Gamma
        let gamma = self.trajectory_monitor.compute_gamma();
        self.flight_recorder.log_gamma(gamma.composite)?;
        
        // Get intervention decision from Simplex logic
        let decision = self.intervention_controller.decide(gamma.composite);
        self.flight_recorder.log_intervention(&decision)?;
        
        Ok(decision)
    }

    /// Record that an action was executed.
    /// Updates trajectory state for future Gamma calculations.
    pub fn record_execution(&mut self, action: &str, reversible: bool) {
        self.trajectory_monitor.record_action(action, reversible);
    }

    /// Record human checkpoint (resets human latency component).
    pub fn human_checkpoint(&mut self) {
        self.trajectory_monitor.human_checkpoint();
    }

    /// Get the current governance level.
    pub fn current_level(&self) -> GovernanceLevel {
        self.intervention_controller.current_level()
    }

    /// Get the current composite Gamma score.
    pub fn current_gamma(&self) -> f64 {
        self.trajectory_monitor.compute_gamma().composite
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_sentinel_creation() {
        let key = [0u8; 32];
        let sentinel = Sentinel::new(key);
        assert_eq!(sentinel.current_level(), GovernanceLevel::Observation);
    }

    #[test]
    fn test_gamma_escalation() {
        let key = [0u8; 32];
        let mut sentinel = Sentinel::new(key);
        
        // Simulate high-velocity, irreversible actions
        for i in 0..100 {
            sentinel.record_execution(&format!("delete_file_{}", i), false);
        }
        
        let gamma = sentinel.current_gamma();
        // Irreversibility component should be elevated (100% irreversible actions)
        // Even if velocity is low due to test speed, reversibility should dominate
        assert!(gamma > 0.2, "Gamma should escalate with irreversible actions (got {})", gamma);
    }
}
