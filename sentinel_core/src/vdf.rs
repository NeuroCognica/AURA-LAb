//! Verifiable Delay Function (VDF) implementation.
//! 
//! This module implements rate shaping as described in EGD Chapter 2.
//! VDFs impose temporal cost that cannot be parallelized.

use sha2::{Sha256, Digest};
use serde::{Serialize, Deserialize};
use std::time::{Duration, Instant};

/// A VDF proof demonstrating that sequential computation was performed.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct VdfProof {
    /// The input to the VDF
    pub input: [u8; 32],
    /// The output after T iterations
    pub output: [u8; 32],
    /// Number of iterations performed
    pub iterations: u64,
    /// Claimed computation time in milliseconds
    pub computation_time_ms: u64,
}

impl VdfProof {
    /// Verify that a VDF proof is valid.
    /// 
    /// This is O(T) verification - in production, you would use
    /// a VDF construction with O(log T) verification (e.g., Wesolowski).
    /// This skeleton uses iterated hashing for simplicity.
    pub fn verify(&self) -> bool {
        let mut current = self.input;
        
        for _ in 0..self.iterations {
            let mut hasher = Sha256::new();
            hasher.update(&current);
            let result = hasher.finalize();
            current.copy_from_slice(&result);
        }
        
        current == self.output
    }
}

/// Rate shaper using VDF-like delays.
/// 
/// This is a simplified implementation. In production, you would use
/// a proper VDF construction (e.g., repeated squaring in a group of
/// unknown order, or Wesolowski/Pietrzak proofs).
/// 
/// The key property we preserve: delay is sequential and cannot be
/// parallelized.
pub struct RateShaper {
    /// Target delay in milliseconds
    target_delay_ms: u64,
    /// Iterations calibrated to achieve target delay
    iterations: u64,
    /// Last evaluation time (for tracking)
    last_evaluation: Option<Instant>,
}

impl RateShaper {
    /// Create a new rate shaper with target delay in milliseconds.
    pub fn new(target_delay_ms: u64) -> Self {
        // Calibrate iterations to achieve target delay
        // This is approximate; real calibration would measure actual hardware
        let iterations = Self::calibrate(target_delay_ms);
        
        Self {
            target_delay_ms,
            iterations,
            last_evaluation: None,
        }
    }

    /// Calibrate iterations for target delay.
    /// 
    /// In production, this would run a timing loop. Here we use
    /// a rough approximation: ~1M hashes per second on typical hardware.
    fn calibrate(target_delay_ms: u64) -> u64 {
        // Approximate: 1 million iterations ≈ 1 second
        // This is hardware-dependent and should be measured
        (target_delay_ms as u64) * 1000
    }

    /// Evaluate the VDF (impose delay).
    /// 
    /// Returns a proof that the delay was performed.
    pub fn evaluate(&mut self, input: &[u8]) -> VdfProof {
        let start = Instant::now();
        
        // Create initial hash from input
        let mut current = {
            let mut hasher = Sha256::new();
            hasher.update(input);
            let result = hasher.finalize();
            let mut hash = [0u8; 32];
            hash.copy_from_slice(&result);
            hash
        };
        
        let input_hash = current;
        
        // Sequential iteration (cannot be parallelized)
        for _ in 0..self.iterations {
            let mut hasher = Sha256::new();
            hasher.update(&current);
            let result = hasher.finalize();
            current.copy_from_slice(&result);
        }
        
        let elapsed = start.elapsed();
        self.last_evaluation = Some(start);
        
        VdfProof {
            input: input_hash,
            output: current,
            iterations: self.iterations,
            computation_time_ms: elapsed.as_millis() as u64,
        }
    }

    /// Evaluate with minimum enforced delay.
    /// 
    /// If VDF computation completes faster than target, sleep the remainder.
    /// This ensures consistent timing even with fast hardware.
    pub fn evaluate_with_minimum_delay(&mut self, input: &[u8]) -> VdfProof {
        let start = Instant::now();
        let proof = self.evaluate(input);
        
        let elapsed = start.elapsed();
        let target = Duration::from_millis(self.target_delay_ms);
        
        if elapsed < target {
            std::thread::sleep(target - elapsed);
        }
        
        proof
    }

    /// Check if rate limit allows an operation.
    /// 
    /// Returns Ok(()) if sufficient time has passed since last operation.
    /// Returns Err with remaining wait time if rate limited.
    pub fn check_rate_limit(&self) -> Result<(), Duration> {
        match self.last_evaluation {
            None => Ok(()),
            Some(last) => {
                let elapsed = last.elapsed();
                let target = Duration::from_millis(self.target_delay_ms);
                
                if elapsed >= target {
                    Ok(())
                } else {
                    Err(target - elapsed)
                }
            }
        }
    }

    /// Get the target delay.
    pub fn target_delay(&self) -> Duration {
        Duration::from_millis(self.target_delay_ms)
    }

    /// Get the configured iteration count.
    pub fn iterations(&self) -> u64 {
        self.iterations
    }
}

/// Rate limit configuration for different operation classes.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct RateLimitConfig {
    /// Delay for low-risk operations (ms)
    pub low_risk_delay_ms: u64,
    /// Delay for medium-risk operations (ms)
    pub medium_risk_delay_ms: u64,
    /// Delay for high-risk operations (ms)
    pub high_risk_delay_ms: u64,
    /// Delay for irreversible operations (ms)
    pub irreversible_delay_ms: u64,
}

impl Default for RateLimitConfig {
    fn default() -> Self {
        Self {
            low_risk_delay_ms: 100,       // 100ms - barely noticeable
            medium_risk_delay_ms: 1000,   // 1 second
            high_risk_delay_ms: 5000,     // 5 seconds  
            irreversible_delay_ms: 30000, // 30 seconds - time for human review
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_vdf_proof_deterministic() {
        let mut shaper = RateShaper::new(1); // 1ms target
        
        let proof1 = shaper.evaluate(b"test input");
        let proof2 = shaper.evaluate(b"test input");
        
        // Same input should produce same output
        assert_eq!(proof1.input, proof2.input);
        assert_eq!(proof1.output, proof2.output);
    }

    #[test]
    fn test_vdf_proof_verification() {
        let mut shaper = RateShaper::new(1);
        let proof = shaper.evaluate(b"test input");
        
        assert!(proof.verify(), "Valid proof should verify");
    }

    #[test]
    fn test_different_inputs_different_outputs() {
        let mut shaper = RateShaper::new(1);
        
        let proof1 = shaper.evaluate(b"input 1");
        let proof2 = shaper.evaluate(b"input 2");
        
        assert_ne!(proof1.output, proof2.output);
    }

    #[test]
    fn test_rate_limit_check() {
        let shaper = RateShaper::new(100);
        
        // First check should pass (no previous evaluation)
        assert!(shaper.check_rate_limit().is_ok());
    }
}
