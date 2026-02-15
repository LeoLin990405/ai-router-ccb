.PHONY: help build up down logs clean dev prod restart health

# Default target
help:
	@echo "HiveMind Docker Commands"
	@echo "------------------------"
	@echo "make build      - Build all Docker images"
	@echo "make up         - Start all services (production)"
	@echo "make down       - Stop all services"
	@echo "make logs       - View logs from all services"
	@echo "make clean      - Remove all containers and volumes"
	@echo "make dev        - Start in development mode"
	@echo "make prod       - Start in production mode"
	@echo "make restart    - Restart all services"
	@echo "make health     - Check health of all services"

# Build Docker images
build:
	docker-compose build

# Start services (production)
up:
	docker-compose --env-file .env.docker up -d

# Stop services
down:
	docker-compose down

# View logs
logs:
	docker-compose logs -f

# Clean up everything
clean:
	docker-compose down -v
	docker system prune -f

# Development mode
dev:
	docker-compose -f docker-compose.dev.yml up

# Production mode
prod:
	docker-compose --env-file .env.docker up -d

# Restart services
restart:
	docker-compose restart

# Health check
health:
	@echo "Checking service health..."
	@docker ps --filter "name=hivemind" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
