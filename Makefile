.PHONY: dev stop build engines clean

# Development
dev:
	docker compose up -d

stop:
	docker compose down

# Build Go engines
engines:
	cd engines && make build

# Full build
build: engines
	docker compose build

# Clean
clean:
	docker compose down -v
	cd engines && make clean
