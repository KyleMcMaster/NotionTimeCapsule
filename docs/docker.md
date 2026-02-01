# Docker Deployment

> **Added:** 2026-01-31

NotionTimeCapsule can be run as a Docker container for easy deployment and scheduling.

## Quick Start

```bash
# Build the image
docker build -t notion-time-capsule .

# Run the scheduler
docker run -d \
  --name notion-scheduler \
  -e NOTION_TOKEN=your_token \
  -v $(pwd)/config.toml:/app/config.toml:ro \
  -v $(pwd)/backups:/app/backups \
  notion-time-capsule
```

## Image Details

- **Base**: Python 3.12-slim
- **Size**: ~220MB (47MB compressed)
- **User**: Runs as non-root user (UID 1000)
- **Health check**: Uses `notion-time-capsule status` command

## Configuration

### Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `NOTION_TOKEN` | Yes | Notion integration token |
| `DISCORD_WEBHOOK_URL` | No | Discord webhook for notifications |

### Volume Mounts

| Container Path | Purpose | Mode |
|----------------|---------|------|
| `/app/config.toml` | Configuration file | Read-only |
| `/app/backups` | Backup output directory | Read-write |
| `/app/templates` | Template files for daily content | Read-only |

## Usage Examples

### Run Scheduler (Default)

The default command runs the scheduler daemon:

```bash
docker run -d \
  --name notion-scheduler \
  --restart unless-stopped \
  -e NOTION_TOKEN=your_token \
  -v $(pwd)/config.toml:/app/config.toml:ro \
  -v $(pwd)/backups:/app/backups \
  -v $(pwd)/templates:/app/templates:ro \
  notion-time-capsule
```

### Run One-Off Backup

```bash
docker run --rm \
  -e NOTION_TOKEN=your_token \
  -v $(pwd)/backups:/app/backups \
  notion-time-capsule notion-time-capsule backup
```

### Run Daily Content Generation

```bash
docker run --rm \
  -e NOTION_TOKEN=your_token \
  -v $(pwd)/config.toml:/app/config.toml:ro \
  -v $(pwd)/templates:/app/templates:ro \
  notion-time-capsule notion-time-capsule daily
```

### Check Status

```bash
docker run --rm \
  -e NOTION_TOKEN=your_token \
  -v $(pwd)/config.toml:/app/config.toml:ro \
  -v $(pwd)/backups:/app/backups \
  notion-time-capsule notion-time-capsule status
```

### Test Discord Webhook

```bash
docker run --rm \
  -e NOTION_TOKEN=your_token \
  -e DISCORD_WEBHOOK_URL=your_webhook_url \
  -v $(pwd)/config.toml:/app/config.toml:ro \
  notion-time-capsule notion-time-capsule test-discord
```

## Docker Compose

For easier management, use Docker Compose:

```yaml
# docker-compose.yml
services:
  notion-time-capsule:
    build: .
    container_name: notion-time-capsule
    restart: unless-stopped
    environment:
      - NOTION_TOKEN=${NOTION_TOKEN}
      - DISCORD_WEBHOOK_URL=${DISCORD_WEBHOOK_URL:-}
    volumes:
      - ./config.toml:/app/config.toml:ro
      - ./backups:/app/backups
      - ./templates:/app/templates:ro
```

### Docker Compose Commands

```bash
# Start scheduler in background
docker-compose up -d

# View logs
docker-compose logs -f

# Run one-off backup
docker-compose run --rm notion-time-capsule notion-time-capsule backup

# Run daily content
docker-compose run --rm notion-time-capsule notion-time-capsule daily

# Stop
docker-compose down
```

### Environment File

Create a `.env` file for secrets:

```bash
# .env
NOTION_TOKEN=secret_xxx
DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/...
```

Docker Compose automatically loads `.env` files.

## Graceful Shutdown

The container handles SIGTERM gracefully:

```bash
# Stop with graceful shutdown
docker stop notion-scheduler

# Logs will show:
# "Received SIGTERM, shutting down gracefully..."
# "Scheduler stopped"
```

## Health Checks

The container includes a health check that runs every 60 seconds:

```bash
# Check container health
docker inspect --format='{{.State.Health.Status}}' notion-scheduler

# View health check logs
docker inspect --format='{{json .State.Health}}' notion-scheduler | jq
```

## Building the Image

### Standard Build

```bash
docker build -t notion-time-capsule .
```

### With Custom Tag

```bash
docker build -t notion-time-capsule:v1.0.0 .
```

### Multi-Platform Build

```bash
docker buildx build --platform linux/amd64,linux/arm64 -t notion-time-capsule .
```

## Troubleshooting

### Container Exits Immediately

Check if NOTION_TOKEN is set:

```bash
docker run --rm -e NOTION_TOKEN=test notion-time-capsule notion-time-capsule status
```

### Permission Denied on Volumes

Ensure the host directories are writable by UID 1000:

```bash
sudo chown -R 1000:1000 ./backups
```

### View Container Logs

```bash
docker logs -f notion-scheduler
```

### Debug Mode

Run with verbose logging:

```bash
docker run --rm \
  -e NOTION_TOKEN=your_token \
  notion-time-capsule notion-time-capsule -vv backup
```
