use clap::{Parser, Subcommand, ValueEnum};

/// ReasonScript TestPlayground v0.1
///
/// Language specification validation environment for ReasonScript.
/// Validates source files through the parse → AST → Semantic AST → Reason IR → Validation pipeline.
#[derive(Parser)]
#[command(
    name = "testplayground",
    version = "0.1.0",
    about = "ReasonScript TestPlayground v0.1 — language specification validation environment"
)]
pub struct Cli {
    #[command(subcommand)]
    pub command: Commands,
}

#[derive(Subcommand)]
pub enum Commands {
    /// Parse a ReasonScript source file and verify syntax
    Parse {
        /// Path to the .rsn source file
        source: String,
        /// Output format
        #[arg(long, value_enum, default_value = "pretty")]
        format: Format,
    },
    /// Display the AST for a ReasonScript source file
    Ast {
        /// Path to the .rsn source file
        source: String,
        /// Output format
        #[arg(long, value_enum, default_value = "json")]
        format: Format,
    },
    /// Display the Semantic AST for a ReasonScript source file
    Semantic {
        /// Path to the .rsn source file
        source: String,
        /// Output format
        #[arg(long, value_enum, default_value = "json")]
        format: Format,
    },
    /// Compile a ReasonScript source file to Reason IR
    Ir {
        /// Path to the .rsn source file
        source: String,
        /// Output format
        #[arg(long, value_enum, default_value = "json")]
        format: Format,
    },
    /// Validate a ReasonScript source file through all pipeline stages
    Validate {
        /// Path to the .rsn source file
        source: String,
        /// Output format
        #[arg(long, value_enum, default_value = "pretty")]
        format: Format,
    },
    /// Execute a ReasonScript source file through RuntimeReal
    Run {
        /// Path to the .rsn source file
        source: String,
        /// Output format
        #[arg(long, value_enum, default_value = "json")]
        format: Format,
    },
}

#[derive(ValueEnum, Clone, Debug)]
pub enum Format {
    /// JSON output
    Json,
    /// Human-readable pretty output
    Pretty,
}

impl Format {
    pub fn as_str(&self) -> &'static str {
        match self {
            Format::Json => "json",
            Format::Pretty => "pretty",
        }
    }
}
