.PHONY: up down test lint

up:
	docker compose up --build

down:
	docker compose down

test:
	docker compose run --rm backend pytest

lint:
	docker compose run --rm backend ruff check .
