FROM ubuntu:24.04 AS base-all
LABEL maintainer "info@camptocamp.org"

RUN --mount=type=cache,target=/var/lib/apt/lists \
    --mount=type=cache,target=/var/cache,sharing=locked \
    apt-get update \
    && apt-get upgrade --assume-yes \
    && apt-get install --assume-yes --no-install-recommends python3-pip python3-venv \
    && python3 -m venv /venv

ENV PATH=/venv/bin:$PATH

# Used to convert the locked packages by poetry to pip requirements format
# We don't directly use `poetry install` because it force to use a virtual environment.
FROM base-all AS poetry

# Install Poetry
WORKDIR /tmp
COPY requirements.txt ./
RUN --mount=type=cache,target=/root/.cache \
    python3 -m pip install --disable-pip-version-check --requirement=requirements.txt

# Do the conversion
COPY poetry.lock pyproject.toml ./
RUN poetry export --output=requirements.txt

# Base, the biggest thing is to install the Python packages
FROM base-all AS base

WORKDIR /acceptance_tests

RUN --mount=type=cache,target=/var/lib/apt/lists \
    --mount=type=cache,target=/var/cache,sharing=locked \
    apt-get update \
    && apt-get install --assume-yes --no-install-recommends software-properties-common \
    && add-apt-repository ppa:savoury1/pipewire \
    && add-apt-repository ppa:savoury1/chromium \
    && apt-get update \
    && apt-get install --assume-yes --no-install-recommends chromium-browser npm git

COPY package.json package-lock.json ./
RUN npm install --ignore-scripts
ENV PUPPETEER_EXECUTABLE_PATH=/usr/bin/chromium-browser

RUN --mount=type=cache,target=/var/lib/apt/lists \
    --mount=type=cache,target=/var/cache,sharing=locked \
    --mount=type=cache,target=/root/.cache \
    --mount=type=bind,from=poetry,source=/tmp,target=/poetry \
    apt-get update \
    && apt-get install --assume-yes --no-install-recommends python3-dev libpq-dev gcc \
    && python3 -m pip install --disable-pip-version-check --no-deps --requirement=/poetry/requirements.txt \
    && apt-get autoremove --assume-yes python3-dev libpq-dev gcc

COPY . ./

RUN mv ./master_config/ /etc/shared_config_manager/ \
    && ./create-test-repos

VOLUME [ "/repos", "/config", "/etc/shared_config_manager" ]
