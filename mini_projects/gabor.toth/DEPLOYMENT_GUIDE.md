# Deployment Guide: Local VPS Deployment for RAG Agent

## Overview

This guide provides instructions for deploying the Gábor Tóth RAG Agent to a local VPS using GitHub Actions. The workflow handles automated deployment, health checks, data backup, and graceful service restarts.

**Deployment Model**: Manual trigger via GitHub Actions → SSH to VPS → Git pull → Docker Compose restart

---

## Prerequisites

### On Your Local VPS

1. **Operating System**: Linux (Ubuntu 20.04+ recommended)
2. **Required Software**:
   - Docker 20.10+ (`docker --version`)
   - Docker Compose 2.0+ (`docker-compose --version`)
   - Git (`git --version`)
   - SSH server (sshd running)
   - curl (for health checks)

3. **User Setup**:
   - Create deployment user: `sudo useradd -m -s /bin/bash deploy`
   - Add to docker group: `sudo usermod -aG docker deploy`
   - Create deployment directory: `sudo mkdir -p /home/deploy/rag-agent && sudo chown deploy:deploy /home/deploy/rag-agent`

4. **SSH Access**:
   - Generate ED25519 key pair on your local machine: `ssh-keygen -t ed25519 -f ~/.ssh/deploy_key`
   - Copy public key to VPS: `ssh-copy-id -i ~/.ssh/deploy_key.pub deploy@your-vps-ip`

5. **Environment Setup**:
   - Create `.env` file on VPS: `/home/deploy/rag-agent/.env`
   - Add required environment variables:
     ```
     OPENAI_API_KEY=sk-...your-api-key...
     ```

6. **Verify Setup**:
   ```bash
   ssh deploy@your-vps-ip "cd /home/deploy/rag-agent && docker-compose ps"
   ```

---

## GitHub Actions Setup

### 1. Generate SSH Key for Deployment

**On your local machine**:
```bash
# Generate ED25519 key (secure and efficient)
ssh-keygen -t ed25519 -f ~/rag-deploy-key -N ""
# Or with passphrase:
ssh-keygen -t ed25519 -f ~/rag-deploy-key
```

**Verify the key**:
```bash
cat ~/rag-deploy-key
cat ~/rag-deploy-key.pub
```

### 2. Add GitHub Secrets

Go to your GitHub repository → **Settings** → **Secrets and variables** → **Actions**

Add these secrets:

| Secret Name | Value | Example |
|------------|-------|---------|
| `DEPLOY_HOST` | VPS IP or hostname | `192.168.1.100` or `deploy.example.com` |
| `DEPLOY_USER` | SSH user on VPS | `deploy` |
| `DEPLOY_SSH_KEY` | Private SSH key content (paste entire file) | `-----BEGIN OPENSSH PRIVATE KEY-----\n...` |

**⚠️ Important**: 
- Paste the **entire private key file** content (including `-----BEGIN OPENSSH PRIVATE KEY-----` lines)
- Never share this key
- Keep backups in a secure location

### 3. Verify Secrets Configuration

```bash
# Test SSH connection from GitHub (use workflow UI)
# Or test locally:
ssh -i ~/rag-deploy-key deploy@192.168.1.100 "echo 'SSH works!'"
```

---

## Deployment Methods

### Method 1: GitHub Web UI (Recommended for Manual Deployments)

1. Go to your repository on GitHub
2. Click **Actions** tab
3. Select **Deploy RAG Agent to Local VPS** workflow
4. Click **Run workflow** button
5. Choose environment (default: `production`)
6. Click **Run workflow**
7. Monitor the workflow execution in real-time

**Expected output**:
```
✓ Code updated successfully
✓ Services updated and restarted
✓ Backend is healthy
✓ Frontend is responding
✓ Smoke test passed
✅ Deployment completed successfully!
```

### Method 2: GitHub CLI (For Automation)

```bash
gh workflow run deploy-local-server.yml \
  --ref main \
  -f environment=production
```

### Method 3: GitHub REST API

```bash
curl -X POST \
  https://api.github.com/repos/YOUR_OWNER/YOUR_REPO/actions/workflows/deploy-local-server.yml/dispatches \
  -H "Accept: application/vnd.github.v3+json" \
  -H "Authorization: token YOUR_GITHUB_TOKEN" \
  -d '{
    "ref": "main",
    "inputs": {
      "environment": "production"
    }
  }'
```

