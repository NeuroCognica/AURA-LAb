//! Context Binding (CBIG) implementation.
//! 
//! This module implements the Context-Bound Integrity Gate as described in 
//! EGD Chapter 2. Capabilities are derived from environmental state rather
//! than stored secrets alone.

use sha2::{Sha256, Digest};
use hkdf::Hkdf;
use serde::{Serialize, Deserialize};
use crate::error::SentinelError;

/// A cryptographic commitment to environmental state.
/// 
/// The context signature binds execution to:
/// - Hardware attestation (TPM measurements, enclave reports)
/// - Software state (binary hashes, configuration)
/// - Temporal bounds (validity windows)
/// - Operational parameters (approved scopes)
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct ContextSignature {
    /// Hardware attestation hash
    pub hardware_attestation: [u8; 32],
    /// Software state hash
    pub software_state: [u8; 32],
    /// Validity start timestamp (Unix epoch seconds)
    pub valid_from: u64,
    /// Validity end timestamp (Unix epoch seconds)
    pub valid_until: u64,
    /// Operational parameters hash
    pub parameters: [u8; 32],
}

impl ContextSignature {
    /// Create a new context signature from component measurements.
    pub fn new(
        hardware_attestation: [u8; 32],
        software_state: [u8; 32],
        valid_from: u64,
        valid_until: u64,
        parameters: [u8; 32],
    ) -> Self {
        Self {
            hardware_attestation,
            software_state,
            valid_from,
            valid_until,
            parameters,
        }
    }

    /// Compute the composite context hash.
    /// 
    /// C = H(h_hw || h_sw || t_start || t_end || θ)
    pub fn compute_hash(&self) -> [u8; 32] {
        let mut hasher = Sha256::new();
        hasher.update(&self.hardware_attestation);
        hasher.update(&self.software_state);
        hasher.update(&self.valid_from.to_le_bytes());
        hasher.update(&self.valid_until.to_le_bytes());
        hasher.update(&self.parameters);
        
        let result = hasher.finalize();
        let mut hash = [0u8; 32];
        hash.copy_from_slice(&result);
        hash
    }

    /// Check if the context is temporally valid.
    pub fn is_temporally_valid(&self, current_time: u64) -> bool {
        current_time >= self.valid_from && current_time <= self.valid_until
    }
}

/// A derived capability key.
/// 
/// This key is never stored—it is computed from master key material
/// and the context signature. If context changes, key derivation fails.
#[derive(Debug, Clone)]
pub struct CapabilityKey {
    key: [u8; 32],
}

impl CapabilityKey {
    /// Derive a capability key from master key and context.
    /// 
    /// K_cap = HKDF(K_master, C, info)
    pub fn derive(
        master_key: &[u8; 32],
        context: &ContextSignature,
        info: &[u8],
    ) -> Result<Self, SentinelError> {
        let context_hash = context.compute_hash();
        
        let hk = Hkdf::<Sha256>::new(Some(&context_hash), master_key);
        let mut key = [0u8; 32];
        hk.expand(info, &mut key)
            .map_err(|_| SentinelError::KeyDerivationFailed)?;
        
        Ok(Self { key })
    }

    /// Get the raw key bytes.
    pub fn as_bytes(&self) -> &[u8; 32] {
        &self.key
    }

    /// Verify that a context matches the expected context.
    /// 
    /// This is the runtime check: measure current context, derive key,
    /// verify it matches expected key.
    pub fn verify_context(
        &self,
        master_key: &[u8; 32],
        current_context: &ContextSignature,
        info: &[u8],
    ) -> bool {
        match CapabilityKey::derive(master_key, current_context, info) {
            Ok(derived) => derived.key == self.key,
            Err(_) => false,
        }
    }
}

/// The Context Evaluator component.
/// 
/// This is the first component in the Sentinel architecture.
/// It measures environmental state and derives capability keys.
pub struct ContextEvaluator {
    master_key: [u8; 32],
}

impl ContextEvaluator {
    /// Create a new context evaluator with the given master key.
    pub fn new(master_key: [u8; 32]) -> Self {
        Self { master_key }
    }

    /// Measure the current hardware attestation.
    /// 
    /// In production, this would query TPM 2.0 or secure enclave.
    /// This skeleton returns a placeholder measurement.
    pub fn measure_hardware(&self) -> [u8; 32] {
        // PLACEHOLDER: In production, query TPM/enclave
        let mut hasher = Sha256::new();
        hasher.update(b"hardware_attestation_placeholder");
        let result = hasher.finalize();
        let mut hash = [0u8; 32];
        hash.copy_from_slice(&result);
        hash
    }

