# Makefile

.PHONY: build
build:
	docker compose build

.PHONY: run
run:
	docker compose run syaroho-rating

.PHONY: format
format:
	black syaroho_rating
	isort syaroho_rating