---

## Detailed Workflow Steps

### Step 1: Code Checkout
- Pulls the latest code from the repository
- Ensures we're deploying the correct version

### Step 2: SSH Setup
- Configures SSH authentication using the stored private key
- Adds VPS to known_hosts to prevent "host verification" prompts
- Permissions set to 600 (secure) on private key

### Step 3: Pre-deployment Health Check (Informational)
- Checks current service status before deployment
- Non-blocking (continues even if services are down)
- Useful for understanding current state

### Step 4: Data Backup
- Creates timestamped backup directory: `data/.backup_YYYYMMDD_HHMMSS/`
- Backs up:
  - User profiles (`data/users/`)
  - Chat sessions (`data/sessions/`)
- Allows easy rollback if needed
- Non-blocking if backup fails (service continues)

### Step 5: Git Pull
- Fetches latest changes from GitHub
- Checks out main branch
- Pulls latest commits
- Fails workflow if git pull fails (prevents deploying broken state)

### Step 6: Docker Update (Graceful Restart)
- Pulls latest Docker images: `docker-compose pull`
- Restarts services with new code: `docker-compose up -d --build`
- Builds any new images needed
- Maintains data persistence

### Step 7: Backend Health Check
- Polls `/api/health` endpoint (max 30 attempts, 10s intervals = 5 min timeout)
- Verifies response contains `"ok"` field
- **Blocking**: Workflow fails if backend doesn't respond
- Ensures application is operational before considering deployment successful

### Step 8: Frontend Health Check (Non-blocking)
- Polls frontend HTTP (max 15 attempts, 5s intervals = 75s timeout)
- Accepts HTTP 200 or 301 status
- **Non-blocking**: Continues even if frontend times out
- Frontend may be loading assets, so less strict than backend

### Step 9: Smoke Test
- Makes HTTP GET request to `/api/health`
- Validates response contains `"ok"`
- Confirms backend is functional with correct response format
- Catches configuration issues

### Step 10: Log Service Status
- Displays `docker-compose ps` (running containers)
- Shows last 20 lines of logs from all services
- Displays resource usage (CPU, memory)
- Helpful for debugging if health checks fail

### Step 11: Success Summary
- Confirms all services are running
- Displays access URLs and service endpoints
- Notes backup location for rollback

### Step 12: Failure Handling
- Only runs if workflow failed
- Provides troubleshooting checklist (6 common issues)
- Shows rollback procedure using timestamped backups

### Step 13: Cleanup
- Removes SSH private key from GitHub runner
- Always runs (even if workflow failed)
- Prevents key from being left in logs or temporary files

---

## Troubleshooting

### Issue 1: SSH Connection Failed

**Symptoms**:
```
Permission denied (publickey)
or
Could not resolve hostname
```

**Solutions**:
1. Verify VPS IP/hostname:
   ```bash
   ping your-vps-ip
   ssh deploy@your-vps-ip
   ```

2. Check SSH key permissions:
   ```bash
   chmod 600 ~/.ssh/deploy_key
   ssh-add ~/.ssh/deploy_key
   ```

3. Verify SSH key is added to VPS:
   ```bash
   cat ~/.ssh/deploy_key.pub | ssh deploy@your-vps-ip "cat >> .ssh/authorized_keys"
   ```

4. Test from command line:
   ```bash
   ssh -i ~/.ssh/deploy_key deploy@your-vps-ip "echo 'Connected!'"
   ```

### Issue 2: Git Pull Failed

**Symptoms**:
```
fatal: 'origin' does not appear to be a 'git' repository
or
Permission denied (publickey).
```

**Solutions**:
1. Verify git is initialized on VPS:
   ```bash
   ssh deploy@your-vps-ip "cd /home/deploy/rag-agent && git status"
   ```

2. Clone repository if not present:
   ```bash
   ssh deploy@your-vps-ip "cd /home/deploy && git clone https://github.com/YOUR_OWNER/YOUR_REPO rag-agent"
   ```

3. If using SSH URLs, ensure deploy user has GitHub SSH access:
   ```bash
   ssh deploy@your-vps-ip "ssh -T git@github.com"
   ```

