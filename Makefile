.PHONY: run build test test-integration clean up down logs migrate-create

run:
	go run ./cmd/server

build:
	go build -o bin/clearmoney ./cmd/server

test:
	go test ./... -v

test-integration:
	TEST_DATABASE_URL="postgres://clearmoney:clearmoney@localhost:5432/clearmoney?sslmode=disable" go test ./... -v -count=1

clean:
	rm -rf bin/

up:
	docker compose up -d --build

down:
	docker compose down

logs:
	docker compose logs -f

migrate-create:
	@if [ -z "$(name)" ]; then echo "Usage: make migrate-create name=<migration_name>"; exit 1; fi
	@next=$$(printf "%06d" $$(ls internal/database/migrations/*.up.sql 2>/dev/null | wc -l)); \
	touch "internal/database/migrations/$${next}_$(name).up.sql"; \
	touch "internal/database/migrations/$${next}_$(name).down.sql"; \
	echo "Created: $${next}_$(name).{up,down}.sql"
