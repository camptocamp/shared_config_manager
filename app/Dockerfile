FROM camptocamp/c2cwsgiutils:2
LABEL maintainer "info@camptocamp.org"

# Doing things in two steps to avoid needing to re-install everything when we do a rebuild
# after changing code

# Step #1 copy only the stuff needed to install the dependencies and run the script
WORKDIR /app

EXPOSE 8080

# Step #2 copy the rest of the files (watch for the .dockerignore)
COPY . /app

ARG GIT_HASH

RUN pip3 install --no-cache-dir -e . && \
    c2cwsgiutils_genversion.py $GIT_HASH && \
    flake8 shared_config_manager tests && \
    pytest -vv --cov=shared_config_manager --color=yes tests && \
    python3 -m compileall -q . && \
    mkdir -p /master_config /config && \
    adduser www-data root && \
    chown www-data:root /master_config /config && \
    chmod og+rwx /master_config /config && \
    rm -rf /tmp/* /master_config/* /config/*

ENV GUNICORN_PARAMS="-b :8080 --workers 1" \
    LOG_LEVEL=DEBUG

# www-data
USER 33
