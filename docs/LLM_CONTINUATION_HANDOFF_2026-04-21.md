# V2AI Continuation Handoff (2026-04-21)

## 1) Purpose of this file
This handoff is for another LLM/engineer to continue work without losing context.
It captures:
- what was implemented and validated
- current repo/runtime/deployment state
- open blockers
- exact next actions
- reusable deployment automation script for local Windows + GCP VM

---

## 2) Current repository state
- Repo path: `/data/sujiv1/v2ai`
- Branch: `main`
- Working tree: clean except one untracked file `cookies.txt`
- Remote:
  - `origin https://github.com/Jyoti-Dwivedi-010/V2AI_M25CSA010_M25CSA018.git`

### Recent commits
1. `4d2bab0` - feat: release GPU memory after pipeline completion
2. `762585c` - fix: configure active groq model via env
3. `4d2b081` - ui: flip flashcards with hover reveal
4. `357f41e` - savepoint: stable v2ai build with gpu verification and robust generation fixes
5. `0fa4912` - fix: resolve return_full_text kwarg injection in local model pipeline

---

## 3) Current runtime state (server)
All core containers are up and healthy:
- `v2ai-api` (8000)
- `v2ai-api-gpu` (8001)
- `v2ai-ui` (8501)
- `v2ai-postgres` (5432)
- `v2ai-minio` (9000/9001)
- `v2ai-mlflow` (5000)
- `v2ai-prometheus` (9090)
- `v2ai-grafana` (3000)

---

## 4) What has been fixed/implemented

### A) Generation/runtime robustness
- Added safe HF generation path to avoid unsupported kwargs issue (`return_full_text` warning/failure path).
- Hardened summary + study material generation flow.
- Confirmed end-to-end upload pipeline returns summary, concepts, flashcards, quiz.

### B) Groq model deprecation fix
- Groq model is now configurable via env.
- Default switched to active model: `llama-3.3-70b-versatile`.
- Files updated:
  - `src/app/config.py`
  - `src/app/services/video_pipeline_service.py`
  - `.env.example`
  - `docker-compose.yml`

### C) Flashcard UI behavior
- Flashcards converted to hover flip-card style.
- Updated classes and markup in `src/ui/streamlit_app.py`.
- Confirmed updated code exists both in source and running UI container.

### D) GPU memory release after task completion
Implemented in `src/app/services/video_pipeline_service.py`:
- New `_release_gpu_memory(reason)` method.
- Runs in `finally` blocks after:
  - `create_session` (upload pipeline)
  - `ask_question` (QnA)
- Cleanup includes:
  - `gc.collect()`
  - `torch.cuda.empty_cache()`
  - `torch.cuda.ipc_collect()` (if available)
  - clearing cached model builders to make memory reclaimable between requests
  - lazy re-init logic for generation model on next request

Validation done:
- upload-video + ask both succeeded
- logs show:
  - `Released GPU cache after task: create_session`
  - `Released GPU cache after task: ask_question`

---

## 5) Git push/authentication status and blocker history

### What happened
- Local commit succeeded for GPU memory release (`4d2bab0`).
- Push to GitHub failed on shared server due:
  1) missing/invalid credentials over HTTPS
  2) earlier ENOSPC issues in askpass flow (now disk improved)
  3) SSH push failed due missing server-side public key authorization (`Permission denied (publickey)`).

### Current remote protocol
- Back to HTTPS remote (safe default):
  - `origin https://github.com/Jyoti-Dwivedi-010/V2AI_M25CSA010_M25CSA018.git`

### Suggested continuation
- Push from local Windows workstation (recommended), not shared server.

---

## 6) Disk cleanup performed

### Done
- Build cache prune completed.
- Project-specific unused image cleanup completed.

### Outcome
- Reclaimed significant space (including ~48GB from unused project images).
- Root filesystem moved from 100% to around 90% usage.
- Build cache currently: `0B`.

---

## 7) CI/CD status in repository

### Present workflows
- `/.github/workflows/ci.yml`
  - PR/push checks: lint, tests, etc.
- `/.github/workflows/cd.yml`
  - Builds and pushes images to GHCR on `main`
  - Optional SSH deploy step (if server secrets exist)
- `/.github/workflows/evaluate.yml`
  - evaluation trigger flow

### Important note
Current CD deploy step is SSH to a server using GitHub secrets (`SERVER_HOST`, `SERVER_USER`, `SERVER_PASSWORD`).

---

## 8) Ready-to-run Windows script for automated GCP VM deployment + CI/CD secret wiring
Use this from a local Windows machine with `gcloud`, `gh`, and `git` installed.

