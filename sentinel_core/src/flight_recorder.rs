//! Flight Recorder implementation.
//! 
//! This module implements immutable logging as described in EGD Chapter 4.
//! Hash-chained entries provide tamper evidence; Merkle roots enable anchoring.

use sha2::{Sha256, Digest};
use chrono::{DateTime, Utc};
use serde::{Serialize, Deserialize};
use crate::simplex::SimplexDecision;
use crate::error::SentinelError;

/// Types of log entries.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum LogEntryType {
    /// An action was attempted
    ActionAttempt { action: String },
    /// An action was executed
    ActionExecuted { action: String, success: bool },
    /// Gamma score was computed
    GammaUpdate { gamma: f64 },
    /// Intervention decision was made
    Intervention { decision: SimplexDecision },
    /// Human checkpoint occurred
    HumanCheckpoint { operator_id: Option<String> },
    /// Context was verified
    ContextVerification { valid: bool },
    /// System event
    SystemEvent { event: String },
}

/// A single log entry in the flight recorder.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct LogEntry {
    /// Sequence number
    pub sequence: u64,
    /// Timestamp
    pub timestamp: DateTime<Utc>,
    /// Entry type and payload
    pub entry_type: LogEntryType,
    /// Hash of the previous entry (creates chain)
    pub previous_hash: [u8; 32],
    /// Hash of this entry
    pub hash: [u8; 32],
}

impl LogEntry {
    /// Compute the hash of this entry.
    fn compute_hash(
        sequence: u64,
        timestamp: &DateTime<Utc>,
        entry_type: &LogEntryType,
        previous_hash: &[u8; 32],
    ) -> [u8; 32] {
        let mut hasher = Sha256::new();
        hasher.update(&sequence.to_le_bytes());
        hasher.update(timestamp.to_rfc3339().as_bytes());
        hasher.update(&serde_json::to_vec(entry_type).unwrap_or_default());
        hasher.update(previous_hash);
        
        let result = hasher.finalize();
        let mut hash = [0u8; 32];
        hash.copy_from_slice(&result);
        hash
    }

    /// Verify the hash of this entry.
    pub fn verify(&self) -> bool {
        let computed = Self::compute_hash(
            self.sequence,
            &self.timestamp,
            &self.entry_type,
            &self.previous_hash,
        );
        computed == self.hash
    }
}

/// The Flight Recorder component.
/// 
/// This is the fourth major component in the Sentinel architecture.
/// It provides tamper-evident, non-repudiable logging of all governance events.
pub struct FlightRecorder {
    /// Log entries (in production, this would be persistent storage)
    entries: Vec<LogEntry>,
    /// Hash of the most recent entry
    last_hash: [u8; 32],
    /// Current sequence number
    sequence: u64,
}

impl FlightRecorder {
    /// Create a new flight recorder.
    pub fn new() -> Self {
        Self {
            entries: Vec::new(),
            last_hash: [0u8; 32], // Genesis hash
            sequence: 0,
        }
    }

    /// Append an entry to the log.
    fn append(&mut self, entry_type: LogEntryType) -> Result<&LogEntry, SentinelError> {
        let timestamp = Utc::now();
        let hash = LogEntry::compute_hash(
            self.sequence,
            &timestamp,
            &entry_type,
            &self.last_hash,
        );

        let entry = LogEntry {
            sequence: self.sequence,
            timestamp,
            entry_type,
            previous_hash: self.last_hash,
            hash,
        };

        self.entries.push(entry);
        self.last_hash = hash;
        self.sequence += 1;

        Ok(self.entries.last().unwrap())
    }

    /// Log an action attempt.
    pub fn log_action(&mut self, action: &str) -> Result<(), SentinelError> {
        self.append(LogEntryType::ActionAttempt {
            action: action.to_string(),
        })?;
        Ok(())
    }

    /// Log an action execution result.
    pub fn log_execution(&mut self, action: &str, success: bool) -> Result<(), SentinelError> {
        self.append(LogEntryType::ActionExecuted {
            action: action.to_string(),
            success,
        })?;
        Ok(())
    }

    /// Log a Gamma score computation.
    pub fn log_gamma(&mut self, gamma: f64) -> Result<(), SentinelError> {
        self.append(LogEntryType::GammaUpdate { gamma })?;
        Ok(())
    }

    /// Log an intervention decision.
    pub fn log_intervention(&mut self, decision: &SimplexDecision) -> Result<(), SentinelError> {
        self.append(LogEntryType::Intervention {
            decision: decision.clone(),
        })?;
        Ok(())
    }

