# GPU Server Setup Guide

Target server: `m25csa0xx@172.25.1.123`

## 1. Connect to server
```bash
ssh m25csa0xx@172.25.1.123
```

## 2. Install Docker and Kubernetes (k3s example)
```bash
sudo apt update
sudo apt install -y curl git
curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker $USER
curl -sfL https://get.k3s.io | sh -
sudo kubectl get nodes
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

## 5. Local server docker validation
```bash
docker compose --profile gpu up --build -d
```

## 6. Kubernetes deployment
```bash
kubectl apply -f k8s/namespace.yaml
kubectl apply -f k8s/configmap.yaml
kubectl apply -f k8s/postgres-pvc.yaml
kubectl apply -f k8s/postgres-deployment.yaml
kubectl apply -f k8s/minio-pvc.yaml
kubectl apply -f k8s/minio-deployment.yaml
kubectl apply -f k8s/mlflow-pvc.yaml
kubectl apply -f k8s/mlflow-deployment.yaml
kubectl apply -f k8s/api-deployment.yaml
kubectl apply -f k8s/ui-deployment.yaml
kubectl apply -f k8s/hpa-api.yaml
```

Optional GPU deployment:
```bash
kubectl apply -f k8s/api-deployment-gpu.yaml
```

## 7. Verify services
```bash
kubectl get pods -n major-project
kubectl get svc -n major-project
```

## 8. Troubleshooting quick checks
```bash
kubectl logs deployment/api -n major-project --tail=100
kubectl logs deployment/ui -n major-project --tail=100
kubectl logs deployment/mlflow -n major-project --tail=100
kubectl logs deployment/postgres -n major-project --tail=100
kubectl logs deployment/minio -n major-project --tail=100
```
