$ErrorActionPreference = "Stop"
$scriptPath = Join-Path $PSScriptRoot "install_common.py"
$mapped = foreach ($arg in $args) {
    switch ($arg) { "-NonInteractive" { "--non-interactive" } "-Json" { "--json" } "-ModifyPath" { "--modify-path" } "-Update" { "--update" } "-Package" { "--package" } "-Force" { "--force" } default { $arg } }
}
python $scriptPath @mapped
exit $LASTEXITCODE