```powershell
param(
  [Parameter(Mandatory = $true)] [string]$ProjectId,
  [Parameter(Mandatory = $false)] [string]$Region = "asia-south1",
  [Parameter(Mandatory = $false)] [string]$Zone = "asia-south1-a",
  [Parameter(Mandatory = $false)] [string]$VmName = "v2ai-gpu-vm",
  [Parameter(Mandatory = $false)] [string]$MachineType = "n1-standard-8",
  [Parameter(Mandatory = $false)] [int]$DiskGb = 250,
  [Parameter(Mandatory = $false)] [bool]$UseGpu = $true,
  [Parameter(Mandatory = $false)] [string]$GpuType = "nvidia-tesla-t4",
  [Parameter(Mandatory = $true)] [string]$GithubRepo,
  [Parameter(Mandatory = $false)] [string]$ServerUser = $env:USERNAME,
  [Parameter(Mandatory = $false)] [string]$ServerPassword = "",
  [Parameter(Mandatory = $false)] [switch]$TriggerCd
)

$ErrorActionPreference = "Stop"

function Require-Cmd($name) {
  if (-not (Get-Command $name -ErrorAction SilentlyContinue)) {
    throw "$name is required but not found in PATH."
  }
}

Write-Host "==> Checking prerequisites..."
Require-Cmd "gcloud"
Require-Cmd "git"
Require-Cmd "gh"

Write-Host "==> Configuring gcloud project/region/zone..."
gcloud config set project $ProjectId | Out-Null
gcloud config set compute/region $Region | Out-Null
gcloud config set compute/zone $Zone | Out-Null

Write-Host "==> Enabling required APIs..."
gcloud services enable compute.googleapis.com | Out-Null

Write-Host "==> Creating firewall rules (idempotent)..."
$fwRules = @(
  @{ Name="v2ai-allow-ui"; Ports="tcp:8501" },
  @{ Name="v2ai-allow-api"; Ports="tcp:8000,tcp:8001" },
  @{ Name="v2ai-allow-mlops"; Ports="tcp:5000,tcp:9000,tcp:9001,tcp:9090,tcp:3000" }
)

foreach ($r in $fwRules) {
  $exists = $false
  try {
    gcloud compute firewall-rules describe $r.Name | Out-Null
    $exists = $true
  } catch {}
  if (-not $exists) {
    gcloud compute firewall-rules create $r.Name `
      --allow $r.Ports `
      --target-tags v2ai-server `
      --direction INGRESS `
      --source-ranges 0.0.0.0/0 | Out-Null
  }
}

Write-Host "==> Preparing VM startup script..."
$startup = @'
#!/usr/bin/env bash
set -euo pipefail

sudo apt-get update
sudo apt-get install -y ca-certificates curl gnupg lsb-release git

if ! command -v docker >/dev/null 2>&1; then
  curl -fsSL https://get.docker.com | sudo sh
fi
sudo usermod -aG docker ${SUDO_USER:-$USER} || true
sudo apt-get install -y docker-compose-plugin || true

if lspci | grep -qi nvidia; then
  distribution=$(. /etc/os-release;echo $ID$VERSION_ID) || true
  curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey | sudo gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg || true
  curl -s -L https://nvidia.github.io/libnvidia-container/$distribution/libnvidia-container.list | \
    sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g' | \
    sudo tee /etc/apt/sources.list.d/nvidia-container-toolkit.list >/dev/null || true
  sudo apt-get update || true
  sudo apt-get install -y nvidia-container-toolkit || true
  sudo nvidia-ctk runtime configure --runtime=docker || true
  sudo systemctl restart docker || true
fi
'@

$startupPath = Join-Path $env:TEMP "v2ai_startup.sh"
$startup | Set-Content -Path $startupPath -Encoding ASCII

Write-Host "==> Creating VM if needed..."
$vmExists = $false
try {
  gcloud compute instances describe $VmName --zone $Zone | Out-Null
  $vmExists = $true
} catch {}

if (-not $vmExists) {
  if ($UseGpu) {
    gcloud compute instances create $VmName `
      --zone $Zone `
      --machine-type $MachineType `
      --boot-disk-size "${DiskGb}GB" `
      --image-family ubuntu-2204-lts `
      --image-project ubuntu-os-cloud `
      --accelerator "type=$GpuType,count=1" `
      --maintenance-policy TERMINATE `
      --restart-on-failure `
      --metadata-from-file "startup-script=$startupPath" `
      --tags v2ai-server `
      --scopes cloud-platform | Out-Null
  } else {
    gcloud compute instances create $VmName `
      --zone $Zone `
      --machine-type $MachineType `
      --boot-disk-size "${DiskGb}GB" `
      --image-family ubuntu-2204-lts `
      --image-project ubuntu-os-cloud `
      --metadata-from-file "startup-script=$startupPath" `
      --tags v2ai-server `
      --scopes cloud-platform | Out-Null
  }
} else {
  Write-Host "VM already exists. Skipping create."
}

