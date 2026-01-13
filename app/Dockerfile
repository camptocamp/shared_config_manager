FROM ubuntu:24.04 AS base-all
LABEL org.opencontainers.image.authors="Camptocamp <info@camptocamp.com>"
SHELL ["/bin/bash", "-o", "pipefail", "-cux"]

RUN --mount=type=cache,target=/var/lib/apt/lists \
    --mount=type=cache,target=/var/cache,sharing=locked \
    apt-get update \
    && DEBIAN_FRONTEND=noninteractive apt-get upgrade --assume-yes \
    && DEBIAN_FRONTEND=noninteractive TZ=Etc/UTC apt-get install --assume-yes tzdata \
    && DEBIAN_FRONTEND=noninteractive apt-get install --assume-yes --no-install-recommends python3-pip python3-venv \
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
RUN poetry export --output=requirements.txt \
    && poetry export --with=dev --output=requirements-dev.txt

# Base, the biggest thing is to install the Python packages
FROM base-all AS base

# Fail on error on pipe, see: https://github.com/hadolint/hadolint/wiki/DL4006.
# Treat unset variables as an error when substituting.
# Print commands and their arguments as they are executed.
SHELL ["/bin/bash", "-o", "pipefail", "-cux"]

# Doing things in two steps to avoid needing to re-install everything when we do a rebuild
# after changing code

# Copy only the stuff needed to install the dependencies and run the script
WORKDIR /app

EXPOSE 8080

RUN --mount=type=cache,target=/var/lib/apt/lists \
    --mount=type=cache,target=/var/cache,sharing=locked \
    apt-get update \
    && apt-get install --assume-yes --no-install-recommends openssh-client git rsync curl gettext-base \
    && echo "    VerifyHostKeyDNS yes" >> /etc/ssh/ssh_config \
    && echo "    StrictHostKeyChecking no" >> /etc/ssh/ssh_config # TODO: find better

RUN --mount=type=cache,target=/var/lib/apt/lists \
    --mount=type=cache,target=/root/.cache \
    --mount=type=cache,target=/var/cache,sharing=locked \
    --mount=type=bind,from=poetry,source=/tmp,target=/poetry \
    apt-get update \
    && apt-get install --assume-yes --no-install-recommends python3-dev libpq-dev gcc \
    && python3 -m pip install --disable-pip-version-check --no-deps --requirement=/poetry/requirements.txt \
    && python3 -m compileall -q /usr/local/lib/python3.* \
    && apt-get autoremove --assume-yes python3-dev libpq-dev gcc

# Copy the rest of the files (watch for the .dockerignore)
COPY pyproject.toml poetry.lock ./
COPY shared_config_manager/__init__.py ./shared_config_manager/

ARG GIT_HASH

RUN --mount=type=cache,target=/root/.cache \
    python3 -m pip install --disable-pip-version-check --no-deps --editable=. \
    && python3 -m pip freeze > /requirements.txt \
    && c2cwsgiutils-genversion $GIT_HASH \
    && mkdir -p /master_config /config /var/www \
    && adduser www-data root \
    && chown www-data:root /master_config /config /var/www \
    && chmod og+rwx /master_config /config /var/www \
    && chmod g+w /etc/passwd \
    && python3 -m compileall -q . \
    && rm -rf /tmp/* /master_config/* /config/*

COPY logging.yaml ./
COPY scripts/ /usr/bin/
COPY shared_config_manager/ ./shared_config_manager/

RUN mkdir -p /prometheus-metrics \
    && chmod a+rwx /prometheus-metrics
ENV PROMETHEUS_MULTIPROC_DIR=/prometheus-metrics

CMD ["uvicorn", "shared_config_manager.main:app", "--host=0.0.0.0", "--port=8080", "--log-config=/app/logging.yaml"]

FROM base AS checker

RUN --mount=type=cache,target=/root/.cache \
    --mount=type=bind,from=poetry,source=/tmp,target=/poetry \
    python3 -m pip install --disable-pip-version-check --no-deps --requirement=/poetry/requirements-dev.txt

FROM base AS runner
