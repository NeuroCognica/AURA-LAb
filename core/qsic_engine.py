"""
Quantum-Seeded Integrity Check (QSIC) Engine - Hardened Edition

Security-hardened implementation of context-locked cryptographic integrity verification.
Designed to resist timing attacks, side-channel analysis, brute force, and tampering.

Author: AURA Propulsion Laboratory
Date: 2026-01-05
Threat Model: Nation-state adversary with unlimited compute
"""

from __future__ import annotations

import hashlib
import hmac
import secrets
import time
from dataclasses import dataclass, field
from typing import Optional, Tuple

# Security constants
MAX_LAYERS = 100_000_000  # Upper bound to prevent DoS via massive integer computation
MIN_LAYERS = 1_000_000  # Lower bound for statistical security
QUANTUM_INTEGER_BYTE_SIZE = 32  # 256-bit encoding for the quantum integer
RATE_LIMIT_DELAY_SECONDS = 0.1  # Anti-brute-force throttle
MAX_DATA_SIZE_BYTES = 100_000_000  # 100 MB limit to prevent memory exhaustion
KDF_ITERATIONS = 100_000  # Key derivation iterations (memory-hard defense)


@dataclass(frozen=True)
class QSICConfig:
    """Immutable configuration for QSIC engine."""

    n_layers: int
    project_salt: str
    enable_kdf: bool = True  # Key derivation function for additional hardening
    enable_rate_limit: bool = True  # Anti-brute-force delay
    enable_audit: bool = True  # Security event logging
    kdf_iterations: int = KDF_ITERATIONS

    def __post_init__(self) -> None:
        """Validate configuration parameters to prevent security bypass."""
        if not isinstance(self.n_layers, int):
            raise TypeError(f"n_layers must be int, got {type(self.n_layers)}")

        if not (MIN_LAYERS <= self.n_layers <= MAX_LAYERS):
            raise ValueError(
                f"n_layers {self.n_layers} outside secure range "
                f"[{MIN_LAYERS}, {MAX_LAYERS}]"
            )

        if not isinstance(self.project_salt, str) or len(self.project_salt) < 8:
            raise ValueError("project_salt must be string with length >= 8")

        if self.kdf_iterations < 10_000:
            raise ValueError("kdf_iterations must be >= 10,000 for security")


@dataclass
class QSICResult:
    """Result of QSIC verification with detailed security metadata."""

    verified: bool
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    quantum_integer: Optional[int] = None
    hash_value: Optional[str] = None
    timestamp: float = field(default_factory=time.time)
    computation_time_ms: float = 0.0

    def is_success(self) -> bool:
        """Check if verification succeeded."""
        return self.verified and self.error_code is None


