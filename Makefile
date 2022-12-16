# Makefile

.PHONY: build
build:
	docker compose build

.PHONY: run
run:
	docker compose run syaroho-rating

.PHONY: format
format:
	black syaroho_rating main.py
	isort syaroho_rating main.py

.PHONY: test
test:
	mypy syaroho_rating main.py
