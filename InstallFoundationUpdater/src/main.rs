//! Native, dependency-free atomic activation helper for Install Foundation v1.1.
use std::env;
use std::fs::{self, File};
use std::io::{self, Write};
use std::path::{Path, PathBuf};

fn valid_version(value: &str) -> bool {
    !value.is_empty()
        && value.len() <= 128
        && value
            .bytes()
            .all(|byte| byte.is_ascii_alphanumeric() || matches!(byte, b'.' | b'-' | b'+'))
}

fn atomic_current(root: &Path, active: &str, previous: Option<&str>) -> io::Result<()> {
    if !valid_version(active) || previous.is_some_and(|value| !valid_version(value)) {
        return Err(io::Error::new(
            io::ErrorKind::InvalidInput,
            "invalid version identifier",
        ));
    }
    if !root.join("versions").join(active).is_dir() {
        return Err(io::Error::new(
            io::ErrorKind::NotFound,
            "version directory is missing",
        ));
    }
    let metadata = root.join("metadata");
    fs::create_dir_all(&metadata)?;
    let destination = metadata.join("current.json");
    let temporary = metadata.join(format!(".current.json.{}.tmp", std::process::id()));
    let previous_json = previous.map_or_else(|| "null".to_owned(), |value| format!("\"{value}\""));
    let document = format!(
        "{{\n  \"activation_status\": \"active\",\n  \"active_version\": \"{active}\",\n  \"previous_version\": {previous_json},\n  \"schema_version\": \"reasonscript-current-installation/1.0\"\n}}\n"
    );
    let mut file = File::create(&temporary)?;
    file.write_all(document.as_bytes())?;
    file.sync_all()?;
    fs::rename(&temporary, &destination)?;
    if let Ok(directory) = File::open(&metadata) {
        let _ = directory.sync_all();
    }
    Ok(())
}

fn usage() -> ! {
    eprintln!(
        "usage: reason-updater activate <install-root> <active-version> [previous-version|-]"
    );
    std::process::exit(2);
}

fn main() {
    let args: Vec<String> = env::args().collect();
    if args.len() != 5 || args[1] != "activate" {
        usage();
    }
    let root = PathBuf::from(&args[2]);
    let previous = if args[4] == "-" {
        None
    } else {
        Some(args[4].as_str())
    };
    if let Err(error) = atomic_current(&root, &args[3], previous) {
        eprintln!("INS-UPD-009: {error}");
        std::process::exit(7);
    }
}

#[cfg(test)]
mod tests {
    use super::valid_version;

    #[test]
    fn version_identifier_is_restricted() {
        assert!(valid_version("0.5.1-phase1r"));
        assert!(!valid_version("../0.5.1"));
        assert!(!valid_version("0.5.1\""));
    }
}
