#!/usr/bin/env python3
import argparse
import logging
import os
import signal
import sys
import time

import c2cwsgiutils.setup_process

from shared_config_manager import slave_status  # noqa: F401, pylint: disable=unused-import
from shared_config_manager import sources


def main():
    parser = argparse.ArgumentParser(description="Run the shared config slave")
    c2cwsgiutils.setup_process.fill_arguments(parser)
    args = parser.parse_args()

    os.environ["IS_SLAVE"] = "true"

    signal.signal(signal.SIGTERM, _sig_term)

    c2cwsgiutils.setup_process.bootstrap_application_from_options(args)

    sources.init(slave=True)
    while True:
        time.sleep(3600)


def _sig_term(signum, frame):
    logging.getLogger("shared_config_slave").info("Got a SIGTERM, stopping the slave")
    sys.exit(0)


if __name__ == "__main__":
    main()
