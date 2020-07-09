#!/usr/bin/env python3
import logging
import signal
import sys
import time

from c2cwsgiutils import setup_process

from shared_config_manager import slave_status  # noqa: F401, pylint: disable=unused-import
from shared_config_manager import sources

setup_process.init()


def main():
    signal.signal(signal.SIGTERM, _sig_term)

    sources.init(slave=True)
    while True:
        time.sleep(3600)


def _sig_term(signum, frame):
    logging.getLogger("shared_config_slave").info("Got a SIGTERM, stopping the slave")
    sys.exit(0)


if __name__ == "__main__":
    main()
