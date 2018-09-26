#!/usr/bin/env python3
import os
import signal
import time


def main():
    signal.signal(signal.SIGTERM, _sig_term)
    _setup_logging()
    _init_c2cwsgiutils()
    from shared_config_manager import sources, slave_status
    sources.init()
    while True:
        time.sleep(3600)


def _setup_logging():
    import logging
    from logging.config import fileConfig
    logging.captureWarnings(True)
    configfile_ = os.environ.get('C2CWSGIUTILS_CONFIG', "/app/production.ini")
    fileConfig(configfile_, defaults=dict(os.environ))


def _init_c2cwsgiutils():
    from c2cwsgiutils import sentry, broadcast, stats, redis_stats, coverage_setup
    coverage_setup.init()
    sentry.init()
    broadcast.init()
    stats.init_backends({})
    redis_stats.init(None)


def _sig_term(signum, frame):
    import logging
    logging.getLogger("shared_config_slave").info("Got a SIGTERM, stopping the slave")
    exit(0)

if __name__ == "__main__":
    main()
