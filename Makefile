# Simple Makefile for Xiquet Casteller Application

.PHONY: help dev down logs clean migrate

# Default target
help:
	@echo "Xiquet Casteller Application - Simple Commands:"
	@echo ""
	@echo "  dev     - Start both backend and frontend in development mode"
	@echo "  down    - Stop all services"
	@echo "  logs    - Show logs from all services"
	@echo "  migrate - Run database migrations"
	@echo "  clean   - Clean up Docker containers and images"
	@echo ""

# Start development environment
dev:
	@echo "Starting development environment..."
	docker-compose up --build

# Stop all services
down:
	@echo "Stopping all services..."
	docker-compose down

# Show logs
logs:
	docker-compose logs -f

# Run database migrations
migrate:
	@echo "Running database migrations..."
	@docker-compose exec backend python migrations/run_migration.py || \
	 (echo "⚠️  Backend container not running. Starting it first..." && \
	  docker-compose up -d backend && \
	  sleep 2 && \
	  docker-compose exec backend python migrations/run_migration.py)

# Clean up
clean:
	@echo "Cleaning up Docker resources..."
	docker-compose down -v
	docker system prune -f
