use std::fmt;

/// Diagnostic severity level
#[derive(Debug, Clone, PartialEq)]
#[allow(dead_code)]
pub enum Severity {
    Error,
    Warning,
    Info,
}

impl fmt::Display for Severity {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Severity::Error => write!(f, "ERROR"),
            Severity::Warning => write!(f, "WARN"),
            Severity::Info => write!(f, "INFO"),
        }
    }
}

/// A diagnostic message from a pipeline stage
#[derive(Debug, Clone)]
#[allow(dead_code)]
pub struct Diagnostic {
    pub severity: Severity,
    pub stage: String,
    pub message: String,
}

impl Diagnostic {
    #[allow(dead_code)]
    pub fn error(stage: impl Into<String>, message: impl Into<String>) -> Self {
        Self {
            severity: Severity::Error,
            stage: stage.into(),
            message: message.into(),
        }
    }
}

impl fmt::Display for Diagnostic {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(f, "[{}] {}: {}", self.severity, self.stage, self.message)
    }
}

/// Pipeline execution error
#[derive(Debug)]
pub enum PlaygroundError {
    /// Source file could not be read
    #[allow(dead_code)]
    SourceNotFound(String),
    /// Python runtime not available or failed to start
    RuntimeError(String),
    /// Pipeline stage returned a failure result
    PipelineFailure { stage: String, details: String },
}

impl fmt::Display for PlaygroundError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            PlaygroundError::SourceNotFound(path) => {
                write!(f, "source file not found: {}", path)
            }
            PlaygroundError::RuntimeError(msg) => {
                write!(f, "runtime error: {}", msg)
            }
            PlaygroundError::PipelineFailure { stage, details } => {
                write!(f, "{} failed: {}", stage, details)
            }
        }
    }
}

impl std::error::Error for PlaygroundError {}