    /// Measure the current software state.
    /// 
    /// In production, this would hash loaded binaries and configuration.
    /// This skeleton returns a placeholder measurement.
    pub fn measure_software(&self) -> [u8; 32] {
        // PLACEHOLDER: In production, hash loaded binaries
        let mut hasher = Sha256::new();
        hasher.update(b"software_state_placeholder");
        let result = hasher.finalize();
        let mut hash = [0u8; 32];
        hash.copy_from_slice(&result);
        hash
    }

    /// Measure the current operational parameters.
    pub fn measure_parameters(&self, params: &[u8]) -> [u8; 32] {
        let mut hasher = Sha256::new();
        hasher.update(params);
        let result = hasher.finalize();
        let mut hash = [0u8; 32];
        hash.copy_from_slice(&result);
        hash
    }

    /// Capture the current context.
    pub fn capture_context(
        &self,
        valid_from: u64,
        valid_until: u64,
        params: &[u8],
    ) -> ContextSignature {
        ContextSignature::new(
            self.measure_hardware(),
            self.measure_software(),
            valid_from,
            valid_until,
            self.measure_parameters(params),
        )
    }

    /// Issue a capability for the current context.
    pub fn issue_capability(
        &self,
        valid_from: u64,
        valid_until: u64,
        params: &[u8],
        info: &[u8],
    ) -> Result<(ContextSignature, CapabilityKey), SentinelError> {
        let context = self.capture_context(valid_from, valid_until, params);
        let key = CapabilityKey::derive(&self.master_key, &context, info)?;
        Ok((context, key))
    }

    /// Verify that a capability is valid in the current context.
    pub fn verify_capability(
        &self,
        expected_context: &ContextSignature,
        capability: &CapabilityKey,
        info: &[u8],
        current_time: u64,
    ) -> Result<bool, SentinelError> {
        // Check temporal validity
        if !expected_context.is_temporally_valid(current_time) {
            return Ok(false);
        }

        // Measure current context
        let current_context = self.capture_context(
            expected_context.valid_from,
            expected_context.valid_until,
            &expected_context.parameters, // Use expected params for comparison
        );

        // Verify context match through key derivation
        Ok(capability.verify_context(&self.master_key, &current_context, info))
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_context_signature_hash() {
        let ctx = ContextSignature::new(
            [1u8; 32],
            [2u8; 32],
            1000,
            2000,
            [3u8; 32],
        );
        
        let hash1 = ctx.compute_hash();
        let hash2 = ctx.compute_hash();
        assert_eq!(hash1, hash2, "Hash should be deterministic");
    }

    #[test]
    fn test_capability_derivation() {
        let master_key = [0u8; 32];
        let ctx = ContextSignature::new(
            [1u8; 32],
            [2u8; 32],
            1000,
            2000,
            [3u8; 32],
        );
        
        let key1 = CapabilityKey::derive(&master_key, &ctx, b"test").unwrap();
        let key2 = CapabilityKey::derive(&master_key, &ctx, b"test").unwrap();
        
        assert_eq!(key1.as_bytes(), key2.as_bytes(), "Same inputs should derive same key");
    }

    #[test]
    fn test_context_change_invalidates_capability() {
        let master_key = [0u8; 32];
        let ctx1 = ContextSignature::new(
            [1u8; 32],
            [2u8; 32],
            1000,
            2000,
            [3u8; 32],
        );
        let ctx2 = ContextSignature::new(
            [1u8; 32],
            [9u8; 32], // Different software state
            1000,
            2000,
            [3u8; 32],
        );
        
        let key1 = CapabilityKey::derive(&master_key, &ctx1, b"test").unwrap();
        
        // Key derived from different context should not match
        assert!(!key1.verify_context(&master_key, &ctx2, b"test"));
    }

    #[test]
    fn test_temporal_validity() {
        let ctx = ContextSignature::new(
            [1u8; 32],
            [2u8; 32],
            1000,
            2000,
            [3u8; 32],
        );
        
        assert!(!ctx.is_temporally_valid(500), "Before valid_from");
        assert!(ctx.is_temporally_valid(1500), "Within window");
        assert!(!ctx.is_temporally_valid(2500), "After valid_until");
    }
}
