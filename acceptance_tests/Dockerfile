FROM camptocamp/c2cwsgiutils:2

WORKDIR /acceptance_tests

ARG DOCKER_VERSION=1.12.0
ARG DOCKER_COMPOSE_VERSION=1.10.0
RUN /opt/c2cwsgiutils/install_docker.sh

COPY . ./

RUN flake8 acceptance

ENV DOCKER_RUN 1
CMD py.test -vv --color=yes --junitxml /reports/acceptance.xml acceptance
