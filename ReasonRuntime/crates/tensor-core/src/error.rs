#[derive(Debug, Clone)]
pub struct TensorCoreError {
    pub code: String,
    pub message: String,
}

impl TensorCoreError {
    pub fn new(code: &str, message: impl Into<String>) -> Self {
        TensorCoreError {
            code: code.to_string(),
            message: message.into(),
        }
    }
}

pub type Result<T> = std::result::Result<T, TensorCoreError>;
