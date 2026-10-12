# Local quality gate. Run before every commit. No CI runs in the cloud.
# Set CALLTIMEOUT_E2E=1 to also build the wheel and test it installed.
$ErrorActionPreference = "Stop"

$steps = @(
    { ruff format --check . },
    { ruff check . },
    { mypy --strict src tests },
    { python -m pytest }
)
foreach ($step in $steps) {
    & $step
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}
