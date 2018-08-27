#!/usr/bin/env python3
from c2cwsgiutils import sentry, broadcast, stats, redis_stats, coverage_setup
import logging
from logging.config import fileConfig
import os
import time

from shared_config_manager import sources


def main():
    _setup_logging()
    _init_c2cwsgiutils()
    sources.init()
    while True:
        time.sleep(3600)


def _setup_logging():
    logging.captureWarnings(True)
    configfile_ = os.environ.get('C2CWSGIUTILS_CONFIG', "/app/production.ini")
    fileConfig(configfile_, defaults=dict(os.environ))


def _init_c2cwsgiutils():
    coverage_setup.init()
    sentry.init()
    broadcast.init()
    stats.init_backends({})
    redis_stats.init(None)


if __name__ == "__main__":
    main()
