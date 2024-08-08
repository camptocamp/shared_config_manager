DOCKER_TAG ?= latest
DOCKER_BASE = camptocamp/shared_config_manager

THIS_MAKEFILE_PATH := $(word $(words $(MAKEFILE_LIST)),$(MAKEFILE_LIST))
THIS_DIR := $(shell cd $(dir $(THIS_MAKEFILE_PATH));pwd)

GIT_HASH := $(shell git rev-parse HEAD)

DOCKER_TTY := $(shell [ -t 0 ] && echo -ti)

.PHONY: all
all: build acceptance

.PHONY: build
build: build_app

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

.PHONY: build_app
build_app:
	docker build --tag=$(DOCKER_BASE):$(DOCKER_TAG) --build-arg="GIT_HASH=$(GIT_HASH)" \
		--build-arg="PRIVATE_SSH_KEY=$(shell echo ${PRIVATE_SSH_KEY})" app

.PHONY: build_acceptance
build_acceptance:
	docker build --tag=$(DOCKER_BASE)_acceptance:$(DOCKER_TAG) acceptance_tests

.PHONY: acceptance
acceptance: build_acceptance build
	docker compose up -d
	docker compose exec -T tests py.test -vv --color=yes --junitxml /reports/acceptance.xml acceptance
	docker compose down

.PHONY: run
run: build
	docker compose stop && \
	docker compose rm -f && \
	docker compose up

.PHONY: clean
clean:
	rm -rf reports .venv
	docker compose down
