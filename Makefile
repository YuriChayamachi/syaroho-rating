# Makefile

.PHONY: build
build:
	docker compose build

.PHONY: run
run:
	docker compose build
	docker compose run syaroho-rating

.PHONY: format
format:
	black src
	isort src

.PHONY: test
test:
	mypy syaroho_rating main.py
