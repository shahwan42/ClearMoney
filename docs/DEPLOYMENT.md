# Deployment Guide — Ubuntu VPS with Docker Compose

## Prerequisites

- Ubuntu 22.04+ VPS with SSH access
- Domain name (optional, for HTTPS)
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
PORT=8080
ENV=production
LOG_LEVEL=info

# IMPORTANT: Change these credentials for production
DATABASE_URL=postgres://clearmoney:CHANGE_THIS_PASSWORD@db:5432/clearmoney?sslmode=disable
POSTGRES_USER=clearmoney
POSTGRES_PASSWORD=CHANGE_THIS_PASSWORD
POSTGRES_DB=clearmoney

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
docker compose logs -f app
```

The app is now running on port 8080. First visit will prompt PIN setup.

## 4. HTTPS with Caddy (Recommended)

Install Caddy as a reverse proxy for automatic HTTPS:

```bash
sudo apt install -y debian-keyring debian-archive-keyring apt-transport-https
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' | sudo gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' | sudo tee /etc/apt/sources.list.d/caddy-stable.list
sudo apt update
sudo apt install caddy
```

Create `/etc/caddy/Caddyfile`:

```
money.yourdomain.com {
    reverse_proxy localhost:8080
}
```

```bash
sudo systemctl restart caddy
```

Caddy automatically provisions and renews Let's Encrypt certificates.

## 5. Firewall

```bash
sudo ufw allow 22/tcp    # SSH
sudo ufw allow 80/tcp    # HTTP (Caddy redirect)
sudo ufw allow 443/tcp   # HTTPS
sudo ufw enable
```

Do **not** expose port 8080 publicly if using Caddy — it should only be accessible via the reverse proxy.

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
# Check status
docker compose ps

# View logs
docker compose logs -f app
docker compose logs -f db

# Health check
curl -s http://localhost:8080/healthz
```

## 9. Troubleshooting

| Issue | Solution |
|-------|---------|
| App can't connect to DB | Check `DATABASE_URL` uses `db` as hostname (not `localhost`) |
| Port 8080 already in use | Change `PORT` in `.env` and update `docker-compose.yml` port mapping |
| Migrations fail | Check `docker compose logs app` for SQL errors |
| Out of disk | Prune old Docker images: `docker system prune -a` |
