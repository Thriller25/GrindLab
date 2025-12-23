# 🐳 Docker Setup for GrindLab

This document explains how to run GrindLab using Docker.

## Prerequisites

- Docker Engine 24.0+
- Docker Compose V2+

## Quick Start

### 1. Create environment file

```bash
cp .env.docker.example .env
# Edit .env and set your SECRET_KEY and passwords
```

### 2. Build and run

```bash
# Production mode
docker compose up -d --build

# Development mode (with hot reload)
docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d --build
```

### 3. Access the application

- **Frontend**: http://localhost
- **Backend API**: http://localhost:8000
- **API Docs**: http://localhost:8000/docs
- **Adminer** (dev only): http://localhost:8080

## Services

| Service | Port | Description |
|---------|------|-------------|
| frontend | 80 | React app served by Nginx |
| backend | 8000 | FastAPI backend |
| db | 5432 | PostgreSQL database |
| adminer | 8080 | Database admin UI (dev profile) |

## Commands

### View logs
```bash
docker compose logs -f
docker compose logs -f backend
```

### Run database migrations
```bash
docker compose exec backend alembic upgrade head
```

### Access database shell
```bash
docker compose exec db psql -U grindlab -d grindlab
```

### Run backend tests
```bash
docker compose exec backend pytest
```

### Stop all services
```bash
docker compose down

# Remove volumes (WARNING: deletes data)
docker compose down -v
```

### Rebuild specific service
```bash
docker compose build backend
docker compose up -d backend
```

## Development Mode

Development mode provides:
- Hot reload for backend (uvicorn --reload)
- Hot reload for frontend (Vite dev server)
- Source code mounted as volumes

```bash
docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d
```

## Production Deployment

For production:

1. Set strong passwords in `.env`
2. Set `DEBUG=false`
3. Configure proper `SECRET_KEY`
4. Use external PostgreSQL or managed database
5. Set up HTTPS (via reverse proxy like Traefik/Nginx)

```bash
# Production build
docker compose -f docker-compose.yml up -d --build
```

## Health Checks

All services have health checks configured:

- **Backend**: `GET /health` and `GET /health/ready`
- **Frontend**: `GET /health`
- **Database**: `pg_isready`

## Troubleshooting

### Database connection issues
```bash
# Check if database is healthy
docker compose ps
docker compose logs db
```

### Backend not starting
```bash
# Check backend logs
docker compose logs backend

# Restart backend
docker compose restart backend
```

### Reset everything
```bash
docker compose down -v
docker compose up -d --build
```
