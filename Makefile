.PHONY: run build test clean up down logs

run:
	go run ./cmd/server

build:
	go build -o bin/clearmoney ./cmd/server

test:
	go test ./... -v

clean:
	rm -rf bin/

up:
	docker compose up -d --build

down:
	docker compose down

logs:
	docker compose logs -f
