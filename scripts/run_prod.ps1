<#
.SYNOPSIS
    Explicit production server launcher for Bottom Pot.

.DESCRIPTION
    Starts uvicorn against the configured SQLITE_DB_PATH ONLY after verifying that
    no automated test, Playwright E2E, or CI environment markers are active.
    Sets BOTTOM_POT_ALLOW_OPERATIONAL_DB=1 explicitly for the launched process without
    storing it in .env.
#>

[CmdletBinding()]
param(
    [string]$HostAddress = "127.0.0.1",
    [int]$Port = 8000,
    [switch]$Reload
)

$testMarkers = @("PYTEST_CURRENT_TEST", "PLAYWRIGHT_TEST", "PLAYWRIGHT_SQLITE_DB_PATH", "BOTTOM_POT_TEST_MODE", "TESTING", "CI")
foreach ($marker in $testMarkers) {
    $val = [Environment]::GetEnvironmentVariable($marker)
    if ($val -and $val.Trim() -notin @("", "0", "false", "no", "off")) {
        Write-Error "Refusing to launch operational server while test/CI marker '$marker=$val' is active."
        exit 1
    }
}

$env:BOTTOM_POT_ALLOW_OPERATIONAL_DB = "1"
$uvicornArgs = @("-m", "uvicorn", "src.api.main:app", "--host", $HostAddress, "--port", "$Port")
if ($Reload) {
    $uvicornArgs += "--reload"
}

& python @uvicornArgs
exit $LASTEXITCODE
