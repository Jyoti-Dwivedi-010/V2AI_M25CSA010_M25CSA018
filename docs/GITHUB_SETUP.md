# GitHub Setup and Versioning Guide

## 1. Initialize repository locally
```bash
git init
git add .
git commit -m "feat: initial end-to-end MLOps LLMOps pipeline scaffold"
```

## 2. Create GitHub repository and set remote
```bash
git remote add origin <YOUR_GITHUB_REPO_URL>
git branch -M main
git push -u origin main
```

## 3. Branch strategy
- `main`: production branch
- `develop`: integration branch
- `feature/*`: new features
- `hotfix/*`: urgent fixes

## 4. Standard development cycle
```bash
git checkout develop
git pull
git checkout -b feature/<topic>
# code + tests

git add .
git commit -m "feat: <summary>"
git push -u origin feature/<topic>
```

Open PR from `feature/<topic>` to `develop`.

## 5. Release versioning
```bash
git checkout main
git pull
git tag v0.1.0
git push origin v0.1.0
```

## 6. Required GitHub secrets for CD
- `KUBE_CONFIG_DATA` (base64 encoded kubeconfig)

## 7. Optional protected branch rules
- Require PR review before merge
- Require status checks to pass
- Restrict direct pushes to `main`