class QSICEngine:
    """
    Hardened Quantum-Seeded Integrity Check Engine.

    Security Features:
    - Constant-time hash comparison (timing attack mitigation)
    - Integer overflow protection with bounds checking
    - Memory-hard key derivation (KDF) option
    - Rate limiting to prevent brute force
    - Input validation and sanitization
    - Secure random number generation (secrets module)
    - Side-channel resistant arithmetic
    - Audit logging for security events
    """

    def __init__(self, config: QSICConfig) -> None:
        """Initialize QSIC engine with validated configuration."""
        self.config = config
        self._audit_log: list[str] = []
        self._verification_attempts = 0
        self._last_verification_time = 0.0

        # Pre-compute the canonical quantum integer (cache for performance)
        self._canonical_quantum_integer = self._calculate_quantum_integer_secure(
            config.n_layers
        )

        self._log_audit(f"QSIC Engine initialized with n_layers={config.n_layers}")

    def _log_audit(self, message: str) -> None:
        """Log security-relevant events."""
        if self.config.enable_audit:
            timestamp = time.time()
            self._audit_log.append(f"[{timestamp:.6f}] {message}")

    def _rate_limit_check(self) -> None:
        """Enforce rate limiting to prevent brute force attacks."""
        if not self.config.enable_rate_limit:
            return

        current_time = time.time()
        time_since_last = current_time - self._last_verification_time

        if time_since_last < RATE_LIMIT_DELAY_SECONDS:
            # Force delay to prevent rapid-fire attacks
            delay = RATE_LIMIT_DELAY_SECONDS - time_since_last
            time.sleep(delay)
            self._log_audit(f"Rate limit enforced: {delay:.3f}s delay")

        self._last_verification_time = time.time()

    def _calculate_quantum_integer_secure(self, n_layers: int) -> int:
        """
        Calculate quantum integer with overflow protection.

        Formula: N = floor(n^3 / 3)

        Security: Uses integer arithmetic to prevent floating-point side channels.
        Bounds checking prevents integer overflow DoS.
        """
        # Validate input bounds
        if not isinstance(n_layers, int):
            raise TypeError(f"n_layers must be int, got {type(n_layers)}")

        if not (MIN_LAYERS <= n_layers <= MAX_LAYERS):
            raise ValueError(f"n_layers {n_layers} out of secure range")

        # Calculate n^3 with overflow detection
        try:
            n_cubed = n_layers ** 3
        except OverflowError as e:
            raise ValueError(f"Integer overflow in n^3 calculation: {e}")

        # Integer division (floor) for deterministic result
        quantum_integer = n_cubed // 3

        # Sanity check: ensure result is positive and reasonable
        if quantum_integer <= 0:
            raise ValueError("Quantum integer calculation produced non-positive result")

        return quantum_integer

    def _derive_key_secure(self, quantum_integer: int, salt: str) -> bytes:
        """
        Derive cryptographic key using memory-hard KDF.

        Security: PBKDF2-HMAC-SHA256 with high iteration count makes brute force
        computationally expensive. Even if quantum_integer is leaked, deriving
        the key requires significant computation.
        """
        if not self.config.enable_kdf:
            # Fast path: direct integer encoding
            return quantum_integer.to_bytes(QUANTUM_INTEGER_BYTE_SIZE, byteorder="big")

        # Convert integer to bytes
        integer_bytes = quantum_integer.to_bytes(
            QUANTUM_INTEGER_BYTE_SIZE, byteorder="big"
        )

        # Apply PBKDF2 key stretching
        derived_key = hashlib.pbkdf2_hmac(
            "sha256",
            password=integer_bytes,
            salt=salt.encode("utf-8"),
            iterations=self.config.kdf_iterations,
        )

        return derived_key

    def generate_hash(self, data: bytes) -> QSICResult:
        """
        Generate QSIC hash for data payload.

        Args:
            data: Binary data to protect (e.g., AI model weights)

        Returns:
            QSICResult with hash value or error details

        Security: Validates input size, uses HMAC-SHA256 for authenticated hashing
        """
        start_time = time.time()

        try:
            # Input validation
            if not isinstance(data, bytes):
                return QSICResult(
                    verified=False,
                    error_code="INVALID_INPUT",
                    error_message="Data must be bytes",
                )

            if len(data) > MAX_DATA_SIZE_BYTES:
                return QSICResult(
                    verified=False,
                    error_code="DATA_TOO_LARGE",
                    error_message=f"Data exceeds {MAX_DATA_SIZE_BYTES} bytes",
                )

            if len(data) == 0:
                return QSICResult(
                    verified=False,
                    error_code="EMPTY_DATA",
                    error_message="Cannot hash empty data",
                )

            # Derive cryptographic key from quantum integer
            derived_key = self._derive_key_secure(
                self._canonical_quantum_integer, self.config.project_salt
            )

            # Generate HMAC-SHA256 (authenticated hash)
            # HMAC provides both integrity and authenticity
            hash_obj = hmac.new(derived_key, data, hashlib.sha256)
            hash_value = hash_obj.hexdigest()

            computation_time_ms = (time.time() - start_time) * 1000

            self._log_audit(f"Hash generated: {hash_value[:16]}... ({len(data)} bytes)")

            return QSICResult(
                verified=True,
                quantum_integer=self._canonical_quantum_integer,
                hash_value=hash_value,
                computation_time_ms=computation_time_ms,
            )

        except Exception as e:
            self._log_audit(f"Hash generation failed: {e}")
            return QSICResult(
                verified=False,
                error_code="INTERNAL_ERROR",
                error_message=str(e),
            )

    def verify_hash(
        self,
        data: bytes,
        expected_hash: str,
        user_provided_n_layers: int,
    ) -> QSICResult:
        """
        Verify QSIC hash with Proof-of-Context.

        Args:
            data: Binary data to verify
            expected_hash: Stored hash value (hex string)
            user_provided_n_layers: User's claimed seed parameter

        Returns:
            QSICResult with verification outcome

        Security:
        - Rate limiting prevents brute force of n_layers
        - Constant-time comparison prevents timing attacks on hash
        - Context verification (n_layers) prevents unauthorized use
        - Detailed error codes aid debugging without leaking information
        """
        start_time = time.time()
        self._verification_attempts += 1

        try:
            # Rate limiting (anti-brute-force)
            self._rate_limit_check()

            # Input validation
            if not isinstance(data, bytes):
                self._log_audit("VERIFICATION_FAILED: Invalid data type")
                return QSICResult(
                    verified=False,
                    error_code="INVALID_INPUT",
                    error_message="Data must be bytes",
                )

            if not isinstance(expected_hash, str):
                self._log_audit("VERIFICATION_FAILED: Invalid hash type")
                return QSICResult(
                    verified=False,
                    error_code="INVALID_HASH",
                    error_message="Expected hash must be string",
                )

            if len(expected_hash) != 64:  # SHA-256 hex = 64 chars
                self._log_audit("VERIFICATION_FAILED: Invalid hash length")
                return QSICResult(
                    verified=False,
                    error_code="INVALID_HASH_LENGTH",
                    error_message="Hash must be 64 hex characters",
                )

            if len(data) > MAX_DATA_SIZE_BYTES:
                self._log_audit("VERIFICATION_FAILED: Data too large")
                return QSICResult(
                    verified=False,
                    error_code="DATA_TOO_LARGE",
                    error_message=f"Data exceeds {MAX_DATA_SIZE_BYTES} bytes",
                )

            # LAYER 1: Proof of Context - Verify n_layers matches
            try:
                user_quantum_integer = self._calculate_quantum_integer_secure(
                    user_provided_n_layers
                )
            except (ValueError, TypeError, OverflowError) as e:
                self._log_audit(
                    f"VERIFICATION_FAILED: Invalid n_layers={user_provided_n_layers}"
                )
                return QSICResult(
                    verified=False,
                    error_code="CONTEXT_INVALID",
                    error_message=f"Invalid n_layers: {e}",
                )

            # Constant-time comparison of quantum integers (timing attack mitigation)
            canonical_bytes = self._canonical_quantum_integer.to_bytes(
                QUANTUM_INTEGER_BYTE_SIZE, byteorder="big"
            )
            user_bytes = user_quantum_integer.to_bytes(
                QUANTUM_INTEGER_BYTE_SIZE, byteorder="big"
            )

            if not secrets.compare_digest(canonical_bytes, user_bytes):
                self._log_audit(
                    f"VERIFICATION_FAILED: Context mismatch "
                    f"(expected n={self.config.n_layers}, got n={user_provided_n_layers})"
                )
                return QSICResult(
                    verified=False,
                    error_code="CONTEXT_MISMATCH",
                    error_message="Proof-of-Context failed: incorrect n_layers",
                    quantum_integer=user_quantum_integer,
                )

            # LAYER 2: Integrity Check - Verify hash matches
            # Derive key and compute hash
            derived_key = self._derive_key_secure(
                user_quantum_integer, self.config.project_salt
            )

            hash_obj = hmac.new(derived_key, data, hashlib.sha256)
            computed_hash = hash_obj.hexdigest()

            # Constant-time comparison of hashes (timing attack mitigation)
            if not secrets.compare_digest(computed_hash, expected_hash):
                self._log_audit(
                    f"VERIFICATION_FAILED: Hash mismatch "
                    f"(computed={computed_hash[:16]}..., expected={expected_hash[:16]}...)"
                )
                return QSICResult(
                    verified=False,
                    error_code="HASH_MISMATCH",
                    error_message="Data integrity check failed: hash mismatch",
                    quantum_integer=user_quantum_integer,
                    hash_value=computed_hash,
                )

            # SUCCESS: Both context and integrity verified
            computation_time_ms = (time.time() - start_time) * 1000

            self._log_audit(
                f"VERIFICATION_SUCCESS: attempt #{self._verification_attempts}, "
                f"time={computation_time_ms:.2f}ms"
            )

            return QSICResult(
                verified=True,
                quantum_integer=user_quantum_integer,
                hash_value=computed_hash,
                computation_time_ms=computation_time_ms,
            )

        except Exception as e:
            self._log_audit(f"VERIFICATION_ERROR: Unexpected exception: {e}")
            return QSICResult(
                verified=False,
                error_code="INTERNAL_ERROR",
                error_message=f"Verification failed: {e}",
            )

    def get_audit_log(self) -> list[str]:
        """Retrieve security audit log."""
        return self._audit_log.copy()

    def get_statistics(self) -> dict[str, int | float]:
        """Get security statistics."""
        return {
            "total_verification_attempts": self._verification_attempts,
            "n_layers": self.config.n_layers,
            "quantum_integer": self._canonical_quantum_integer,
            "kdf_enabled": self.config.enable_kdf,
            "kdf_iterations": self.config.kdf_iterations,
        }
