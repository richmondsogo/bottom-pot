<#
.SYNOPSIS
    Bottom Pot Project Verification Script.

.DESCRIPTION
    Runs complete verification suite for Bottom Pot:
    - Repository health & secrets check
    - Frontend linting (oxlint)
    - Frontend typecheck & production build (tsc + vite)
    - Python backend unit tests (pytest)
    - Playwright end-to-end smoke tests against mock pipeline
#>

[CmdletBinding()]
param(
    [switch]$SkipE2E = $false,
    [switch]$E2EOnly = $false
)

Write-Host ""
Write-Host "Bottom Pot Verification Suite" -ForegroundColor Cyan
Write-Host "=============================" -ForegroundColor Cyan
Write-Host ""

$passed  = 0
$failed  = 0
$skipped = 0

function Run-Check {
    param(
        [string]$Label,
        [scriptblock]$Block,
        [bool]$Skip = $false
    )

    if ($Skip) {
        Write-Host ("  --  {0}  [skipped]" -f $Label) -ForegroundColor DarkGray
        $script:skipped++
        return
    }

    Write-Host ("  ..  {0}" -f $Label) -ForegroundColor DarkGray
    try {
        $output = & $Block 2>&1
        if ($LASTEXITCODE -eq 0 -or $LASTEXITCODE -eq $null) {
            Write-Host ("  OK  {0}" -f $Label) -ForegroundColor Green
            $script:passed++
        } else {
            Write-Host ("  !!  {0}  [exit code $LASTEXITCODE]" -f $Label) -ForegroundColor Red
            if ($output) {
                Write-Host ($output | Out-String) -ForegroundColor DarkRed
            }
            $script:failed++
        }
    } catch {
        Write-Host ("  !!  {0}  [error: {1}]" -f $Label, $_) -ForegroundColor Red
        $script:failed++
    }
}

# ---- Repository State --------------------------------------------------------

Write-Host "Repository State:" -ForegroundColor White

Run-Check "Git available" {
    git --version | Out-Null
} -Skip $E2EOnly

Run-Check "No tracked secrets (.env, keys, credentials)" {
    $patterns = @("*.pem", "*.key", ".env", "*.secret", "credentials.json", ".agents/mcp_config.json")
    $found    = @()
    foreach ($p in $patterns) {
        $matches = git ls-files $p 2>&1
        if ($matches -and $LASTEXITCODE -eq 0) { $found += $matches }
    }
    if ($found.Count -gt 0) {
        Write-Host "  Possible secrets tracked by git: $($found -join ', ')" -ForegroundColor Red
        exit 1
    }
} -Skip $E2EOnly

Write-Host ""

# ---- Frontend Verification --------------------------------------------------

Write-Host "Frontend Checks:" -ForegroundColor White

Run-Check "CSS Cascade Lint (no unlayered element/reset selectors)" {
    node scripts/lint_css_cascade.js
} -Skip $E2EOnly

Run-Check "Frontend Linting (oxlint)" {
    npm --prefix frontend run lint
} -Skip $E2EOnly

Run-Check "Frontend Unit Tests (vitest)" {
    npm --prefix frontend run test
} -Skip $E2EOnly

Run-Check "Frontend Typecheck & Production Build (tsc + vite)" {
    npm --prefix frontend run build
} -Skip $E2EOnly

Write-Host ""

# ---- Backend Verification ---------------------------------------------------

Write-Host "Backend Checks:" -ForegroundColor White

Run-Check "Python Unit Tests (pytest)" {
    python -m pytest -q
} -Skip $E2EOnly

Write-Host ""

# ---- End-to-End Verification ------------------------------------------------

Write-Host "End-to-End Browser Tests:" -ForegroundColor White

Run-Check "Playwright E2E Suite" {
    $e2eTmpDir = Join-Path ([System.IO.Path]::GetTempPath()) ("bottom-pot-e2e-" + [guid]::NewGuid().ToString("N"))
    New-Item -ItemType Directory -Path $e2eTmpDir -Force | Out-Null
    $hadPlaywrightDb = Test-Path Env:PLAYWRIGHT_SQLITE_DB_PATH
    $hadPlaywrightSub = Test-Path Env:PLAYWRIGHT_SUBSCRIPTIONS_FILE
    $hadBaseUrl = Test-Path Env:PLAYWRIGHT_BASE_URL
    $hadReuseServer = Test-Path Env:PLAYWRIGHT_REUSE_SERVER
    $prevPlaywrightDb = $env:PLAYWRIGHT_SQLITE_DB_PATH
    $prevPlaywrightSub = $env:PLAYWRIGHT_SUBSCRIPTIONS_FILE
    $prevBaseUrl = $env:PLAYWRIGHT_BASE_URL
    $prevReuseServer = $env:PLAYWRIGHT_REUSE_SERVER
    try {
        $env:PLAYWRIGHT_BASE_URL = "http://127.0.0.1:8000"
        $env:PLAYWRIGHT_SQLITE_DB_PATH = Join-Path $e2eTmpDir "e2e-cache.sqlite"
        $env:PLAYWRIGHT_SUBSCRIPTIONS_FILE = Join-Path $e2eTmpDir "e2e-subscriptions.csv"
        $env:PLAYWRIGHT_REUSE_SERVER = "0"
        npx playwright test
    } finally {
        if ($hadBaseUrl) { $env:PLAYWRIGHT_BASE_URL = $prevBaseUrl } else { Remove-Item Env:PLAYWRIGHT_BASE_URL -ErrorAction SilentlyContinue }
        if ($hadPlaywrightDb) { $env:PLAYWRIGHT_SQLITE_DB_PATH = $prevPlaywrightDb } else { Remove-Item Env:PLAYWRIGHT_SQLITE_DB_PATH -ErrorAction SilentlyContinue }
        if ($hadPlaywrightSub) { $env:PLAYWRIGHT_SUBSCRIPTIONS_FILE = $prevPlaywrightSub } else { Remove-Item Env:PLAYWRIGHT_SUBSCRIPTIONS_FILE -ErrorAction SilentlyContinue }
        if ($hadReuseServer) { $env:PLAYWRIGHT_REUSE_SERVER = $prevReuseServer } else { Remove-Item Env:PLAYWRIGHT_REUSE_SERVER -ErrorAction SilentlyContinue }
        Remove-Item -Path $e2eTmpDir -Recurse -Force -ErrorAction SilentlyContinue
    }
} -Skip $SkipE2E

Write-Host ""

# ---- Summary ----------------------------------------------------------------

$total = $passed + $failed + $skipped

$color = if ($failed -gt 0) { "Red" } elseif ($skipped -gt 0) { "Yellow" } else { "Green" }
Write-Host ("Results: {0} passed, {1} failed, {2} skipped  (of {3} checks)" `
    -f $passed, $failed, $skipped, $total) -ForegroundColor $color

Write-Host ""

if ($failed -gt 0) {
    exit 1
}
