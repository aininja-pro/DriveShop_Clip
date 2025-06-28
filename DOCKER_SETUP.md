# Docker Setup for DriveShop Clip Tracking

## CURRENT WORKING SETUP ✅

**Container**: `driveshop_clip-app-1`  
**Port**: `8501` (Streamlit dashboard)  
**Compose File**: `docker-compose.yml` exists and works  
**Environment**: Uses `.env` file for secrets  
**Volumes**: Data, logs, and src folders are mounted

## COMMANDS THAT WORK

```bash
# Build and run (standard)
docker compose up --build -d

# Just run existing container
docker compose up -d

# Stop container
docker compose down

# Check running containers
docker ps

# View logs
docker compose logs -f

# Check specific app logs
docker compose logs -f app
```

## EXACT WORKING CONFIGURATION

### docker-compose.yml
```yaml
services:
  app:
    build: .
    ports:
      - '8501:8501'
    volumes:
      - ./data:/app/data
      - ./logs:/app/logs
      - ./src:/app/src
    env_file:
      - .env
    restart: unless-stopped
```

### Dockerfile Structure
```dockerfile
FROM python:3.11-slim
# Installs system dependencies for Playwright
# Copies requirements.txt and installs ALL Python deps
# Installs playwright browsers with --with-deps
# Copies source code and creates directories
# Runs Streamlit on port 8501
```

## IMPORTANT NOTES

- ✅ `requirements.txt` contains ALL dependencies (90 packages including streamlit-aggrid, playwright, etc.)
- ✅ `.env` file contains secrets (OPENAI_API_KEY, STREAMLIT_PASSWORD, SLACK_WEBHOOK_URL, etc.)
- ✅ App runs on `http://localhost:8501`
- ✅ Volumes mount data/, logs/, and src/ for persistence
- ❌ DON'T "simplify" dependencies - install everything from requirements.txt
- ❌ DON'T change the Dockerfile unless absolutely necessary
- ❌ DON'T remove playwright browser installation

## WHEN THINGS BREAK

1. Check if container is running: `docker ps`
2. Check logs: `docker compose logs -f app`
3. If Debian repository issues: May need to wait for upstream fix
4. Reset to working commit if needed: `git reset --hard [working-commit]`
5. **NEVER** install "simplified" dependencies - use full requirements.txt

## QUICK ONBOARDING FOR NEW CHATS

"This is a working DriveShop Clip Tracking system with Docker. Check DOCKER_SETUP.md for all details. Use `docker compose up -d` to run, access at localhost:8501. DON'T change Dockerfile or simplify dependencies." 