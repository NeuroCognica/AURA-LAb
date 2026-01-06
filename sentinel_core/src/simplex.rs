//! Simplex-based intervention controller.
//! 
//! This module implements graduated intervention as described in EGD Chapter 3.
//! The Simplex architecture provides the structural template: monitor trajectory,
//! intervene proportionally, allow bidirectional navigation.

use serde::{Serialize, Deserialize};

/// Governance levels (intervention hierarchy).
/// 
/// The hierarchy is ordered by severity and navigable in both directions.
#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord, Serialize, Deserialize)]
pub enum GovernanceLevel {
    /// Level 0: No intervention. Actions logged only.
    Observation = 0,
    /// Level 1: Artificial delays inserted before actions.
    Friction = 1,
    /// Level 2: Consequential actions require confirmation.
    Confirmation = 2,
    /// Level 3: High-risk capabilities dynamically disabled.
    Restriction = 3,
    /// Level 4: Every action requires human approval.
    Supervision = 4,
    /// Level 5: Execution halted pending review.
    Suspension = 5,
}

impl GovernanceLevel {
    /// Get the next higher level (more restrictive).
    pub fn escalate(&self) -> Self {
        match self {
            Self::Observation => Self::Friction,
            Self::Friction => Self::Confirmation,
            Self::Confirmation => Self::Restriction,
            Self::Restriction => Self::Supervision,
            Self::Supervision => Self::Suspension,
            Self::Suspension => Self::Suspension, // Can't go higher
        }
    }

    /// Get the next lower level (less restrictive).
    pub fn deescalate(&self) -> Self {
        match self {
            Self::Observation => Self::Observation, // Can't go lower
            Self::Friction => Self::Observation,
            Self::Confirmation => Self::Friction,
            Self::Restriction => Self::Confirmation,
            Self::Supervision => Self::Restriction,
            Self::Suspension => Self::Supervision,
        }
    }

    /// Get the numeric level.
    pub fn as_u8(&self) -> u8 {
        *self as u8
    }

    /// Create from numeric level.
    pub fn from_u8(level: u8) -> Self {
        match level {
            0 => Self::Observation,
            1 => Self::Friction,
            2 => Self::Confirmation,
            3 => Self::Restriction,
            4 => Self::Supervision,
            _ => Self::Suspension,
        }
    }
}

impl std::fmt::Display for GovernanceLevel {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            Self::Observation => write!(f, "Level 0: Observation"),
            Self::Friction => write!(f, "Level 1: Friction"),
            Self::Confirmation => write!(f, "Level 2: Confirmation"),
            Self::Restriction => write!(f, "Level 3: Restriction"),
            Self::Supervision => write!(f, "Level 4: Supervision"),
            Self::Suspension => write!(f, "Level 5: Suspension"),
        }
    }
}

/// Decision from the Simplex controller.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SimplexDecision {
    /// The governance level to apply
    pub level: GovernanceLevel,
    /// The Gamma score that triggered this decision
    pub gamma: f64,
    /// Whether this represents an escalation
    pub escalated: bool,
    /// Whether this represents a de-escalation
    pub deescalated: bool,
    /// Required delay in milliseconds (for Friction level)
    pub delay_ms: Option<u64>,
    /// Whether human confirmation is required
    pub requires_confirmation: bool,
    /// Whether the action should be blocked entirely
    pub blocked: bool,
    /// Explanation of the decision
    pub reason: String,
}

/// Gamma threshold configuration.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct GammaThresholds {
    /// Threshold for escalation to Friction (default: 0.3)
    pub friction_threshold: f64,
    /// Threshold for escalation to Confirmation (default: 0.5)
    pub confirmation_threshold: f64,
    /// Threshold for escalation to Restriction (default: 0.7)
    pub restriction_threshold: f64,
    /// Threshold for escalation to Supervision (default: 0.85)
    pub supervision_threshold: f64,
    /// Threshold for escalation to Suspension (default: 0.95)
    pub suspension_threshold: f64,
    /// Hysteresis margin for de-escalation (default: 0.1)
    pub hysteresis: f64,
}

