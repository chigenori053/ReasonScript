mod cli;
mod commands;
mod diagnostics;
mod output;

use clap::Parser;
use cli::{Cli, Commands};

fn main() {
    let cli = Cli::parse();

    let result = match &cli.command {
        Commands::Parse { source, format } => commands::parse::run(source, format),
        Commands::Ast { source, format } => commands::ast::run(source, format),
        Commands::Semantic { source, format } => commands::semantic::run(source, format),
        Commands::Ir { source, format } => commands::ir::run(source, format),
        Commands::Validate { source, format } => commands::validate::run(source, format),
        Commands::Run { source, format } => commands::invoke_pipeline("run", source, format),
    };

    if let Err(e) = result {
        eprintln!("Error: {}", e);
        std::process::exit(1);
    }
}
