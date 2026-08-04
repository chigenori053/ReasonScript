use serde::{Deserialize, Serialize};

#[derive(Clone, Debug, Deserialize, Eq, PartialEq, Serialize)]
pub struct Diagnostic {
    pub code: String,
    pub severity: String,
    pub message: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub location: Option<String>,
}

impl Diagnostic {
    pub fn error(code: &str, message: impl Into<String>, location: impl Into<String>) -> Self {
        Self {
            code: code.into(),
            severity: "error".into(),
            message: message.into(),
            location: Some(location.into()),
        }
    }

    pub fn warning(code: &str, message: impl Into<String>, location: impl Into<String>) -> Self {
        Self {
            code: code.into(),
            severity: "warning".into(),
            message: message.into(),
            location: Some(location.into()),
        }
    }
}

pub fn sort(items: &mut [Diagnostic]) {
    items.sort_by(|a, b| {
        (&a.code, &a.location, &a.message).cmp(&(&b.code, &b.location, &b.message))
    });
}
