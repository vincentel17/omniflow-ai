SHELL := /bin/sh

setup:
	pnpm run setup

check:
	pnpm run check

test:
	pnpm run test

test-unit:
	pnpm run test-unit

test-integration:
	pnpm run test-integration

test-e2e:
	pnpm run test-e2e

build:
	pnpm run build

migrate:
	pnpm run migrate

seed:
	pnpm run seed

release-check:
	pnpm run release-check

smoke:
	powershell -ExecutionPolicy Bypass -File ./scripts/smoke.ps1

create-vertical-pack:
	python scripts/create-vertical-pack.py $(slug)

validate-pack:
	python scripts/validate-pack.py $(slug)
