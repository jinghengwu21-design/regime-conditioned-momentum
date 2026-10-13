param([ValidateSet('serve','demo','test','evaluate','build')][string]$Mode = 'serve')
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
Push-Location -LiteralPath $projectRoot
try {
    $env:PYTHONUTF8 = '1'
    $venvPython = Join-Path $projectRoot '.venv\Scripts\python.exe'
    if (-not (Test-Path -LiteralPath $venvPython)) {
        & python -m venv --without-pip .venv
        if ($LASTEXITCODE -ne 0) { throw 'Could not create the virtual environment.' }
    }
    $lockHash = (Get-FileHash -LiteralPath 'requirements.lock' -Algorithm SHA256).Hash
    $stampPath = Join-Path $projectRoot '.venv\dependency-lock.sha256'
    $installedHash = if (Test-Path -LiteralPath $stampPath) { (Get-Content -LiteralPath $stampPath -Raw).Trim() } else { '' }
    if ($installedHash -ne $lockHash) {
        & python -m pip --python .venv install -r requirements.lock --disable-pip-version-check
        if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed.' }
        Set-Content -LiteralPath $stampPath -Value $lockHash -Encoding utf8
    }
    if ($Mode -eq 'serve' -or $Mode -eq 'build') {
        Push-Location -LiteralPath (Join-Path $projectRoot 'web')
        try {
            & npm.cmd ci --no-fund --no-audit
            if ($LASTEXITCODE -ne 0) { throw 'Frontend dependency installation failed.' }
            & npm.cmd run build
            if ($LASTEXITCODE -ne 0) { throw 'Frontend build failed.' }
        } finally { Pop-Location }
    }
    switch ($Mode) {
        'serve' { & $venvPython -m research_agent.server }
        'build' { Write-Output 'Terminal built in web/dist.' }
        'demo' { & $venvPython -m research_agent.cli demo }
        'evaluate' { & $venvPython -m research_agent.cli evaluate }
        'test' {
            $env:PYTEST_DISABLE_PLUGIN_AUTOLOAD = '1'
            $testTemp = Join-Path $projectRoot ('outputs\pytest-' + [guid]::NewGuid().ToString('N'))
            & $venvPython -m pytest tests --basetemp $testTemp --junitxml outputs\test-results.xml
        }
    }
    if ($LASTEXITCODE -ne 0) { throw ('Command failed with code ' + $LASTEXITCODE) }
} finally {
    Pop-Location
}

