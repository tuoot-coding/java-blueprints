# Полный набор локальных проверок Backend. Останавливается на первой ошибке.
# Запуск: powershell -ExecutionPolicy Bypass -File scripts/check.ps1
$ErrorActionPreference = "Stop"
$repositoryRoot = Split-Path -Parent $PSScriptRoot

function Invoke-Step([string]$Directory, [string]$Title, [scriptblock]$Command) {
    Write-Host "==> $Title"
    Push-Location (Join-Path $repositoryRoot $Directory)
    try {
        & $Command
        if ($LASTEXITCODE -ne 0) { throw "Шаг '$Title' завершился с кодом $LASTEXITCODE" }
    }
    finally {
        Pop-Location
    }
}

Invoke-Step "backend" "backend: ruff check" { uv run ruff check }
Invoke-Step "backend" "backend: ruff format --check" { uv run ruff format --check }
Invoke-Step "backend" "backend: mypy" { uv run mypy }
Invoke-Step "backend" "backend: pytest" { uv run pytest }
Invoke-Step "backend" "backend: OpenAPI-контракт актуален" { uv run python -m app.openapi_export --check }

if (Test-Path (Join-Path $repositoryRoot "frontend/package.json")) {
    Invoke-Step "frontend" "frontend: typecheck" { npm run typecheck }
    Invoke-Step "frontend" "frontend: lint" { npm run lint }
    Invoke-Step "frontend" "frontend: test" { npm test }
}

Write-Host "Все проверки пройдены"
