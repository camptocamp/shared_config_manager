DOCKER_TAG ?= latest
DOCKER_BASE = camptocamp/shared_config_manager

#Get the docker version (must use the same version for acceptance tests)
DOCKER_VERSION_ACTUAL := $(shell docker version --format '{{.Server.Version}}')
ifeq ($(DOCKER_VERSION_ACTUAL),)
DOCKER_VERSION := 1.12.0
else
DOCKER_VERSION := $(DOCKER_VERSION_ACTUAL)
endif

#Get the docker-compose version (must use the same version for acceptance tests)
DOCKER_COMPOSE_VERSION_ACTUAL := $(shell docker-compose version --short)

ifeq ($(DOCKER_COMPOSE_VERSION_ACTUAL),)
DOCKER_COMPOSE_VERSION := 1.10.0
else
DOCKER_COMPOSE_VERSION := $(DOCKER_COMPOSE_VERSION_ACTUAL)
endif

THIS_MAKEFILE_PATH := $(word $(words $(MAKEFILE_LIST)),$(MAKEFILE_LIST))
THIS_DIR := $(shell cd $(dir $(THIS_MAKEFILE_PATH));pwd)

GIT_HASH := $(shell git rev-parse HEAD)

DOCKER_TTY := $(shell [ -t 0 ] && echo -ti)

.PHONY: all
all: build acceptance

.PHONY: build
build: build_app

.venv/timestamp: app/requirements.txt Makefile
	/usr/bin/virtualenv --python=/usr/bin/python3 .venv
	.venv/bin/pip install -U "c2cwsgiutils>=2,<3" yamllint==1.10.0 -r app/requirements.txt
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
	@echo "Docker version: $(DOCKER_VERSION)"
	@echo "Docker-compose version: $(DOCKER_COMPOSE_VERSION)"
	docker build --build-arg DOCKER_VERSION="$(DOCKER_VERSION)" --build-arg DOCKER_COMPOSE_VERSION="$(DOCKER_COMPOSE_VERSION)" -t $(DOCKER_BASE)_acceptance:$(DOCKER_TAG) acceptance_tests

.PHONY: acceptance
acceptance: build_acceptance build
	rm -rf reports/coverage/api reports/acceptance*.xml
	mkdir -p reports/coverage/api
	#get the UT reports
	docker run --rm $(DOCKER_BASE):$(DOCKER_TAG) cat /app/.coverage > reports/coverage/api/coverage.ut.1
	#run the tests
	docker run $(DOCKER_TTY) -e DOCKER_TAG=$(DOCKER_TAG) -v /var/run/docker.sock:/var/run/docker.sock -v /tmp/test_repos:/tmp/test_repos -v /tmp/slaves/:/tmp/slaves --name scm_acceptance_$(DOCKER_TAG)_$$PPID $(DOCKER_BASE)_acceptance:$(DOCKER_TAG) \
	bash -c "py.test -vv --color=yes --junitxml /reports/acceptance.xml $(PYTEST_OPTS) acceptance; status=\$$?; junit2html /reports/acceptance.xml /reports/acceptance.html; exit \$$status\$$?"; \
	status=$$status$$?; \
	#copy the reports locally \
	docker cp scm_acceptance_$(DOCKER_TAG)_$$PPID:/reports ./; \
	status=$$status$$?; \
	docker rm scm_acceptance_$(DOCKER_TAG)_$$PPID; \
	status=$$status$$?; \
	#generate the HTML report for code coverage \
	docker run -v $(THIS_DIR)/reports/coverage/api:/reports/coverage/api:ro --name scm_acceptance_reports_$(DOCKER_TAG)_$$PPID $(DOCKER_BASE):$(DOCKER_TAG) c2cwsgiutils_coverage_report.py; \
	status=$$status$$?; \
	#copy the HTML locally \
	docker cp scm_acceptance_reports_$(DOCKER_TAG)_$$PPID:/tmp/coverage/api reports/coverage; \
	status=$$status$$?; \
	docker rm scm_acceptance_reports_$(DOCKER_TAG)_$$PPID; \
	exit $$status$$?

.PHONY: run
run: build test_repos
	docker-compose -p scm stop && \
	docker-compose -p scm rm -f && \
	docker-compose -p scm up

.PHONY: clean
clean:
	rm -rf reports .venv

test_repos: acceptance_tests/create_test_repos
	./acceptance_tests/create_test_repos
