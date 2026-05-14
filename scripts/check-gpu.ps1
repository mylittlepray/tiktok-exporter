$ErrorActionPreference = "Stop"

if (Get-Command nvidia-smi -ErrorAction SilentlyContinue) {
    nvidia-smi
} else {
    Write-Host "nvidia-smi not found." -ForegroundColor Yellow
}

uv run tiktokexport doctor