### Issue 3: Docker Build Failed

**Symptoms**:
```
ERROR: Service 'backend' failed to build
or
ENOSPC: no space left on device
```

**Solutions**:
1. Check disk space on VPS:
   ```bash
   ssh deploy@your-vps-ip "df -h"
   ```

2. Clean up Docker:
   ```bash
   ssh deploy@your-vps-ip "docker system prune -a"
   ```

3. Check docker-compose.yml syntax:
   ```bash
   ssh deploy@your-vps-ip "cd /home/deploy/rag-agent && docker-compose config"
   ```

4. Verify Docker daemon is running:
   ```bash
   ssh deploy@your-vps-ip "sudo systemctl status docker"
   ```

### Issue 4: Backend Health Check Timeout

**Symptoms**:
```
Backend health check failed after 30 attempts
```

**Solutions**:
1. Check backend logs:
   ```bash
   ssh deploy@your-vps-ip "cd /home/deploy/rag-agent && docker-compose logs backend --tail=50"
   ```

2. Verify OPENAI_API_KEY is set:
   ```bash
   ssh deploy@your-vps-ip "grep OPENAI_API_KEY /home/deploy/rag-agent/.env"
   ```

3. Test endpoint manually:
   ```bash
   ssh deploy@your-vps-ip "curl -s http://localhost:8000/api/health | head -20"
   ```

4. Check if port 8000 is exposed:
   ```bash
   ssh deploy@your-vps-ip "docker-compose ps | grep backend"
   ```

### Issue 5: Frontend Health Check Timeout

**Symptoms**:
```
Frontend check timed out (may still be healthy)
```

**Solutions** (non-critical, but if concerning):
1. Check frontend logs:
   ```bash
   ssh deploy@your-vps-ip "cd /home/deploy/rag-agent && docker-compose logs frontend --tail=50"
   ```

2. Verify port 3000 is exposed:
   ```bash
   ssh deploy@your-vps-ip "docker-compose ps | grep frontend"
   ```

3. Test nginx health:
   ```bash
   ssh deploy@your-vps-ip "curl -s http://localhost:3000 -I"
   ```

### Issue 6: Data Backup Failed

**Symptoms**:
```
cp: cannot create directory (Permission denied)
```

**Solutions**:
1. Check data directory ownership:
   ```bash
   ssh deploy@your-vps-ip "ls -la /home/deploy/rag-agent/data/"
   ```

2. Ensure deploy user owns the directory:
   ```bash
   ssh deploy@your-vps-ip "sudo chown -R deploy:deploy /home/deploy/rag-agent"
   ```

3. Check disk space:
   ```bash
   ssh deploy@your-vps-ip "df -h /home/deploy/rag-agent"
   ```

---

## Monitoring and Maintenance

### Check Service Status

```bash
# From any machine with SSH access to VPS:
ssh deploy@your-vps-ip "cd /home/deploy/rag-agent && docker-compose ps"

# Expected output:
# NAME                COMMAND                  SERVICE             STATUS              PORTS
# rag-agent-backend-1   "python3 main.py"        backend             Up 2 hours          8000->8000/tcp
# rag-agent-frontend-1  "nginx -g daemon off"    frontend            Up 2 hours          3000->3000/tcp
```

### View Live Logs

```bash
# All services:
ssh deploy@your-vps-ip "cd /home/deploy/rag-agent && docker-compose logs -f"

# Specific service:
ssh deploy@your-vps-ip "cd /home/deploy/rag-agent && docker-compose logs -f backend"
```

### Monitor Resource Usage

```bash
ssh deploy@your-vps-ip "docker stats --no-stream"
```

### Check API Health

```bash
# From your local machine:
curl -s http://your-vps-ip:8000/api/health | jq .
# Expected response: {"ok": true, "timestamp": "2026-02-01T21:30:00Z"}

# Access frontend:
curl -s http://your-vps-ip:3000 | head -20
```

---

## Rollback Procedure

### Automatic Rollback

If a deployment fails, the previous version remains running because Docker Compose restarts fail gracefully.

### Manual Rollback Using Backups

