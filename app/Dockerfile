FROM camptocamp/c2cwsgiutils:2
LABEL maintainer "info@camptocamp.org"

# Doing things in two steps to avoid needing to re-install everything when we do a rebuild
# after changing code

# Step #1 copy only the stuff needed to install the dependencies and run the script
WORKDIR /app

EXPOSE 8080

RUN curl https://downloads.rclone.org/v1.43.1/rclone-v1.43.1-linux-amd64.deb > /tmp/rclone.deb && \
    dpkg -i /tmp/rclone.deb && \
    rm /tmp/rclone.deb && \
    apt update && \
    apt install -y --no-install-recommends ssh rsync gettext-base && \
    apt clean && \
    rm -r /var/lib/apt/lists/* && \
    echo "    VerifyHostKeyDNS yes" >> /etc/ssh/ssh_config && \
    echo "    StrictHostKeyChecking no" >> /etc/ssh/ssh_config  # TODO: find better

# Step #2 copy the rest of the files (watch for the .dockerignore)
COPY . /app

ARG GIT_HASH

RUN pip3 install --no-cache-dir -e . && \
    c2cwsgiutils_genversion.py $GIT_HASH && \
    flake8 shared_config_manager tests && \
    mkdir -p /master_config /config /var/www && \
    adduser www-data root && \
    chown www-data:root /master_config /config /var/www && \
    chmod og+rwx /master_config /config /var/www && \
    chmod g+w /etc/passwd && \
    pytest -vv --cov=shared_config_manager --color=yes tests && \
    python3 -m compileall -q . && \
    rm -rf /tmp/* /master_config/* /config/*

ENV GUNICORN_PARAMS="-b :8080 --workers 1" \
    LOG_LEVEL=DEBUG \
    C2C_BROADCAST_PREFIX=broadcast_scm_

# www-data
USER 33
