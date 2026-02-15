# HiveMind Docker Deployment Guide

> **Version**: 1.11.1
> **Last Updated**: 2026-02-15
> **Related**: R007 Docker Deployment Configuration

## Table of Contents

- [Overview](#overview)
- [Architecture](#architecture)
- [Prerequisites](#prerequisites)
- [Quick Start](#quick-start)
- [Environment Configuration](#environment-configuration)
- [Production Deployment](#production-deployment)
- [Development Workflow](#development-workflow)
- [Service Management](#service-management)
- [Health Checks & Monitoring](#health-checks--monitoring)
- [Troubleshooting](#troubleshooting)
- [Security Best Practices](#security-best-practices)
- [Maintenance & Updates](#maintenance--updates)
- [Performance Tuning](#performance-tuning)

---

## Overview

HiveMind's Docker setup provides a production-ready, containerized deployment solution with the following features:

- **Multi-stage builds** for optimized image sizes
- **Service orchestration** with Docker Compose
- **Nginx reverse proxy** for frontend serving and API routing
- **Health checks** for all services
- **Volume persistence** for database data
- **Development mode** with hot reload
- **Network isolation** for security

### Services

| Service | Purpose | Port | Image Base |
|---------|---------|------|------------|
| **frontend** | React SPA + Nginx | 80 | nginx:alpine |
| **backend** | Express API + Socket.IO | 8765 | node:20-alpine |
| **postgres** | PostgreSQL database | 5432 | postgres:15-alpine |
| **redis** | Session storage & cache | 6379 | redis:7-alpine |

---

## Architecture

```
┌─────────────────────────────────────────────────┐
│                   Client Browser                │
└────────────────────┬────────────────────────────┘
                     │ HTTP/HTTPS (Port 80/443)
                     ▼
┌─────────────────────────────────────────────────┐
│            Frontend (Nginx + React)             │
│  • Serves static files                          │
│  • Proxies /api/* to backend                    │
│  • Proxies /socket.io/* to backend (WebSocket)  │
└────────┬────────────────────────────────────────┘
         │ Internal Network
         ▼
┌─────────────────────────────────────────────────┐
│        Backend (Node.js + Express)              │
│  • REST API endpoints                           │
│  • Socket.IO WebSocket server                   │
│  • Authentication (JWT + OAuth2 + 2FA)          │
└────┬────────────────────────┬───────────────────┘
     │                        │
     │ PostgreSQL             │ Redis
     ▼                        ▼
┌──────────────┐         ┌──────────────┐
│   Postgres   │         │    Redis     │
│  (Database)  │         │   (Cache)    │
└──────────────┘         └──────────────┘
```

---

## Prerequisites

### System Requirements

- **OS**: Linux (Ubuntu 20.04+), macOS (10.15+), Windows 10/11 with WSL2
- **RAM**: Minimum 4GB, recommended 8GB+
- **Disk**: 10GB+ free space
- **CPU**: 2+ cores recommended

### Software Dependencies

1. **Docker Engine** 24.0+
   ```bash
   docker --version
   ```

2. **Docker Compose** 2.20+
   ```bash
   docker compose version
   ```

3. **Make** (optional, for Makefile commands)
   ```bash
   make --version
   ```

### Installation

**Linux (Ubuntu/Debian)**:
```bash
# Install Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh
sudo usermod -aG docker $USER

# Install Docker Compose (usually included)
docker compose version
```

**macOS**:
```bash
# Install Docker Desktop
brew install --cask docker
```

**Windows**:
- Install Docker Desktop from https://www.docker.com/products/docker-desktop/
- Enable WSL2 backend

---

## Quick Start

### 1. Clone Repository

```bash
git clone <repository-url>
cd HiveMind
```

### 2. Configure Environment

```bash
# Copy environment template
cp .env.docker.example .env.docker

# Edit with your values
nano .env.docker
```

**Critical Variables** (must change):
```env
# Security - MUST change these!
POSTGRES_PASSWORD=your_strong_password_here
REDIS_PASSWORD=your_redis_password_here
JWT_SECRET=your_random_secret_key_here

# OAuth (if using)
GOOGLE_CLIENT_ID=your_google_client_id
GOOGLE_CLIENT_SECRET=your_google_client_secret
GITHUB_CLIENT_ID=your_github_client_id
GITHUB_CLIENT_SECRET=your_github_client_secret
```

### 3. Build & Start

**Using Make** (recommended):
```bash
make build  # Build all images
make up     # Start all services
make logs   # View logs
```

**Using Docker Compose**:
```bash
docker compose build
docker compose --env-file .env.docker up -d
docker compose logs -f
```

### 4. Verify Deployment

```bash
# Check service health
make health

# Or manually
docker ps --filter "name=hivemind"
```

Expected output:
```
NAME                STATUS                  PORTS
hivemind-frontend   Up (healthy)           0.0.0.0:80->80/tcp
hivemind-backend    Up (healthy)           8765/tcp
hivemind-postgres   Up (healthy)           5432/tcp
hivemind-redis      Up (healthy)           6379/tcp
```

### 5. Access Application

- **Web Interface**: http://localhost
- **API**: http://localhost/api/v1
- **Health Check**: http://localhost/health

---

## Environment Configuration

### Complete Environment Variables Reference

#### Application Settings

```env
NODE_ENV=production           # Environment mode (development|production)
FRONTEND_PORT=80              # Frontend exposed port
BACKEND_PORT=8765             # Backend internal port
FRONTEND_URL=http://localhost # Public frontend URL
```

#### Database Configuration

```env
POSTGRES_USER=hivemind        # Database username
POSTGRES_PASSWORD=***         # Database password (CHANGE THIS!)
POSTGRES_DB=hivemind          # Database name
POSTGRES_PORT=5432            # Database port
```

#### Redis Configuration

```env
REDIS_PASSWORD=***            # Redis password (CHANGE THIS!)
REDIS_PORT=6379               # Redis port
```

#### JWT Authentication

```env
JWT_SECRET=***                # Secret key for signing JWTs (CHANGE THIS!)
JWT_EXPIRES_IN=15m            # Access token expiry
REFRESH_TOKEN_EXPIRES_IN=7d   # Refresh token expiry
```

#### Google OAuth (Optional)

```env
GOOGLE_CLIENT_ID=your_google_client_id
GOOGLE_CLIENT_SECRET=your_google_client_secret
GOOGLE_CALLBACK_URL=http://localhost/api/v1/auth/google/callback
```

#### GitHub OAuth (Optional)

```env
GITHUB_CLIENT_ID=your_github_client_id
GITHUB_CLIENT_SECRET=your_github_client_secret
GITHUB_CALLBACK_URL=http://localhost/api/v1/auth/github/callback
```

#### SMTP Email (Optional)

```env
SMTP_HOST=smtp.gmail.com      # SMTP server
SMTP_PORT=587                 # SMTP port
SMTP_SECURE=false             # Use TLS
SMTP_USER=your-email@gmail.com
SMTP_PASS=your-app-password   # App password (not regular password)
FROM_EMAIL=noreply@hivemind.com
FROM_NAME=HiveMind
```

### Generating Secure Secrets

**JWT_SECRET**:
```bash
openssl rand -base64 64
```

**POSTGRES_PASSWORD / REDIS_PASSWORD**:
```bash
openssl rand -base64 32
```

---

## Production Deployment

### Pre-Deployment Checklist

- [ ] Environment variables configured (`.env.docker`)
- [ ] Secrets changed from defaults
- [ ] OAuth credentials obtained (if using)
- [ ] SMTP configured (if using email)
- [ ] Domain name configured
- [ ] SSL certificates ready (if using HTTPS)
- [ ] Firewall rules configured
- [ ] Backup strategy planned
- [ ] Monitoring tools ready

### Production Build

1. **Set Production Environment**:
   ```bash
   echo "NODE_ENV=production" >> .env.docker
   ```

2. **Build Optimized Images**:
   ```bash
   make build
   ```

3. **Start Services**:
   ```bash
   make prod
   ```

4. **Run Database Migrations** (if needed):
   ```bash
   docker compose exec backend npm run db:migrate
   ```

5. **Verify All Services Healthy**:
   ```bash
   make health
   ```

### SSL/HTTPS Configuration

For HTTPS, add a reverse proxy (Caddy, Traefik, or Nginx) in front of the frontend service.

**Example with Caddy**:

`Caddyfile`:
```
yourdomain.com {
  reverse_proxy localhost:80
  encode gzip
}
```

**Update environment**:
```env
FRONTEND_URL=https://yourdomain.com
GOOGLE_CALLBACK_URL=https://yourdomain.com/api/v1/auth/google/callback
GITHUB_CALLBACK_URL=https://yourdomain.com/api/v1/auth/github/callback
```

### Cloud Deployment

#### AWS EC2

```bash
# 1. Launch EC2 instance (Ubuntu 22.04, t3.medium or larger)
# 2. Install Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh

# 3. Clone repository
git clone <repository-url>
cd HiveMind

# 4. Configure environment
cp .env.docker.example .env.docker
nano .env.docker

# 5. Start services
sudo docker compose --env-file .env.docker up -d

# 6. Configure security group to allow port 80
```

#### DigitalOcean Droplet

Similar to EC2, use a Docker-ready droplet:
- Choose "Docker on Ubuntu" from Marketplace
- Follow same steps as EC2

#### Google Cloud Run

For Cloud Run, you'll need to modify the setup to use Cloud SQL and Memorystore instead of containerized postgres/redis.

---

## Development Workflow

### Development Mode

Development mode includes:
- Hot reload for backend changes
- Vite dev server for frontend
- Volume mounts for live code updates

**Start Development Environment**:
```bash
make dev
```

Or:
```bash
docker compose -f docker-compose.dev.yml up
```

**Access**:
- Frontend: http://localhost:5173 (Vite dev server)
- Backend: http://localhost:8765
- API: http://localhost:8765/api/v1

### Development Workflow

1. **Edit Code Locally**:
   - Frontend code in `src/renderer/` (auto-reload via Vite)
   - Backend code in `src/` (auto-reload via nodemon)

2. **View Logs**:
   ```bash
   docker compose -f docker-compose.dev.yml logs -f backend
   docker compose -f docker-compose.dev.yml logs -f frontend
   ```

3. **Run Tests Inside Container**:
   ```bash
   docker compose exec backend npm test
   ```

4. **Database Operations**:
   ```bash
   # Generate migration
   docker compose exec backend npm run db:generate

   # Run migration
   docker compose exec backend npm run db:migrate

   # Open Drizzle Studio
   docker compose exec backend npm run db:studio
   ```

### Switching Between Modes

**Development → Production**:
```bash
docker compose -f docker-compose.dev.yml down
make prod
```

**Production → Development**:
```bash
make down
make dev
```

---

## Service Management

### Starting Services

```bash
# All services (production)
make up

# Specific service
docker compose up backend -d

# With build
make build && make up
```

### Stopping Services

```bash
# All services
make down

# Specific service
docker compose stop backend

# Stop and remove containers
docker compose down
```

### Restarting Services

```bash
# All services
make restart

# Specific service
docker compose restart backend
```

### Viewing Logs

```bash
# All services
make logs

# Specific service
docker compose logs -f backend

# Last 100 lines
docker compose logs --tail=100 backend
```

### Executing Commands

```bash
# Interactive shell in backend
docker compose exec backend sh

# Run npm command
docker compose exec backend npm run db:migrate

# Execute SQL in postgres
docker compose exec postgres psql -U hivemind -d hivemind
```

### Cleaning Up

```bash
# Remove containers and networks
make down

# Remove containers, networks, and volumes (DATA LOSS!)
make clean

# Remove all Docker resources (prune)
docker system prune -a --volumes
```

---

## Health Checks & Monitoring

### Built-in Health Checks

All services have health checks configured:

| Service | Health Check | Interval |
|---------|--------------|----------|
| **frontend** | HTTP GET / | 30s |
| **backend** | HTTP GET /health | 30s |
| **postgres** | pg_isready | 10s |
| **redis** | redis-cli ping | 10s |

### Checking Service Health

```bash
# All services
make health

# Detailed status
docker compose ps

# Inspect specific service
docker inspect hivemind-backend --format='{{.State.Health.Status}}'
```

### Health Check Endpoints

- **Frontend**: http://localhost/health (returns 200 OK)
- **Backend**: http://localhost/api/v1/health (returns JSON status)

### Monitoring Logs

```bash
# Real-time logs for all services
docker compose logs -f

# Filter by service
docker compose logs -f backend | grep ERROR

# Export logs to file
docker compose logs --since 1h > hivemind-logs.txt
```

### Resource Usage

```bash
# View container resource usage
docker stats

# Specific service
docker stats hivemind-backend
```

### Setting Up External Monitoring

**Prometheus + Grafana**:
1. Expose metrics endpoint in backend (`/metrics`)
2. Configure Prometheus to scrape Docker containers
3. Import Grafana dashboard for Node.js

**ELK Stack**:
1. Configure Docker to use JSON file logging driver
2. Set up Filebeat to ship logs to Elasticsearch
3. Visualize in Kibana

---

## Troubleshooting

### Common Issues

#### 1. Services Won't Start

**Symptom**: `docker compose up` fails

**Solutions**:
```bash
# Check for port conflicts
sudo lsof -i :80
sudo lsof -i :8765

# Check Docker daemon
sudo systemctl status docker

# View detailed error
docker compose up (without -d flag)

# Rebuild from scratch
docker compose down
docker compose build --no-cache
docker compose up
```

#### 2. Database Connection Failed

**Symptom**: Backend logs show `ECONNREFUSED` for postgres

**Solutions**:
```bash
# Check postgres is healthy
docker compose ps postgres

# Verify postgres logs
docker compose logs postgres

# Check environment variables
docker compose exec backend env | grep POSTGRES

# Wait for postgres to be ready (already in depends_on)
docker compose restart backend
```

#### 3. Frontend Shows 502 Bad Gateway

**Symptom**: Nginx returns 502 when accessing API

**Solutions**:
```bash
# Check backend is running
docker compose ps backend

# Check backend logs
docker compose logs backend

# Verify Nginx config
docker compose exec frontend nginx -t

# Restart services
docker compose restart backend frontend
```

#### 4. WebSocket Connection Failed

**Symptom**: Socket.IO connection fails in browser console

**Solutions**:
```bash
# Check Nginx WebSocket proxy config
docker compose exec frontend cat /etc/nginx/conf.d/default.conf

# Verify backend Socket.IO is running
docker compose logs backend | grep socket.io

# Check for proxy_set_header Upgrade
curl -i -N -H "Connection: Upgrade" -H "Upgrade: websocket" http://localhost/socket.io/
```

#### 5. Permission Denied Errors

**Symptom**: Backend can't write files or access resources

**Solutions**:
```bash
# Check container user
docker compose exec backend id

# Fix volume permissions (if using bind mounts)
sudo chown -R 1001:1001 ./data

# Check SELinux (Linux)
sestatus
sudo setenforce 0  # Temporarily disable for testing
```

#### 6. Out of Disk Space

**Symptom**: Build fails or containers stop unexpectedly

**Solutions**:
```bash
# Check disk usage
df -h

# Remove unused Docker resources
docker system prune -a --volumes

# Remove old images
docker image prune -a

# Check Docker disk usage
docker system df
```

### Debugging Commands

```bash
# Check container logs
docker compose logs --tail=100 <service>

# Interactive shell in container
docker compose exec <service> sh

# Inspect container
docker inspect <container_id>

# Check network connectivity between services
docker compose exec backend ping postgres
docker compose exec backend nc -zv postgres 5432

# View environment variables
docker compose exec <service> env

# Check process list
docker compose exec <service> ps aux
```

### Resetting Everything

If all else fails, complete reset:

```bash
# Stop all containers
docker compose down -v

# Remove all HiveMind images
docker images | grep hivemind | awk '{print $3}' | xargs docker rmi -f

# Remove all volumes
docker volume ls | grep hivemind | awk '{print $2}' | xargs docker volume rm

# Rebuild from scratch
make build
make up
```

---

## Security Best Practices

### 1. Secrets Management

**Don't**:
- ❌ Commit `.env.docker` to git
- ❌ Use default passwords in production
- ❌ Share secrets in plain text

**Do**:
- ✅ Use `.env.docker.example` as template
- ✅ Generate strong random secrets
- ✅ Use Docker Secrets or HashiCorp Vault in production
- ✅ Rotate secrets regularly

**Using Docker Secrets**:
```bash
echo "my_secret_password" | docker secret create postgres_password -
```

Then reference in `docker-compose.yml`:
```yaml
secrets:
  postgres_password:
    external: true
services:
  postgres:
    secrets:
      - postgres_password
```

### 2. Network Security

- **Internal Network**: Services communicate on internal Docker network
- **Exposed Ports**: Only frontend (80) is exposed to host
- **Firewall**: Configure host firewall to restrict access

```bash
# UFW example (Ubuntu)
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw enable
```

### 3. Container Security

- **Non-root User**: Backend runs as user `nodejs` (UID 1001)
- **Read-only Root**: Consider adding `read_only: true` to containers
- **No Privileged Mode**: Never use `privileged: true`
- **Drop Capabilities**: Add `cap_drop: [ALL]` where possible

### 4. Image Security

```bash
# Scan images for vulnerabilities
docker scan hivemind-backend

# Keep base images updated
docker compose pull
docker compose build --pull
```

### 5. SSL/TLS

Always use HTTPS in production:
- Use Let's Encrypt for free certificates
- Configure HSTS headers
- Redirect HTTP to HTTPS

### 6. Rate Limiting

Backend includes express-rate-limit middleware. Configure in production:

```env
RATE_LIMIT_WINDOW_MS=900000  # 15 minutes
RATE_LIMIT_MAX=100           # Max requests per window
```

### 7. CORS Configuration

Update CORS settings for production domains:

```typescript
// src/api/middleware/cors.ts
const allowedOrigins = [
  'https://yourdomain.com',
  'https://www.yourdomain.com'
];
```

---

## Maintenance & Updates

### Updating Application

```bash
# 1. Pull latest code
git pull origin main

# 2. Rebuild images
make build

# 3. Restart services (graceful)
make restart

# 4. Or recreate containers (downtime)
docker compose up -d --force-recreate
```

### Updating Dependencies

```bash
# Update npm packages
npm update

# Rebuild images
make build

# Restart
make up
```

### Database Migrations

```bash
# Create migration
docker compose exec backend npm run db:generate

# Apply migration
docker compose exec backend npm run db:migrate

# Rollback (if needed)
docker compose exec backend npm run db:drop
```

### Backup & Restore

**Backup Database**:
```bash
# PostgreSQL
docker compose exec postgres pg_dump -U hivemind hivemind > backup.sql

# Or automated
docker compose exec postgres pg_dump -U hivemind -Fc hivemind > backup_$(date +%Y%m%d).dump
```

**Restore Database**:
```bash
# From SQL dump
docker compose exec -T postgres psql -U hivemind hivemind < backup.sql

# From custom format
docker compose exec postgres pg_restore -U hivemind -d hivemind backup.dump
```

**Backup Redis**:
```bash
docker compose exec redis redis-cli SAVE
docker cp hivemind-redis:/data/dump.rdb ./redis-backup.rdb
```

**Backup Volumes**:
```bash
# Stop services
make down

# Backup volume
docker run --rm -v hivemind_postgres_data:/data -v $(pwd):/backup alpine tar czf /backup/postgres_volume.tar.gz /data

# Restart
make up
```

### Log Rotation

Configure Docker log rotation in `/etc/docker/daemon.json`:

```json
{
  "log-driver": "json-file",
  "log-opts": {
    "max-size": "10m",
    "max-file": "3"
  }
}
```

Then restart Docker:
```bash
sudo systemctl restart docker
```

---

## Performance Tuning

### Docker Resource Limits

Update `docker-compose.yml` to add resource limits:

```yaml
services:
  backend:
    deploy:
      resources:
        limits:
          cpus: '2.0'
          memory: 2G
        reservations:
          cpus: '1.0'
          memory: 1G
```

### PostgreSQL Tuning

Create `docker/postgres/postgresql.conf`:

```
# Memory
shared_buffers = 256MB
effective_cache_size = 1GB
maintenance_work_mem = 64MB
work_mem = 16MB

# Connections
max_connections = 100

# Performance
random_page_cost = 1.1  # For SSD
effective_io_concurrency = 200

# Logging
log_min_duration_statement = 1000  # Log slow queries (>1s)
```

Mount in `docker-compose.yml`:
```yaml
postgres:
  volumes:
    - ./docker/postgres/postgresql.conf:/etc/postgresql/postgresql.conf
  command: postgres -c config_file=/etc/postgresql/postgresql.conf
```

### Redis Tuning

```yaml
redis:
  command: >
    redis-server
    --maxmemory 512mb
    --maxmemory-policy allkeys-lru
    --save 60 1000
```

### Nginx Tuning

Update `docker/nginx/nginx.conf`:

```nginx
worker_processes auto;
worker_connections 2048;

# Enable caching
proxy_cache_path /var/cache/nginx levels=1:2 keys_zone=api_cache:10m max_size=1g inactive=60m;
```

### Build Performance

```bash
# Use BuildKit for faster builds
DOCKER_BUILDKIT=1 docker compose build

# Enable BuildKit by default
echo 'export DOCKER_BUILDKIT=1' >> ~/.bashrc
```

---

## Appendix

### File Structure

```
.
├── Dockerfile.frontend          # Frontend multi-stage build
├── Dockerfile.backend           # Backend multi-stage build
├── docker-compose.yml           # Production compose
├── docker-compose.dev.yml       # Development compose
├── .dockerignore                # Files to exclude from builds
├── .env.docker.example          # Environment template
├── Makefile                     # Convenience commands
├── docker/
│   └── nginx/
│       ├── nginx.conf           # Nginx main config
│       └── default.conf         # Server block config
└── .harness/
    └── DOCKER_DEPLOYMENT_GUIDE.md  # This file
```

### Useful Commands Reference

| Action | Command |
|--------|---------|
| Build images | `make build` |
| Start production | `make up` or `make prod` |
| Start development | `make dev` |
| Stop services | `make down` |
| View logs | `make logs` |
| Restart services | `make restart` |
| Check health | `make health` |
| Clean everything | `make clean` |
| Enter backend shell | `docker compose exec backend sh` |
| Run tests | `docker compose exec backend npm test` |
| Database migration | `docker compose exec backend npm run db:migrate` |

### Support & Resources

- **Documentation**: `.harness/` directory
- **Issues**: GitHub Issues
- **Docker Docs**: https://docs.docker.com
- **Docker Compose**: https://docs.docker.com/compose/

---

**Last Updated**: 2026-02-15
**Version**: 1.0
**Maintained By**: HiveMind Team
