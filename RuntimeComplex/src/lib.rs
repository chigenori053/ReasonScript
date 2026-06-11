pub mod core;
pub mod runtime;

pub struct ComplexReasonUnit {
    pub label: String,
}

impl ComplexReasonUnit {
    pub fn new(label: &str) -> Self {
        Self {
            label: label.to_string(),
        }
    }
}
