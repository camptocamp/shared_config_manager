FROM camptocamp/c2cwsgiutils:release_4 AS base
LABEL maintainer "info@camptocamp.org"

# Doing things in two steps to avoid needing to re-install everything when we do a rebuild
# after changing code

# Copy only the stuff needed to install the dependencies and run the script
WORKDIR /app

EXPOSE 8080

RUN curl https://downloads.rclone.org/v1.52.2/rclone-v1.52.2-linux-amd64.deb > /tmp/rclone.deb && \
    dpkg -i /tmp/rclone.deb && \
    rm /tmp/rclone.deb && \
    apt-get update && \
    apt-get install --assume-yes --no-install-recommends git ssh rsync gettext-base && \
    apt-get clean && \
    rm -r /var/lib/apt/lists/* && \
    echo "    VerifyHostKeyDNS yes" >> /etc/ssh/ssh_config && \
    echo "    StrictHostKeyChecking no" >> /etc/ssh/ssh_config  # TODO: find better

COPY requirements.txt ./
RUN python3 -m pip install --disable-pip-version-check --no-cache-dir --requirement=requirements.txt && \
    rm --recursive --force /tmp/*

COPY Pipfile Pipfile.lock ./
RUN pipenv sync --system --clear && \
    rm --recursive --force /usr/local/lib/python3.*/dist-packages/tests/ /tmp/* /root/.cache/* && \
    python3 -m compileall -q /usr/local/lib/python3.* \
    -x /usr/local/lib/python3.*/dist-packages/pipenv/

# Copy the rest of the files (watch for the .dockerignore)
COPY setup.py production.ini ./
COPY scripts/ ./scripts/
COPY shared_config_manager/ ./shared_config_manager/

ARG GIT_HASH

RUN python3 -m pip install --no-cache-dir --editable=. && \
    c2cwsgiutils-genversion $GIT_HASH && \
    mkdir -p /master_config /config /var/www && \
    adduser www-data root && \
    chown www-data:root /master_config /config /var/www && \
    chmod og+rwx /master_config /config /var/www && \
    chmod g+w /etc/passwd && \
    python3 -m compileall -q . && \
    rm -rf /tmp/* /master_config/* /config/*

ENV GUNICORN_PARAMS="--bind=:8080 --workers=1 --worker-class=gthread --threads=10" \
    OTHER_LOG_LEVEL=WARN \
    GUNICORN_LOG_LEVEL=WARN \
    C2CWSGIUTILS_LOG_LEVEL=WARN \
    LOG_LEVEL=INFO \
    LOG_TYPE=json \
    C2C_BROADCAST_PREFIX=broadcast_scm_


FROM base AS tests

ARG PRIVATE_SSH_KEY
ENV PRIVATE_SSH_KEY=${PRIVATE_SSH_KEY}

RUN pipenv sync --system --clear --dev
COPY .prospector.yaml ./
COPY setup.cfg ./
COPY tests/ ./tests/
RUN prospector -X --output=pylint
RUN pytest -vv --cov=shared_config_manager --color=yes tests


FROM base AS runner
