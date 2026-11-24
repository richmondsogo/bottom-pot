<#
.SYNOPSIS
    Explicit production server launcher for Bottom Pot.

.DESCRIPTION
    Starts uvicorn against the configured SQLITE_DB_PATH ONLY after verifying that
    no automated test, Playwright E2E, or CI environment markers are active.
    Scopes BOTTOM_POT_ALLOW_OPERATIONAL_DB=1 strictly to the child server launch
    and restores or removes the parent session variable in a finally block.
    Compatible with Windows PowerShell 5.1 and PowerShell 7+.
#>

[CmdletBinding()]
param(
    [string]$HostAddress = "127.0.0.1",
    [int]$Port = 8000,
    [switch]$Reload
)

$alwaysActiveMarkers = @(
    "PYTEST_CURRENT_TEST",
    "PLAYWRIGHT_TEST",
    "PLAYWRIGHT_SQLITE_DB_PATH",
    "BOTTOM_POT_TEST_MODE"
)
foreach ($marker in $alwaysActiveMarkers) {
    $val = [Environment]::GetEnvironmentVariable($marker)
    if ($null -ne $val -and $val.Trim() -ne "") {
        [Console]::Error.WriteLine(
            "Refusing to launch operational server while test/E2E marker '$marker=$val' is active."
        )
        exit 1
    }
}

$truthyFlagMarkers = @("TESTING", "CI")
foreach ($marker in $truthyFlagMarkers) {
    $val = [Environment]::GetEnvironmentVariable($marker)
    if ($null -ne $val) {
        $norm = $val.Trim().ToLowerInvariant()
        if ($norm -ne "" -and @("0", "false", "no", "off") -notcontains $norm) {
            [Console]::Error.WriteLine(
                "Refusing to launch operational server while test/CI marker '$marker=$val' is active."
            )
            exit 1
        }
    }
}

$uvicornArgs = @("-m", "uvicorn", "src.api.main:app", "--host", $HostAddress, "--port", "$Port")
if ($Reload) {
    $uvicornArgs += "--reload"
}

$hadAllowOperationalDb = Test-Path Env:BOTTOM_POT_ALLOW_OPERATIONAL_DB
$prevAllowOperationalDb = if ($hadAllowOperationalDb) { $env:BOTTOM_POT_ALLOW_OPERATIONAL_DB } else { $null }
$hadMonitoringEnabled = Test-Path Env:MONITORING_ENABLED
$prevMonitoringEnabled = if ($hadMonitoringEnabled) { $env:MONITORING_ENABLED } else { $null }
$hadSerperMode = Test-Path Env:SERPER_MODE
$prevSerperMode = if ($hadSerperMode) { $env:SERPER_MODE } else { $null }
$childExitCode = 1

try {
    $env:BOTTOM_POT_ALLOW_OPERATIONAL_DB = "1"
    if (-not $hadMonitoringEnabled -or [string]::IsNullOrWhiteSpace($env:MONITORING_ENABLED)) {
        $env:MONITORING_ENABLED = "true"
    }
    if (-not $hadSerperMode -or [string]::IsNullOrWhiteSpace($env:SERPER_MODE)) {
        $env:SERPER_MODE = "fallback"
    }
    & python @uvicornArgs
    if ($null -eq $LASTEXITCODE) {
        $childExitCode = 0
    } else {
        $childExitCode = [int]$LASTEXITCODE
    }
} finally {
    if ($hadAllowOperationalDb) {
        $env:BOTTOM_POT_ALLOW_OPERATIONAL_DB = $prevAllowOperationalDb
    } else {
        Remove-Item Env:BOTTOM_POT_ALLOW_OPERATIONAL_DB -ErrorAction SilentlyContinue
    }
    if ($hadMonitoringEnabled) {
        $env:MONITORING_ENABLED = $prevMonitoringEnabled
    } else {
        Remove-Item Env:MONITORING_ENABLED -ErrorAction SilentlyContinue
    }
    if ($hadSerperMode) {
        $env:SERPER_MODE = $prevSerperMode
    } else {
        Remove-Item Env:SERPER_MODE -ErrorAction SilentlyContinue
    }
}

exit $childExitCode
