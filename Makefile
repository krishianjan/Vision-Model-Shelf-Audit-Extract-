.PHONY: dev migrate seed mobile test health

dev:
	docker-compose up -d
	@echo "Waiting for Postgres..."
	@sleep 3
	cd api && PYTHONPATH=. .venv/bin/uvicorn src.main:app --host 0.0.0.0 --port 8000 --log-level warning

migrate:
	@for f in db/migrations/*.sql; do \
		echo "Running $$f..."; \
		psql "$(DATABASE_URL)" -f "$$f"; \
	done

seed:
	psql "$(DATABASE_URL)" -f db/seeds/accounts.sql
	cd db && python seeds/products.py

mobile:
	cd mobile && npx expo start

test:
	cd api && pytest tests/ -v

health:
	curl -s http://localhost:8000/health | python3 -m json.tool