```bash
ssh deploy@your-vps-ip << 'EOF'
cd /home/deploy/rag-agent

# List available backups
ls -la data/.backup_*/

# Restore from specific backup (example):
BACKUP_DIR="data/.backup_20260201_213000"
cp -r $BACKUP_DIR/users data/users
cp -r $BACKUP_DIR/sessions data/sessions

# Restart services
docker-compose restart

# Verify
docker-compose ps
curl -s http://localhost:8000/api/health | jq .
EOF
```

### Full Rollback (Code + Data)

```bash
ssh deploy@your-vps-ip << 'EOF'
cd /home/deploy/rag-agent

# Reset to previous git commit
git log --oneline -5  # See recent commits
git reset --hard <commit-hash>

# Restore data
BACKUP_DIR="data/.backup_20260201_213000"
cp -r $BACKUP_DIR/users data/users
cp -r $BACKUP_DIR/sessions data/sessions

# Restart with old version
docker-compose down
docker-compose up -d

# Verify
docker-compose ps
curl -s http://localhost:8000/api/health | jq .
EOF
```

---

## Future Enhancements

### 1. Slack Notifications

Add to your workflow to notify on success/failure:

```yaml
- name: Notify Slack on Success
  if: success()
  uses: slackapi/slack-github-action@v1
  with:
    payload: |
      {
        "text": "✅ RAG Agent deployed successfully",
        "blocks": [
          {
            "type": "section",
            "text": {
              "type": "mrkdwn",
              "text": "*Deployment Successful*\nCommit: ${{ github.sha }}\nActor: ${{ github.actor }}"
            }
          }
        ]
      }
  env:
    SLACK_WEBHOOK_URL: ${{ secrets.SLACK_WEBHOOK_URL }}
```

### 2. Automatic Rollback on Failed Health Check

```yaml
- name: Automatic Rollback
  if: failure()
  run: |
    ssh -i ~/.ssh/deploy_key ${{ secrets.DEPLOY_USER }}@${{ secrets.DEPLOY_HOST }} << 'EOF'
    cd ${{ env.DEPLOY_PATH }}
    LATEST_BACKUP=$(ls -t data/.backup_* | head -1)
    cp -r $LATEST_BACKUP/users data/
    cp -r $LATEST_BACKUP/sessions data/
    docker-compose restart
    echo "Auto-rolled back to: $LATEST_BACKUP"
    EOF
```

### 3. Email Notifications

Use GitHub's built-in email on failure, or add:

```yaml
- name: Send Email on Failure
  if: failure()
  uses: dawidd6/action-send-mail@v3
  with:
    server_address: ${{ secrets.MAIL_SERVER }}
    server_port: 465
    username: ${{ secrets.MAIL_USERNAME }}
    password: ${{ secrets.MAIL_PASSWORD }}
    subject: "❌ RAG Agent Deployment Failed"
    to: ${{ secrets.ADMIN_EMAIL }}
    from: "deployments@rag-agent.com"
    body: "Deployment failed. Check GitHub Actions for details: ${{ github.server_url }}/${{ github.repository }}/actions/runs/${{ github.run_id }}"
```

---

## Pre-Deployment Checklist

Before running your first deployment:

- [ ] VPS has Docker and Docker Compose installed
- [ ] SSH key pair generated and added to VPS
- [ ] GitHub Secrets configured (DEPLOY_HOST, DEPLOY_USER, DEPLOY_SSH_KEY)
- [ ] `.env` file exists on VPS with OPENAI_API_KEY
- [ ] Git repository cloned to `/home/deploy/rag-agent` on VPS
- [ ] Deploy user has permissions for docker and /home/deploy/rag-agent directory
- [ ] Ports 3000 (frontend) and 8000 (backend) are accessible
- [ ] SSH connection tested: `ssh -i deploy_key deploy@vps-ip`
- [ ] Workflow file created at `.github/workflows/deploy-local-server.yml`
- [ ] README or documentation updated with deployment links

---

## Support and Documentation

For additional information:
- [GitHub Actions Documentation](https://docs.github.com/en/actions)
- [Docker Compose Documentation](https://docs.docker.com/compose/)
- [SSH Best Practices](https://linux.die.net/man/1/ssh-keygen)
- See project README for architecture and application details

---

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | 2026-02-01 | Initial release with GitHub Actions workflow for local VPS deployment |

