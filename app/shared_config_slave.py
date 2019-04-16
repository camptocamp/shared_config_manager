#!/usr/bin/env python3
from c2cwsgiutils import setup_process  # noqa  # pylint: disable=unused-import
import signal
import time


def main():
    signal.signal(signal.SIGTERM, _sig_term)
    from shared_config_manager import sources, slave_status
    sources.init()
    while True:
        time.sleep(3600)


def _sig_term(signum, frame):
    import logging
    logging.getLogger("shared_config_slave").info("Got a SIGTERM, stopping the slave")
    exit(0)


if __name__ == "__main__":
    main()