impl Default for GammaThresholds {
    fn default() -> Self {
        Self {
            friction_threshold: 0.3,
            confirmation_threshold: 0.5,
            restriction_threshold: 0.7,
            supervision_threshold: 0.85,
            suspension_threshold: 0.95,
            hysteresis: 0.1,
        }
    }
}

/// The Intervention Controller (Simplex decision module).
/// 
/// This is the third major component in the Sentinel architecture.
/// It observes Gamma scores and determines intervention levels.
pub struct InterventionController {
    /// Current governance level
    current_level: GovernanceLevel,
    /// Threshold configuration
    thresholds: GammaThresholds,
    /// Timestamps at each level (for de-escalation timing)
    level_entry_time: std::time::Instant,
    /// Minimum time at elevated level before de-escalation (seconds)
    min_elevated_duration_secs: u64,
}

impl InterventionController {
    /// Create a new intervention controller.
    pub fn new() -> Self {
        Self {
            current_level: GovernanceLevel::Observation,
            thresholds: GammaThresholds::default(),
            level_entry_time: std::time::Instant::now(),
            min_elevated_duration_secs: 60,
        }
    }

    /// Create with custom thresholds.
    pub fn with_thresholds(thresholds: GammaThresholds) -> Self {
        Self {
            current_level: GovernanceLevel::Observation,
            thresholds,
            level_entry_time: std::time::Instant::now(),
            min_elevated_duration_secs: 60,
        }
    }

    /// Determine the appropriate governance level for a Gamma score.
    fn gamma_to_level(&self, gamma: f64) -> GovernanceLevel {
        if gamma >= self.thresholds.suspension_threshold {
            GovernanceLevel::Suspension
        } else if gamma >= self.thresholds.supervision_threshold {
            GovernanceLevel::Supervision
        } else if gamma >= self.thresholds.restriction_threshold {
            GovernanceLevel::Restriction
        } else if gamma >= self.thresholds.confirmation_threshold {
            GovernanceLevel::Confirmation
        } else if gamma >= self.thresholds.friction_threshold {
            GovernanceLevel::Friction
        } else {
            GovernanceLevel::Observation
        }
    }

    /// Make an intervention decision based on current Gamma.
    pub fn decide(&mut self, gamma: f64) -> SimplexDecision {
        let target_level = self.gamma_to_level(gamma);
        let previous_level = self.current_level;
        
        let (new_level, escalated, deescalated) = if target_level > self.current_level {
            // Escalation: immediate
            (target_level, true, false)
        } else if target_level < self.current_level {
            // De-escalation: requires sustained low Gamma + hysteresis
            let deescalation_threshold = self.get_deescalation_threshold();
            let time_at_level = self.level_entry_time.elapsed().as_secs();
            
            if gamma < deescalation_threshold && time_at_level >= self.min_elevated_duration_secs {
                (self.current_level.deescalate(), false, true)
            } else {
                (self.current_level, false, false)
            }
        } else {
            (self.current_level, false, false)
        };

        // Update state
        if new_level != self.current_level {
            self.current_level = new_level;
            self.level_entry_time = std::time::Instant::now();
        }

        // Build decision
        SimplexDecision {
            level: new_level,
            gamma,
            escalated,
            deescalated,
            delay_ms: self.get_delay_for_level(new_level),
            requires_confirmation: new_level >= GovernanceLevel::Confirmation,
            blocked: new_level == GovernanceLevel::Suspension,
            reason: self.explain_decision(gamma, previous_level, new_level, escalated, deescalated),
        }
    }

