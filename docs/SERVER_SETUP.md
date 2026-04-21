# GPU Server Setup Guide (Docker Compose)

Target server: `m25csa0xx@172.25.1.123`

## 1. Connect to server
```bash
ssh m25csa0xx@172.25.1.123
```

## 2. Install Docker
```bash
sudo apt update
sudo apt install -y curl git
curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker $USER
```

## 3. Clone repository and prepare
```bash
git clone <YOUR_REPO_URL>
cd <YOUR_REPO_FOLDER>
cp .env.example .env
```

## 4. Validate GPU availability
```bash
nvidia-smi
```

## 5. Start stack
```bash
docker compose up --build -d
```

Optional GPU profile:
```bash
docker compose --profile gpu up --build -d
```

## 6. Verify services
```bash
docker compose ps
curl http://localhost:8000/health
```

## 7. Troubleshooting quick checks
```bash
docker compose logs api --tail=100
docker compose logs ui --tail=100
docker compose logs mlflow --tail=100
docker compose logs postgres --tail=100
docker compose logs minio --tail=100
```
