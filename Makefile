# Simple Makefile for Xiquet Casteller Application

.PHONY: help dev down logs clean

# Default target
help:
	@echo "Xiquet Casteller Application - Simple Commands:"
	@echo ""
	@echo "  dev     - Start both backend and frontend in development mode"
	@echo "  down    - Stop all services"
	@echo "  logs    - Show logs from all services"
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

# Clean up
clean:
	@echo "Cleaning up Docker resources..."
	docker-compose down -v
	docker system prune -f