$vmIp = gcloud compute instances describe $VmName --zone $Zone --format="get(networkInterfaces[0].accessConfigs[0].natIP)"
Write-Host "==> VM external IP: $vmIp"

Write-Host "==> Waiting for SSH..."
$ok = $false
for ($i=0; $i -lt 20; $i++) {
  try {
    gcloud compute ssh "$ServerUser@$VmName" --zone $Zone --command "echo ok" --quiet | Out-Null
    $ok = $true
    break
  } catch {
    Start-Sleep -Seconds 10
  }
}
if (-not $ok) { throw "SSH not ready. Try again in 1-2 minutes." }

Write-Host "==> Deploying app on VM..."
$deployCmd = @"
set -euo pipefail
if [ ! -d ~/v2ai ]; then
  git clone https://github.com/$GithubRepo.git ~/v2ai
fi
cd ~/v2ai
git pull origin main

if [ -f .env.server-docker ]; then
  cp .env.server-docker .env
elif [ -f .env.example ]; then
  cp .env.example .env
fi

mkdir -p artifacts/uploads artifacts/transcripts artifacts/vectorstore artifacts/monitoring artifacts/reports artifacts/mlflow artifacts/postgres artifacts/minio artifacts/grafana artifacts/prometheus

docker compose up -d postgres minio mlflow prometheus grafana
sleep 12

if docker info 2>/dev/null | grep -qi nvidia; then
  docker compose --profile gpu up -d api-gpu ui
else
  docker compose up -d api ui
fi

docker compose ps
"@
gcloud compute ssh "$ServerUser@$VmName" --zone $Zone --command $deployCmd --quiet

Write-Host "==> Setting GitHub secrets for existing CD workflow..."
gh auth status -h github.com | Out-Null
gh secret set SERVER_HOST --repo $GithubRepo --body $vmIp | Out-Null
gh secret set SERVER_USER --repo $GithubRepo --body $ServerUser | Out-Null

if ($ServerPassword -ne "") {
  gh secret set SERVER_PASSWORD --repo $GithubRepo --body $ServerPassword | Out-Null
  Write-Host "SERVER_PASSWORD updated."
} else {
  Write-Host "SERVER_PASSWORD not set by script. If needed:"
  Write-Host "gh secret set SERVER_PASSWORD --repo $GithubRepo --body '<password>'"
}

if ($TriggerCd) {
  Write-Host "==> Triggering CD workflow..."
  gh workflow run CD --repo $GithubRepo
}

Write-Host ""
Write-Host "=== DONE ==="
Write-Host "UI:         http://$vmIp`:8501"
Write-Host "API CPU:    http://$vmIp`:8000"
Write-Host "API GPU:    http://$vmIp`:8001"
Write-Host "MLflow:     http://$vmIp`:5000"
Write-Host "MinIO:      http://$vmIp`:9001"
Write-Host "Prometheus: http://$vmIp`:9090"
Write-Host "Grafana:    http://$vmIp`:3000"
```

---

## 9) Recommended next actions for continuing LLM/engineer
1. Push current `main` to GitHub from local machine (shared-server auth was flaky).
2. Run the PowerShell deploy script from local Windows machine.
3. Confirm GitHub secrets and CD workflow success.
4. Optional hardening: switch CD deploy auth from password to SSH key.
5. Optional hardening: restrict public firewall CIDR (currently open for convenience).

---

## 10) Fast verification checklist after cloud deploy
- `docker compose ps` shows all required services up
- UI reachable on `:8501`
- API health on `:8000/health` and/or `:8001/health`
- Upload test succeeds and generates summary/flashcards/quiz
- API logs contain no `return_full_text` errors
- GPU logs show CUDA device use when GPU profile active
- `Released GPU cache after task:*` log appears after upload and ask

---

## 11) Security note
This repository currently contains password-based server deploy patterns in places.
For production, prefer:
- SSH key auth for deployment
- least-privilege firewall rules
- secrets in GitHub Actions secrets / GCP Secret Manager

End of handoff.
