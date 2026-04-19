#!/usr/bin/env pwsh
# deploy_to_server.ps1
# Run this from YOUR LOCAL WINDOWS PC that is on the same network as the server.
# Requires: OpenSSH (built into Windows 10/11) or PuTTY plink.exe
# Usage: .\scripts\deploy_to_server.ps1
#
# IMPORTANT: Run from the project root:
#   cd "d:\Mlops_Dlops\MAJOR PROJECT"
#   .\scripts\deploy_to_server.ps1

param(
    [string]$ServerHost = "10.6.0.46",
    [string]$ServerUser = "sujiv1",
    [string]$ServerPass = "sujiv1",
    [string]$HfToken   = $env:HF_TOKEN,      # set: $env:HF_TOKEN='hf_...' before running
    [string]$WandbKey  = $env:WANDB_API_KEY, # set: $env:WANDB_API_KEY='wandb_v1_...' before running
    [string]$RepoUrl   = "https://github.com/Jyoti-Dwivedi-010/V2AI_M25CSA010_M25CSA018.git",
    [string]$RemoteDir = "~/v2ai"
)

Write-Host "========================================================" -ForegroundColor Cyan
Write-Host " V2AI — Deploying to GPU Server $ServerHost" -ForegroundColor Cyan
Write-Host "========================================================" -ForegroundColor Cyan

# ── Check for SSH ────────────────────────────────────────────────────────────
$sshPath = Get-Command ssh -ErrorAction SilentlyContinue
if (-not $sshPath) {
    Write-Host "[ERROR] ssh not found. Enable OpenSSH in Windows Settings -> Apps -> Optional Features." -ForegroundColor Red
    exit 1
}

# ── Helper: run SSH command ──────────────────────────────────────────────────
function Invoke-SSH {
    param([string]$Command)
    Write-Host "  >> $Command" -ForegroundColor Gray
    # Use sshpass equivalent: pipe password via SSH_ASKPASS or use -o PasswordAuthentication
    # On Windows, use plink if available, otherwise use OpenSSH with key
    if (Get-Command plink -ErrorAction SilentlyContinue) {
        plink -ssh -pw $ServerPass "$ServerUser@$ServerHost" $Command
    } else {
        # OpenSSH — will prompt for password (user must enter)
        ssh -o StrictHostKeyChecking=no "$ServerUser@$ServerHost" $Command
    }
}

Write-Host ""
Write-Host "[1/6] Testing SSH connection..." -ForegroundColor Yellow
Invoke-SSH "echo 'SSH OK'"

Write-Host ""
Write-Host "[2/6] Cloning or updating repository on server..." -ForegroundColor Yellow
Invoke-SSH @"
if [ -d $RemoteDir/.git ]; then
    cd $RemoteDir && git fetch origin && git reset --hard origin/main
else
    git clone $RepoUrl $RemoteDir
fi
"@

Write-Host ""
Write-Host "[3/6] Setting credentials and creating .env..." -ForegroundColor Yellow
Invoke-SSH @"
cd $RemoteDir
cp .env.server-docker .env
echo 'HF_TOKEN=$HfToken' >> .env
echo 'WANDB_API_KEY=$WandbKey' >> .env
mkdir -p artifacts/uploads artifacts/transcripts artifacts/vectorstore \
    artifacts/monitoring artifacts/reports artifacts/mlflow \
    artifacts/postgres artifacts/minio artifacts/prometheus artifacts/grafana
"@

Write-Host ""
Write-Host "[4/6] Starting base services..." -ForegroundColor Yellow
Invoke-SSH @"
cd $RemoteDir
export HF_TOKEN='$HfToken'
export WANDB_API_KEY='$WandbKey'
docker-compose up -d postgres minio mlflow prometheus grafana
echo 'Waiting 20 seconds for services to initialize...'
sleep 20
docker-compose ps
"@

Write-Host ""
Write-Host "[5/6] Starting GPU API (GPU-1 only) and UI..." -ForegroundColor Yellow
Invoke-SSH @"
cd $RemoteDir
export HF_TOKEN='$HfToken'
export WANDB_API_KEY='$WandbKey'
docker-compose --profile gpu up -d api-gpu ui
sleep 10
docker-compose ps
"@

Write-Host ""
Write-Host "[6/6] Running health check..." -ForegroundColor Yellow
Start-Sleep -Seconds 15
Invoke-SSH "curl -s http://localhost:8001/health || echo 'API not yet ready (still loading models)'"

Write-Host ""
Write-Host "========================================================" -ForegroundColor Green
Write-Host " DEPLOYMENT COMPLETE" -ForegroundColor Green
Write-Host "========================================================" -ForegroundColor Green
Write-Host " Access via YOUR LOCAL MACHINE (same network as server):" -ForegroundColor Green
Write-Host ""
Write-Host "  UI (Streamlit): http://$ServerHost`:8501" -ForegroundColor White
Write-Host "  API (FastAPI):  http://$ServerHost`:8001" -ForegroundColor White
Write-Host "  API Docs:       http://$ServerHost`:8001/docs" -ForegroundColor White
Write-Host "  MLflow:         http://$ServerHost`:5000" -ForegroundColor White
Write-Host "  Prometheus:     http://$ServerHost`:9090" -ForegroundColor White
Write-Host "  Grafana:        http://$ServerHost`:3000  (admin / v2ai_grafana)" -ForegroundColor White
Write-Host "  MinIO Console:  http://$ServerHost`:9001  (minioadmin / minioadmin123)" -ForegroundColor White
Write-Host ""
Write-Host " To check logs: ssh $ServerUser@$ServerHost 'cd ~/v2ai && docker-compose logs -f api-gpu'" -ForegroundColor Gray
Write-Host "========================================================" -ForegroundColor Green
