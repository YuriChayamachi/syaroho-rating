# Makefile

.PHONY: build
build:
	docker compose build

.PHONY: run
run:
	docker compose build
	docker compose run syaroho-rating run

.PHONY: backfill-silent
backfill-silent:
	docker compose build
	docker compose run syaroho-rating backfill $(DATE) $(DATE) --fetch-tweet

.PHONY: backfill
backfill:
	docker compose build
	docker compose run syaroho-rating backfill $(DATE) $(DATE) --post --retweet --fetch-tweet

.PHONY: format
format:
	black src
	isort src

.PHONY: test
test:
	black --check src
	isort --check --diff src
	mypy src
