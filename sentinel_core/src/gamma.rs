//! Gamma Score implementation.
//! 
//! This module implements trajectory monitoring as described in EGD Chapter 3.
//! Gamma is a composite metric that proxies for governance difficulty.

use std::collections::VecDeque;
use chrono::{DateTime, Utc};
use serde::{Serialize, Deserialize};

/// Configuration weights for Gamma components.
/// 
/// Γ = Σ wᵢ·Γᵢ
/// 
/// Weights are domain-specific and must be calibrated empirically.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct GammaWeights {
    /// Weight for action entropy (novelty of behavior)
    pub w_entropy: f64,
    /// Weight for resource velocity (rate of consumption/modification)
    pub w_velocity: f64,
    /// Weight for scope expansion (departure from original task)
    pub w_scope: f64,
    /// Weight for reversibility (stakes of recent actions)
    pub w_reversibility: f64,
    /// Weight for human latency (time since oversight)
    pub w_human_latency: f64,
}

impl Default for GammaWeights {
    fn default() -> Self {
        Self {
            w_entropy: 0.15,
            w_velocity: 0.20,
            w_scope: 0.20,
            w_reversibility: 0.25,
            w_human_latency: 0.20,
        }
    }
}

impl GammaWeights {
    /// Validate that weights sum to 1.0 (within tolerance).
    pub fn validate(&self) -> bool {
        let sum = self.w_entropy 
            + self.w_velocity 
            + self.w_scope 
            + self.w_reversibility 
            + self.w_human_latency;
        (sum - 1.0).abs() < 0.001
    }
}

/// The computed Gamma score with component breakdown.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct GammaScore {
    /// Composite Gamma: Σ wᵢ·Γᵢ
    pub composite: f64,
    /// Action entropy component (Γ_a)
    pub entropy: f64,
    /// Resource velocity component (Γ_r)
    pub velocity: f64,
    /// Scope expansion component (Γ_s)
    pub scope: f64,
    /// Reversibility index component (Γ_i)
    pub reversibility: f64,
    /// Human latency component (Γ_h)
    pub human_latency: f64,
    /// Timestamp of computation
    pub computed_at: DateTime<Utc>,
}

/// Record of a single action for trajectory analysis.
#[derive(Debug, Clone)]
struct ActionRecord {
    /// Action identifier (e.g., "read_file", "delete_record")
    action_type: String,
    /// Whether the action is reversible
    reversible: bool,
    /// Timestamp
    timestamp: DateTime<Utc>,
}

/// The Trajectory Monitor component.
/// 
/// This is the second major component in the Sentinel architecture.
/// It observes agent behavior and computes the Gamma score.
pub struct TrajectoryMonitor {
    /// Gamma weights
    weights: GammaWeights,
    /// Rolling window of recent actions
    action_history: VecDeque<ActionRecord>,
    /// Maximum history size
    history_size: usize,
    /// Timestamp of last human checkpoint
    last_human_checkpoint: DateTime<Utc>,
    /// Baseline action distribution (for entropy calculation)
    baseline_actions: std::collections::HashMap<String, u64>,
    /// Original task scope (action types at initialization)
    original_scope: std::collections::HashSet<String>,
}

impl TrajectoryMonitor {
    /// Create a new trajectory monitor with given weights.
    pub fn new(weights: GammaWeights) -> Self {
        Self {
            weights,
            action_history: VecDeque::with_capacity(1000),
            history_size: 1000,
            last_human_checkpoint: Utc::now(),
            baseline_actions: std::collections::HashMap::new(),
            original_scope: std::collections::HashSet::new(),
        }
    }

    /// Record an action for trajectory analysis.
    pub fn record_action(&mut self, action_type: &str, reversible: bool) {
        let record = ActionRecord {
            action_type: action_type.to_string(),
            reversible,
            timestamp: Utc::now(),
        };

        self.action_history.push_back(record);
        
        // Maintain window size
        while self.action_history.len() > self.history_size {
            self.action_history.pop_front();
        }

        // Update baseline
        *self.baseline_actions.entry(action_type.to_string()).or_insert(0) += 1;
    }

    /// Record a human checkpoint (resets human latency).
    pub fn human_checkpoint(&mut self) {
        self.last_human_checkpoint = Utc::now();
    }

    /// Set the original task scope (for scope expansion calculation).
    pub fn set_original_scope(&mut self, actions: &[&str]) {
        self.original_scope = actions.iter().map(|s| s.to_string()).collect();
    }

    /// Compute the current Gamma score.
    pub fn compute_gamma(&self) -> GammaScore {
        let now = Utc::now();
        
        let entropy = self.compute_entropy();
        let velocity = self.compute_velocity();
        let scope = self.compute_scope_expansion();
        let reversibility = self.compute_reversibility();
        let human_latency = self.compute_human_latency(now);

        let composite = 
            self.weights.w_entropy * entropy +
            self.weights.w_velocity * velocity +
            self.weights.w_scope * scope +
            self.weights.w_reversibility * reversibility +
            self.weights.w_human_latency * human_latency;

        // Clamp to [0, 1]
        let composite = composite.clamp(0.0, 1.0);

        GammaScore {
            composite,
            entropy,
            velocity,
            scope,
            reversibility,
            human_latency,
            computed_at: now,
        }
    }

