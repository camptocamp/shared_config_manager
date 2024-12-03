DOCKER_TAG ?= latest
DOCKER_BASE = camptocamp/shared_config_manager
export DOCKER_BUILDKIT = 1

THIS_MAKEFILE_PATH := $(word $(words $(MAKEFILE_LIST)),$(MAKEFILE_LIST))
THIS_DIR := $(shell cd $(dir $(THIS_MAKEFILE_PATH));pwd)

GIT_HASH := $(shell git rev-parse HEAD)

DOCKER_TTY := $(shell [ -t 0 ] && echo -ti)

.PHONY: help
help: ## Display this help message
	@echo "Usage: make <target>"
	@echo
	@echo "Available targets:"
	@grep --extended-regexp --no-filename '^[a-zA-Z_-]+:.*## ' $(MAKEFILE_LIST) | sort | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "	%-20s%s\n", $$1, $$2}'

.venv/timestamp: app/requirements.txt requirements.txt Makefile
	python3 -m venv .venv
	.venv/bin/pip install --requirement=requirements.txt --requirement=app/requirements.txt
	touch $@

.PHONY: pull
pull:
	for image in `find -name Dockerfile | xargs grep --no-filename FROM | awk '{print $$2}' | sort -u`; do docker pull $$image; done
	for image in `find -name "docker-compose*.yaml" | xargs grep --no-filename "image:" | awk '{print $$2}' | sort -u | grep -v $(DOCKER_BASE) | grep -v rancher`; do docker pull $$image; done

.PHONY: push
push: build
	docker push $(DOCKER_BASE):$(DOCKER_TAG)

.PHONY: build
build: ## Build the application Docker image
	docker build --tag=$(DOCKER_BASE):$(DOCKER_TAG) --build-arg="GIT_HASH=$(GIT_HASH)" app

.PHONY: build-checker
build-checker: # Build the Docker image for checks and tests
	docker build --target=checker --tag=$(DOCKER_BASE)-checker:$(DOCKER_TAG) --build-arg="GIT_HASH=$(GIT_HASH)" app

.PHONY: build-acceptance
build-acceptance:
	docker build --tag=$(DOCKER_BASE)-acceptance:$(DOCKER_TAG) acceptance_tests

.PHONY: acceptance
acceptance: build-acceptance build # Run the acceptance tests
	C2C_AUTH_GITHUB_CLIENT_ID=$(shell gopass show gs/projects/github/oauth-apps/geoservices-int/client-id) \
	C2C_AUTH_GITHUB_CLIENT_SECRET=$(shell gopass show gs/projects/github/oauth-apps/geoservices-int/client-secret) \
	docker compose up --detach
	docker compose exec -T tests pytest -vv --color=yes --junitxml /reports/acceptance.xml acceptance
	docker compose down

.PHONY: run
run: build
	docker compose stop
	docker compose rm --force
	C2C_AUTH_GITHUB_CLIENT_ID=$(shell gopass show gs/projects/github/oauth-apps/geoservices-int/client-id) \
	C2C_AUTH_GITHUB_CLIENT_SECRET=$(shell gopass show gs/projects/github/oauth-apps/geoservices-int/client-secret) \
	docker compose up --detach

.PHONY: clean
clean:
	rm -rf reports .venv
	docker compose down

.PHONY: checks
checks: prospector acceptance-prospector ## Run the checks

.PHONY: acceptance-prospector
acceptance-prospector: build-acceptance ## Run Prospector on acceptance
	docker run --rm --volume=${PWD}/acceptance_tests:/acceptance_tests --volume=${PWD}/acceptance_tests:/acceptance_tests/acceptance_tests $(DOCKER_BASE)-acceptance:$(DOCKER_TAG) \
		prospector --output=pylint --die-on-tool-error --without=ruff acceptance_tests

.PHONY: prospector
prospector: build-checker ## Run Prospector
	docker run --rm --volume=${PWD}/app:/app --volume=${PWD}/app:/app/app $(DOCKER_BASE)-checker:$(DOCKER_TAG) \
		prospector --output=pylint --die-on-tool-error app

.PHONY: prospector-fast
prospector-fast: ## Run Prospector without building the Docker image
	docker run --rm --volume=${PWD}/app:/app --volume=${PWD}/app:/app/app $(DOCKER_BASE)-checker:$(DOCKER_TAG) \
		prospector --output=pylint --die-on-tool-error app

DOCKER_RUN_TESTS = docker run --rm --volume=${PWD}/results/:/results --volume=${PWD}/app:/app
DOCKER_IMAGE_PYTEST = $(DOCKER_BASE)-checker:$(DOCKER_TAG) pytest -vv --color=yes

.PHONY: tests
tests: build-checker ## Run the unit tests
	$(DOCKER_RUN_TESTS) --env=PRIVATE_SSH_KEY $(DOCKER_IMAGE_PYTEST) tests

.PHONY: tests-fast
tests-fast: ## Run the unit tests
	$(DOCKER_RUN_TESTS) --env=PRIVATE_SSH_KEY=$(shell gopass show gs/ci/github/token/gopass) $(DOCKER_IMAGE_PYTEST) tests
