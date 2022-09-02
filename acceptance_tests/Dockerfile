FROM ubuntu:22.04 AS base-all
LABEL maintainer "info@camptocamp.org"

RUN --mount=type=cache,target=/var/lib/apt/lists \
    --mount=type=cache,target=/var/cache,sharing=locked \
    apt-get update \
    && apt-get upgrade --assume-yes \
    && apt-get install --assume-yes --no-install-recommends python3-pip

# Used to convert the locked packages by poetry to pip requirements format
# We don't directly use `poetry install` because it force to use a virtual environment.
FROM base-all as poetry

# Install Poetry
WORKDIR /tmp
COPY requirements.txt ./
RUN --mount=type=cache,target=/root/.cache \
    python3 -m pip install --disable-pip-version-check --requirement=requirements.txt

# Do the conversion
COPY poetry.lock pyproject.toml ./
RUN poetry export --output=requirements.txt

# Base, the biggest thing is to install the Python packages
FROM base-all as base

WORKDIR /acceptance_tests

RUN --mount=type=cache,target=/var/lib/apt/lists \
    --mount=type=cache,target=/var/cache,sharing=locked \
    apt-get update \
    && apt-get install --assume-yes --no-install-recommends git curl gnupg \
        libglib2.0-0 libnss3 libatk1.0-0 libatk-bridge2.0-0 libcups2 libdrm2 libxkbcommon0 libxcomposite1 \
        libxdamage1 libxfixes3 libxrandr2 libgbm1 libpango-1.0-0 libcairo2 libasound2

RUN --mount=type=cache,target=/var/lib/apt/lists \
    --mount=type=cache,target=/var/cache,sharing=locked \
    . /etc/os-release \
    && echo "deb https://deb.nodesource.com/node_18.x ${VERSION_CODENAME} main" > /etc/apt/sources.list.d/nodesource.list \
    && curl --silent https://deb.nodesource.com/gpgkey/nodesource.gpg.key | apt-key add - \
    && apt-get update \
    && apt-get install --assume-yes --no-install-recommends 'nodejs=18.*'

COPY package.json package-lock.json ./
RUN npm install

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