    /// Compute action entropy (Γ_a).
    /// 
    /// Higher entropy = more unpredictable behavior.
    fn compute_entropy(&self) -> f64 {
        if self.action_history.is_empty() {
            return 0.0;
        }

        // Count action types in recent window
        let mut counts: std::collections::HashMap<&str, u64> = std::collections::HashMap::new();
        for action in &self.action_history {
            *counts.entry(&action.action_type).or_insert(0) += 1;
        }

        // Compute Shannon entropy
        let total = self.action_history.len() as f64;
        let mut entropy = 0.0;
        for count in counts.values() {
            let p = (*count as f64) / total;
            if p > 0.0 {
                entropy -= p * p.log2();
            }
        }

        // Normalize to [0, 1] assuming max ~5 bits of entropy
        (entropy / 5.0).clamp(0.0, 1.0)
    }

    /// Compute resource velocity (Γ_r).
    /// 
    /// Higher velocity = faster rate of action execution.
    fn compute_velocity(&self) -> f64 {
        if self.action_history.len() < 2 {
            return 0.0;
        }

        // Compute actions per second over recent window
        let window_secs = 60.0; // 1 minute window
        let now = Utc::now();
        let cutoff = now - chrono::Duration::seconds(60);

        let recent_count = self.action_history
            .iter()
            .filter(|a| a.timestamp > cutoff)
            .count();

        let rate = (recent_count as f64) / window_secs;

        // Normalize: assume 10 actions/sec is maximum concern
        (rate / 10.0).clamp(0.0, 1.0)
    }

    /// Compute scope expansion (Γ_s).
    /// 
    /// Higher = more actions outside original scope.
    fn compute_scope_expansion(&self) -> f64 {
        if self.original_scope.is_empty() || self.action_history.is_empty() {
            return 0.0;
        }

        // Count actions outside original scope
        let out_of_scope = self.action_history
            .iter()
            .filter(|a| !self.original_scope.contains(&a.action_type))
            .count();

        (out_of_scope as f64 / self.action_history.len() as f64).clamp(0.0, 1.0)
    }

    /// Compute reversibility index (Γ_i).
    /// 
    /// Higher = more irreversible actions recently.
    fn compute_reversibility(&self) -> f64 {
        if self.action_history.is_empty() {
            return 0.0;
        }

        let irreversible_count = self.action_history
            .iter()
            .filter(|a| !a.reversible)
            .count();

        (irreversible_count as f64 / self.action_history.len() as f64).clamp(0.0, 1.0)
    }

    /// Compute human latency (Γ_h).
    /// 
    /// Higher = longer since human oversight.
    fn compute_human_latency(&self, now: DateTime<Utc>) -> f64 {
        let elapsed = now.signed_duration_since(self.last_human_checkpoint);
        let hours = elapsed.num_seconds() as f64 / 3600.0;

        // Normalize: assume 8 hours without contact is maximum concern
        (hours / 8.0).clamp(0.0, 1.0)
    }

    /// Get the current action count.
    pub fn action_count(&self) -> usize {
        self.action_history.len()
    }

    /// Get component weights.
    pub fn weights(&self) -> &GammaWeights {
        &self.weights
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_gamma_weights_default_sum() {
        let weights = GammaWeights::default();
        assert!(weights.validate(), "Default weights should sum to 1.0");
    }

    #[test]
    fn test_empty_monitor_gamma() {
        let monitor = TrajectoryMonitor::new(GammaWeights::default());
        let gamma = monitor.compute_gamma();
        assert!(gamma.composite >= 0.0 && gamma.composite <= 1.0);
    }

    #[test]
    fn test_irreversible_actions_increase_gamma() {
        let mut monitor = TrajectoryMonitor::new(GammaWeights::default());
        
        // Record many irreversible actions
        for i in 0..50 {
            monitor.record_action(&format!("delete_{}", i), false);
        }
        
        let gamma = monitor.compute_gamma();
        assert!(gamma.reversibility > 0.5, "Many irreversible actions should elevate reversibility component");
    }

    #[test]
    fn test_human_checkpoint_resets_latency() {
        let mut monitor = TrajectoryMonitor::new(GammaWeights::default());
        
        let gamma_before = monitor.compute_gamma();
        monitor.human_checkpoint();
        let gamma_after = monitor.compute_gamma();
        
        assert!(gamma_after.human_latency <= gamma_before.human_latency);
    }

    #[test]
    fn test_scope_expansion() {
        let mut monitor = TrajectoryMonitor::new(GammaWeights::default());
        monitor.set_original_scope(&["read_file", "write_file"]);
        
        // Actions within scope
        monitor.record_action("read_file", true);
        monitor.record_action("write_file", true);
        
        let gamma_in_scope = monitor.compute_gamma();
        
        // Actions outside scope
        monitor.record_action("delete_database", false);
        monitor.record_action("send_email", false);
        
        let gamma_out_of_scope = monitor.compute_gamma();
        
        assert!(gamma_out_of_scope.scope > gamma_in_scope.scope);
    }
}
