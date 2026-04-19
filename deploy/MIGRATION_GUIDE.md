# V2AI — Migration Guide: Server → Google Cloud

## Overview

This guide explains how to migrate V2AI from the GPU server (`sujiv1@10.6.0.46`)
to Google Cloud, and how to run the full stack from your **local Windows PC** using
Google Cloud CLI.

---

## Step 1: Install Prerequisites on Your Local Windows PC

```powershell
# Install Google Cloud CLI
# Download from: https://cloud.google.com/sdk/docs/install
# Run the installer, then open a new PowerShell window

# Verify installation
gcloud version

# Install Docker Desktop for Windows
# Download from: https://www.docker.com/products/docker-desktop/

# Install Git for Windows (if not already)
# Download from: https://git-scm.com/download/win
```

---

## Step 2: Authenticate Google Cloud

```powershell
# Login to your Google account
gcloud auth login

# Set your project (replace with your actual project ID)
gcloud config set project YOUR_PROJECT_ID

# Configure Docker to push to GCR
gcloud auth configure-docker
```

---

## Step 3: Clone the Repository Locally

```powershell
git clone https://github.com/Jyoti-Dwivedi-010/V2AI_M25CSA010_M25CSA018.git
cd "V2AI_M25CSA010_M25CSA018"
```

---

## Step 4: Run the GCloud Deploy Script

> **On Windows, use Git Bash or WSL** (the script is a bash script):

```bash
# In Git Bash or WSL:
cd /path/to/V2AI_M25CSA010_M25CSA018

# Make executable
chmod +x deploy/gcloud_deploy.sh

# Deploy (replace with your project ID and region)
bash deploy/gcloud_deploy.sh asia-south1 your-gcloud-project-id
```

The script will:
1. Enable required GCloud APIs
2. Build Docker images locally
3. Push images to Google Container Registry
4. Create Cloud SQL (PostgreSQL) instance
5. Deploy API to Cloud Run
6. Deploy UI to Cloud Run
7. Print the live URLs

---

## Step 5: Migrate Artifacts from Server to GCloud

If you have existing sessions/data on the server:

```bash
# Download artifacts from server to your local machine
# (run in Git Bash on Windows)
SERVER_HOST="10.6.0.46"
SERVER_USER="sujiv1"
SERVER_PASS="sujiv1"

# Download (need sshpass or use WinSCP)
sshpass -p "$SERVER_PASS" scp -r \
  $SERVER_USER@$SERVER_HOST:~/v2ai/artifacts/uploads \
  ./artifacts/

sshpass -p "$SERVER_PASS" scp -r \
  $SERVER_USER@$SERVER_HOST:~/v2ai/artifacts/transcripts \
  ./artifacts/

sshpass -p "$SERVER_PASS" scp -r \
  $SERVER_USER@$SERVER_HOST:~/v2ai/artifacts/vectorstore \
  ./artifacts/

# Then upload to Cloud Storage (optional)
gsutil cp -r ./artifacts/ gs://your-bucket/v2ai-artifacts/
```

---

## Step 6: Using WinSCP (Windows GUI Alternative)

If you prefer a GUI for copying files from the server:
1. Download WinSCP: https://winscp.net/eng/download.php
2. Connect to: Host=`10.6.0.46`, User=`sujiv1`, Pass=`sujiv1`, Port=22
3. Download `/home/sujiv1/v2ai/artifacts/` to your local machine

---

## Service URLs After Deployment

| Service       | URL |
|---|---|
| UI (Streamlit) | `https://v2ai-ui-XXXXX-XX.run.app` |
| API (FastAPI)  | `https://v2ai-api-XXXXX-XX.run.app` |
| API Docs       | `https://v2ai-api-XXXXX-XX.run.app/docs` |
| MLflow         | Runs locally on server at `:5000` |

> **Note**: MLflow and Grafana are not deployed to Cloud Run in this config.
> You can access them via SSH port forwarding:
> ```bash
> ssh -L 5000:localhost:5000 -L 3000:localhost:3000 sujiv1@10.6.0.46
> ```
> Then open `http://localhost:5000` for MLflow and `http://localhost:3000` for Grafana.

---

## Environment Variables for Cloud Run

All sensitive credentials are set inline in `gcloud_deploy.sh`. If you need to
update them without redeploying, use:

```bash
gcloud run services update v2ai-api \
  --region asia-south1 \
  --update-env-vars HF_TOKEN=your_new_token
```

---

## Important Notes

- Cloud Run uses CPU only — the GPU profile is not applicable
- For GPU on Google Cloud, use **Vertex AI** or **GKE with GPU nodes** (requires billing)
- Default Cloud Run memory is 4GB for API, 1GB for UI — increase if needed
- Cloud SQL (PostgreSQL) costs ~$7/month on `db-f1-micro` tier

---

## Teardown (To Avoid Costs)

```bash
# Delete all Cloud Run services
gcloud run services delete v2ai-api --region asia-south1 --quiet
gcloud run services delete v2ai-ui --region asia-south1 --quiet

# Delete Cloud SQL instance
gcloud sql instances delete v2ai-postgres --quiet
```
