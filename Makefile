.PHONY: up down build logs worker-logs test lint format migrate revision bash clean

up:
	docker compose up -d

down:
	docker compose down

build:
	docker compose build

logs:
	docker compose logs -f backend

worker-logs:
	docker compose logs -f worker

test:
	docker compose exec backend pytest -v

lint:
	docker compose exec backend ruff check .

format:
	docker compose exec backend ruff format .

migrate:
	docker compose exec backend alembic upgrade head

revision:
	docker compose exec backend alembic revision --autogenerate -m "$(m)"

bash:
	docker compose exec backend /bin/bash

clean:
	docker compose down -v
