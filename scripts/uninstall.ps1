$ErrorActionPreference = "Stop"
$mapped = foreach ($arg in $args) {
    switch ($arg) { "-DryRun" { "--dry-run" } "-Purge" { "--purge" } "-Json" { "--json" } default { $arg } }
}
python (Join-Path $PSScriptRoot "uninstall.py") @mapped
exit $LASTEXITCODE
