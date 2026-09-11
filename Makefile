.PHONY: up down test
up:
	docker compose up --build
down:
	docker compose down
test:
	cd apps/api && pytest -q
	cd apps/web && npm run build