    /// Log a human checkpoint.
    pub fn log_human_checkpoint(&mut self, operator_id: Option<&str>) -> Result<(), SentinelError> {
        self.append(LogEntryType::HumanCheckpoint {
            operator_id: operator_id.map(String::from),
        })?;
        Ok(())
    }

    /// Log a context verification result.
    pub fn log_context_verification(&mut self, valid: bool) -> Result<(), SentinelError> {
        self.append(LogEntryType::ContextVerification { valid })?;
        Ok(())
    }

    /// Log a system event.
    pub fn log_system_event(&mut self, event: &str) -> Result<(), SentinelError> {
        self.append(LogEntryType::SystemEvent {
            event: event.to_string(),
        })?;
        Ok(())
    }

    /// Verify the integrity of the entire chain.
    pub fn verify_chain(&self) -> bool {
        if self.entries.is_empty() {
            return true;
        }

        // Verify each entry
        for entry in &self.entries {
            if !entry.verify() {
                return false;
            }
        }

        // Verify chain linkage
        let mut expected_prev = [0u8; 32];
        for entry in &self.entries {
            if entry.previous_hash != expected_prev {
                return false;
            }
            expected_prev = entry.hash;
        }

        true
    }

    /// Compute a Merkle root over a range of entries.
    /// 
    /// This root can be anchored to a transparency log or blockchain.
    pub fn compute_merkle_root(&self, start: usize, end: usize) -> Option<[u8; 32]> {
        if start >= end || end > self.entries.len() {
            return None;
        }

        let hashes: Vec<[u8; 32]> = self.entries[start..end]
            .iter()
            .map(|e| e.hash)
            .collect();

        Some(Self::merkle_root(&hashes))
    }

    /// Compute Merkle root from a list of hashes.
    fn merkle_root(hashes: &[[u8; 32]]) -> [u8; 32] {
        if hashes.is_empty() {
            return [0u8; 32];
        }
        if hashes.len() == 1 {
            return hashes[0];
        }

        let mut level = hashes.to_vec();
        
        while level.len() > 1 {
            let mut next_level = Vec::new();
            
            for chunk in level.chunks(2) {
                let mut hasher = Sha256::new();
                hasher.update(&chunk[0]);
                if chunk.len() > 1 {
                    hasher.update(&chunk[1]);
                } else {
                    hasher.update(&chunk[0]); // Duplicate if odd
                }
                
                let result = hasher.finalize();
                let mut hash = [0u8; 32];
                hash.copy_from_slice(&result);
                next_level.push(hash);
            }
            
            level = next_level;
        }

        level[0]
    }

    /// Get the number of entries.
    pub fn len(&self) -> usize {
        self.entries.len()
    }

    /// Check if the recorder is empty.
    pub fn is_empty(&self) -> bool {
        self.entries.is_empty()
    }

    /// Get the latest entry.
    pub fn latest(&self) -> Option<&LogEntry> {
        self.entries.last()
    }

    /// Get entries in a time range.
    pub fn entries_between(
        &self,
        start: DateTime<Utc>,
        end: DateTime<Utc>,
    ) -> Vec<&LogEntry> {
        self.entries
            .iter()
            .filter(|e| e.timestamp >= start && e.timestamp <= end)
            .collect()
    }

    /// Export entries as JSON.
    pub fn export_json(&self) -> Result<String, SentinelError> {
        serde_json::to_string_pretty(&self.entries)
            .map_err(|e| SentinelError::SerializationError(e.to_string()))
    }
}

impl Default for FlightRecorder {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_empty_chain_valid() {
        let recorder = FlightRecorder::new();
        assert!(recorder.verify_chain());
    }

    #[test]
    fn test_chain_integrity() {
        let mut recorder = FlightRecorder::new();
        
        recorder.log_action("action1").unwrap();
        recorder.log_gamma(0.3).unwrap();
        recorder.log_action("action2").unwrap();
        
        assert!(recorder.verify_chain());
    }

    #[test]
    fn test_entry_verification() {
        let mut recorder = FlightRecorder::new();
        recorder.log_action("test").unwrap();
        
        let entry = recorder.latest().unwrap();
        assert!(entry.verify());
    }

    #[test]
    fn test_merkle_root() {
        let mut recorder = FlightRecorder::new();
        
        for i in 0..8 {
            recorder.log_action(&format!("action_{}", i)).unwrap();
        }
        
        let root = recorder.compute_merkle_root(0, 8);
        assert!(root.is_some());
    }

    #[test]
    fn test_export_json() {
        let mut recorder = FlightRecorder::new();
        recorder.log_action("test").unwrap();
        
        let json = recorder.export_json().unwrap();
        assert!(json.contains("ActionAttempt"));
    }
}