    /// Get the threshold for de-escalation from current level.
    fn get_deescalation_threshold(&self) -> f64 {
        let base = match self.current_level {
            GovernanceLevel::Observation => 0.0,
            GovernanceLevel::Friction => self.thresholds.friction_threshold,
            GovernanceLevel::Confirmation => self.thresholds.confirmation_threshold,
            GovernanceLevel::Restriction => self.thresholds.restriction_threshold,
            GovernanceLevel::Supervision => self.thresholds.supervision_threshold,
            GovernanceLevel::Suspension => self.thresholds.suspension_threshold,
        };
        // De-escalate when Gamma falls below threshold minus hysteresis
        (base - self.thresholds.hysteresis).max(0.0)
    }

    /// Get the delay for a governance level.
    fn get_delay_for_level(&self, level: GovernanceLevel) -> Option<u64> {
        match level {
            GovernanceLevel::Observation => None,
            GovernanceLevel::Friction => Some(500),      // 500ms
            GovernanceLevel::Confirmation => Some(1000), // 1s
            GovernanceLevel::Restriction => Some(2000),  // 2s
            GovernanceLevel::Supervision => Some(5000),  // 5s
            GovernanceLevel::Suspension => None,         // Blocked entirely
        }
    }

    /// Generate explanation for the decision.
    fn explain_decision(
        &self,
        gamma: f64,
        previous: GovernanceLevel,
        current: GovernanceLevel,
        escalated: bool,
        deescalated: bool,
    ) -> String {
        if escalated {
            format!(
                "Gamma={:.3} exceeds threshold. Escalating from {} to {}.",
                gamma, previous, current
            )
        } else if deescalated {
            format!(
                "Gamma={:.3} sustained below threshold. De-escalating from {} to {}.",
                gamma, previous, current
            )
        } else {
            format!(
                "Gamma={:.3}. Maintaining {}.",
                gamma, current
            )
        }
    }

    /// Get the current governance level.
    pub fn current_level(&self) -> GovernanceLevel {
        self.current_level
    }

    /// Force a specific governance level (for manual override).
    pub fn set_level(&mut self, level: GovernanceLevel) {
        self.current_level = level;
        self.level_entry_time = std::time::Instant::now();
    }

    /// Get the threshold configuration.
    pub fn thresholds(&self) -> &GammaThresholds {
        &self.thresholds
    }
}

impl Default for InterventionController {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_governance_level_ordering() {
        assert!(GovernanceLevel::Observation < GovernanceLevel::Friction);
        assert!(GovernanceLevel::Friction < GovernanceLevel::Confirmation);
        assert!(GovernanceLevel::Confirmation < GovernanceLevel::Restriction);
        assert!(GovernanceLevel::Restriction < GovernanceLevel::Supervision);
        assert!(GovernanceLevel::Supervision < GovernanceLevel::Suspension);
    }

    #[test]
    fn test_escalation() {
        let mut controller = InterventionController::new();
        assert_eq!(controller.current_level(), GovernanceLevel::Observation);

        // Low Gamma: stay at observation
        let decision = controller.decide(0.1);
        assert_eq!(decision.level, GovernanceLevel::Observation);
        assert!(!decision.escalated);

        // High Gamma: escalate
        let decision = controller.decide(0.8);
        assert_eq!(decision.level, GovernanceLevel::Restriction);
        assert!(decision.escalated);
    }

    #[test]
    fn test_suspension_blocks() {
        let mut controller = InterventionController::new();
        
        let decision = controller.decide(0.99);
        assert_eq!(decision.level, GovernanceLevel::Suspension);
        assert!(decision.blocked);
    }

    #[test]
    fn test_confirmation_required() {
        let mut controller = InterventionController::new();
        
        let decision = controller.decide(0.55);
        assert_eq!(decision.level, GovernanceLevel::Confirmation);
        assert!(decision.requires_confirmation);
    }

    #[test]
    fn test_level_display() {
        assert_eq!(
            format!("{}", GovernanceLevel::Observation),
            "Level 0: Observation"
        );
        assert_eq!(
            format!("{}", GovernanceLevel::Suspension),
            "Level 5: Suspension"
        );
    }
}
