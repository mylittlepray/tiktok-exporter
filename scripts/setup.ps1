param(
    [switch]$CpuOnly,
    [switch]$ForceCuda
)

$ErrorActionPreference = "Stop"

function Write-Step($Message) {
    Write-Host ""
    Write-Host "==> $Message" -ForegroundColor Cyan
}

function Get-NvidiaDriverVersion {
    $nvidiaSmi = Get-Command nvidia-smi -ErrorAction SilentlyContinue
    if (-not $nvidiaSmi) {
        return $null
    }

    $driver = & nvidia-smi --query-gpu=driver_version --format=csv,noheader 2>$null | Select-Object -First 1
    if (-not $driver) {
        return $null
    }

    return [Version]($driver.Trim())
}

if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    Write-Error "uv is not installed. Install it first: https://docs.astral.sh/uv/getting-started/installation/"
}

Write-Step "Checking NVIDIA driver"
$driverVersion = Get-NvidiaDriverVersion
$minimumCu118Driver = [Version]"522.06"

if ($CpuOnly) {
    Write-Host "CPU-only setup requested."
} elseif ($null -eq $driverVersion) {
    Write-Host "NVIDIA GPU was not detected. The project will run on CPU." -ForegroundColor Yellow
} else {
    Write-Host "Detected NVIDIA driver: $driverVersion"
    if ($driverVersion -lt $minimumCu118Driver -and -not $ForceCuda) {
        Write-Host "This driver is below the official CUDA 11.8 toolkit minimum of 522.06." -ForegroundColor Yellow
        Write-Host "Setup will still install the project's PyTorch wheel; trust the final doctor output." -ForegroundColor Yellow
        Write-Host "If cuda_available is False, update the NVIDIA driver and run scripts\setup.ps1 again." -ForegroundColor Yellow
    }
}

Write-Step "Creating/updating the virtual environment"
uv sync

if (-not $CpuOnly -and $null -ne $driverVersion -and ($driverVersion -ge $minimumCu118Driver -or $ForceCuda)) {
    Write-Step "Ensuring CUDA-enabled PyTorch is installed"
    uv pip install torch --index-url https://download.pytorch.org/whl/cu118 --upgrade --force-reinstall
}

Write-Step "Device diagnostics"
uv run tiktokexport doctor

Write-Host ""
Write-Host "Setup finished. Try:" -ForegroundColor Green
Write-Host "uv run tiktokexport export `"https://vt.tiktok.com/ZS59RqM8D/`" --device auto"
