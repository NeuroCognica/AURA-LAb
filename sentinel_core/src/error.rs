//! Error types for Sentinel.

use thiserror::Error;

/// Errors that can occur in Sentinel operations.
#[derive(Error, Debug)]
pub enum SentinelError {
    /// HKDF key derivation failed
    #[error("Key derivation failed")]
    KeyDerivationFailed,

    /// Context validation failed
    #[error("Context validation failed: {0}")]
    ContextValidationFailed(String),

    /// Capability expired
    #[error("Capability expired at {0}")]
    CapabilityExpired(u64),

    /// Context mismatch
    #[error("Context mismatch: expected {expected}, got {actual}")]
    ContextMismatch {
        expected: String,
        actual: String,
    },

    /// Rate limit exceeded
    #[error("Rate limit exceeded, retry after {retry_after_ms}ms")]
    RateLimitExceeded {
        retry_after_ms: u64,
    },

    /// Governance level prohibits action
    #[error("Action blocked at governance level {level}")]
    ActionBlocked {
        level: u8,
    },

    /// Human confirmation required
    #[error("Human confirmation required for action: {action}")]
    ConfirmationRequired {
        action: String,
    },

    /// Serialization error
    #[error("Serialization error: {0}")]
    SerializationError(String),

    /// Chain integrity violation
    #[error("Flight recorder chain integrity violation at sequence {sequence}")]
    ChainIntegrityViolation {
        sequence: u64,
    },

    /// Configuration error
    #[error("Configuration error: {0}")]
    ConfigurationError(String),
}

impl SentinelError {
    /// Check if this error indicates a blocked action.
    pub fn is_blocked(&self) -> bool {
        matches!(self, Self::ActionBlocked { .. })
    }

    /// Check if this error requires human intervention.
    pub fn requires_human(&self) -> bool {
        matches!(self, Self::ConfirmationRequired { .. })
    }

    /// Check if this error is retryable after a delay.
    pub fn is_retryable(&self) -> bool {
        matches!(self, Self::RateLimitExceeded { .. })
    }

    /// Get the retry delay if applicable.
    pub fn retry_after_ms(&self) -> Option<u64> {
        match self {
            Self::RateLimitExceeded { retry_after_ms } => Some(*retry_after_ms),
            _ => None,
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_error_display() {
        let err = SentinelError::ActionBlocked { level: 5 };
        assert!(err.to_string().contains("blocked"));
    }

    #[test]
    fn test_error_classification() {
        let blocked = SentinelError::ActionBlocked { level: 5 };
        assert!(blocked.is_blocked());

        let rate_limited = SentinelError::RateLimitExceeded { retry_after_ms: 1000 };
        assert!(rate_limited.is_retryable());
        assert_eq!(rate_limited.retry_after_ms(), Some(1000));
    }
}
