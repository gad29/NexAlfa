# NexAlfa Windows Installer (PowerShell)
# Usage: iwr -useb https://nexalfa.work/install.ps1 | iex
# Or run locally: powershell -ExecutionPolicy Bypass -File install.ps1

$ErrorActionPreference = "Stop"

Write-Host "🚀 Installing NexAlfa — Your Autonomous AI Agent..." -ForegroundColor Cyan

# 1. Check Python
$pythonCmd = Get-Command python -ErrorAction SilentlyContinue
if (-not $pythonCmd) {
    $pythonCmd = Get-Command python3 -ErrorAction SilentlyContinue
}

if (-not $pythonCmd) {
    Write-Host "⚠️ Python not found. Installing Python via winget..." -ForegroundColor Yellow
    winget install -e --id Python.Python.3.11 --accept-package-agreements --accept-source-agreements
    $env:Path = [System.Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path","User")
} else {
    Write-Host "✅ Python detected: $($pythonCmd.Source)" -ForegroundColor Green
}

# 2. Check Node.js
$nodeCmd = Get-Command node -ErrorAction SilentlyContinue
if (-not $nodeCmd) {
    Write-Host "⚠️ Node.js not found. Installing Node.js LTS..." -ForegroundColor Yellow
    winget install -e --id OpenJS.NodeJS.LTS --accept-package-agreements --accept-source-agreements
} else {
    Write-Host "✅ Node.js detected: $($nodeCmd.Source)" -ForegroundColor Green
}

# 3. Install uv for fast Python package management
Write-Host "📦 Installing uv package manager..." -ForegroundColor Cyan
powershell -ExecutionPolicy Bypass -c "irm https://astral.sh/uv/install.ps1 | iex"

$uvPath = "$env:USERPROFILE\.local\bin"
if ($env:Path -notlike "*$uvPath*") {
    $env:Path = "$uvPath;$env:Path"
}

# 4. Clone or pull NexAlfa repository
$installDir = "$env:USERPROFILE\NexAlfa"
if (Test-Path $installDir) {
    Write-Host "🔄 Updating existing NexAlfa installation at $installDir..." -ForegroundColor Cyan
    Set-Location $installDir
    git pull origin main -q
} else {
    Write-Host "📥 Cloning NexAlfa repository..." -ForegroundColor Cyan
    git clone https://github.com/gad29/NexAlfa.git $installDir
    Set-Location $installDir
}

# 5. Install Python and Node dependencies
Write-Host "⚙️ Installing Python dependencies..." -ForegroundColor Cyan
uv pip install --system -e ".[all]" pywebview

Write-Host "⚙️ Installing Node.js dependencies..." -ForegroundColor Cyan
npm install --omit=dev

Set-Location "$installDir\web"
npm install --omit=dev
Set-Location $installDir

# 6. Create global launcher aliases
Write-Host "🔗 Setting up global nexalfa & nex commands..." -ForegroundColor Cyan
$binDir = "$env:USERPROFILE\.local\bin"
if (-not (Test-Path $binDir)) { New-Item -ItemType Directory -Path $binDir -Force }

$cmdContent = @"
@echo off
python -m cli.main %*
"@

Set-Content -Path "$binDir\nexalfa.cmd" -Value $cmdContent
Set-Content -Path "$binDir\nex.cmd" -Value $cmdContent

Write-Host "`n✅ NexAlfa installation complete!" -ForegroundColor Green
Write-Host "Starting interactive onboarding setup...`n" -ForegroundColor Cyan

# 7. Launch Onboarding Wizard
python -m cli.main onboard
