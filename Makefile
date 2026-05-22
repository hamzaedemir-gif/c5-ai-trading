.PHONY: help install dev test docker-build docker-up docker-down clean

help:
	@echo "Targets:"
	@echo "  make install      - one-time deps install (python venv + npm)"
	@echo "  make dev          - hot-reload dev mode (backend + frontend) -> http://localhost:5173"
	@echo "  make test         - run the pytest suite"
	@echo "  make docker-up    - production-ish: docker compose up --build"
	@echo "  make docker-down  - docker compose down"
	@echo "  make clean        - remove venv, node_modules, demo DBs"

install:
	test -d .venv || python3 -m venv .venv
	. .venv/bin/activate && pip install -q -r requirements.txt
	test -d node_modules || npm install --no-audit --no-fund
	test -d frontend/node_modules || (cd frontend && npm install --no-audit --no-fund)

dev:
	./dev.sh

test:
	. .venv/bin/activate && pytest tests/ -q

docker-build:
	docker compose build

docker-up:
	docker compose up --build

docker-down:
	docker compose down

clean:
	rm -rf .venv node_modules frontend/node_modules c5_demo.sqlite c5_data.sqlite backend.log frontend.log
