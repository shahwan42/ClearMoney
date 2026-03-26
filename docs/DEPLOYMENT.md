# Deployment Guide — Ubuntu VPS with Docker Compose

## Production Infrastructure

| Component | Details |
| --------- | ------- |
| Host | Hetzner VPS (`hetzner-keeper` SSH alias) |
| IP | `49.13.140.20` |
| Domain | `clearmoney.shahwan.me` (DNS A record → VPS IP) |
| URL | `https://clearmoney.shahwan.me` |
| OS | Ubuntu 22.04+ |
| Deploy dir | `~/ClearMoney` |
| Deploy method | `make deploy` — git push → SSH pull → docker compose rebuild |
| Reverse proxy | Caddy (containerized in docker-compose.prod.yml) |
| TLS | Auto-provisioned Let's Encrypt via Caddy, certs in `caddy_data` volume |
| Django app port | 8000 (internal only, not exposed to internet) |
| Public ports | 80 (HTTP → HTTPS redirect), 443 (HTTPS) |
| Database | PostgreSQL 16 (Alpine, containerized, port 5432 internal) |
| Env file | `.env.prod` on the VPS (not in git) |

## Architecture Notes

### Python Dependency Management

ClearMoney uses a **unified uv workspace** for both backend and e2e dependencies:

- **Root `pyproject.toml`**: Defines workspace members (`backend`, `e2e`)
- **Root `uv.lock`**: Single merged lockfile for all dependencies
- **Docker builds**: Copy root workspace config + backend pyproject + root lockfile → creates `/app/.venv` with backend dependencies only
- **No e2e dependencies in production**: Production Docker image is minimal and contains only backend requirements

See [CLAUDE.md](../CLAUDE.md) under "Dependencies" for details.

## Prerequisites

- Ubuntu 22.04+ VPS with SSH access
- Domain name pointing to VPS IP (for HTTPS)
- At least 1GB RAM, 10GB disk

## 1. Install Docker

```bash
# Install Docker
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER
newgrp docker

# Verify
docker --version
docker compose version
```

## 2. Clone and Configure

```bash
git clone https://github.com/shahwan42/clearmoney.git
cd clearmoney

# Create .env from example
cp .env.example .env
```

Edit `.env` with production values:

```bash
# .env
ENV=production
LOG_LEVEL=info

# IMPORTANT: Change these credentials for production
DATABASE_URL=postgres://clearmoney:CHANGE_THIS_PASSWORD@db:5432/clearmoney?sslmode=disable
POSTGRES_USER=clearmoney
POSTGRES_PASSWORD=CHANGE_THIS_PASSWORD
POSTGRES_DB=clearmoney

APP_URL=https://clearmoney.shahwan.me
RESEND_API_KEY=re_...

# Optional: Web Push (generate with `npx web-push generate-vapid-keys`)
# VAPID_PUBLIC_KEY=
# VAPID_PRIVATE_KEY=
```

## 3. Deploy

```bash
# Build and start
docker compose up -d --build

# Verify
docker compose ps
docker compose logs -f django
```

The app is now running at `https://clearmoney.shahwan.me`. First visit will prompt for email (magic link auth).

## 4. HTTPS with Caddy (Containerized)

HTTPS is handled by a Caddy container in `docker-compose.prod.yml`. Caddy automatically provisions and renews Let's Encrypt certificates.

The `Caddyfile` routes all traffic to Django:

```
clearmoney.shahwan.me {
    reverse_proxy django:8000
}
```

**If you previously installed Caddy system-level**, stop and disable it to free ports 80/443:

```bash
sudo systemctl stop caddy
sudo systemctl disable caddy
```

Certificates are persisted in the `caddy_data` Docker volume, so they survive container restarts and rebuilds.

**Ensure `APP_URL` in `.env.prod` uses `https://`** so magic link emails contain the correct URL.

## 5. Firewall

```bash
sudo ufw allow 22/tcp    # SSH
sudo ufw allow 80/tcp    # HTTP (Caddy redirect)
sudo ufw allow 443/tcp   # HTTPS
sudo ufw enable
```

Do **not** expose port 8000 publicly — it should only be accessible via Caddy.

## 6. Backups

### Database Backup

```bash
# Manual backup
docker compose exec db pg_dump -U clearmoney clearmoney > backup_$(date +%Y%m%d).sql

# Restore
docker compose exec -T db psql -U clearmoney clearmoney < backup_20260309.sql
```

### Automated Daily Backup (cron)

```bash
crontab -e
```

Add:

```
0 3 * * * cd /path/to/clearmoney && docker compose exec -T db pg_dump -U clearmoney clearmoney | gzip > /backups/clearmoney_$(date +\%Y\%m\%d).sql.gz
```

## 7. Updates

```bash
cd /path/to/clearmoney
git pull
docker compose up -d --build
```

Migrations run automatically on startup — no manual steps needed.

## 8. Monitoring

```bash
# Check status of all containers
docker compose -f docker-compose.prod.yml ps

# View logs
docker compose -f docker-compose.prod.yml logs -f django   # Django app logs
docker compose -f docker-compose.prod.yml logs -f db       # Database logs
docker compose -f docker-compose.prod.yml logs -f caddy    # Caddy/TLS logs

# Health check (from the VPS itself)
curl -s http://localhost:8000/healthz

# Verify HTTPS externally
curl -I https://clearmoney.shahwan.me
```

## 9. Troubleshooting

| Issue | Solution |
| ----- | ------- |
| App can't connect to DB | Check `DATABASE_URL` uses `db` as hostname (not `localhost`) |
| Port 80/443 already in use | Stop system-level Caddy: `sudo systemctl stop caddy && sudo systemctl disable caddy` |
| TLS cert not provisioning | Check `docker compose logs caddy` — ensure DNS A record points to VPS IP and ports 80/443 are open |
| Migrations fail | Check `docker compose -f docker-compose.prod.yml logs django` for SQL errors |
| Out of disk | Prune old Docker images: `docker system prune -a` |
| Magic links have http:// | Update `APP_URL=https://clearmoney.shahwan.me` in `.env.prod` on VPS |
