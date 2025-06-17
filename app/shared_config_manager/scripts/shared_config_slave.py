#!/usr/bin/env python3

import argparse
import logging
import os
import signal
import sys
import time
from types import FrameType

import c2cwsgiutils.setup_process
import prometheus_client

from shared_config_manager.sources import registry


def main() -> None:
    """Get the WSGI application."""
    parser = argparse.ArgumentParser(description="Run the shared config slave")
    c2cwsgiutils.setup_process.fill_arguments(parser)
    args = parser.parse_args()

    os.environ["IS_SLAVE"] = "true"

    if os.environ.get("C2C_PROMETHEUS_PORT") is not None:
        prometheus_client.start_http_server(int(os.environ["C2C_PROMETHEUS_PORT"]))

    signal.signal(signal.SIGTERM, _sig_term)

    c2cwsgiutils.setup_process.bootstrap_application_from_options(args)

    registry.init(slave=True)
    while True:
        time.sleep(3600)


def _sig_term(signum: int, frame: FrameType | None) -> None:
    del signum, frame
    logging.getLogger("shared_config_slave").info("Got a SIGTERM, stopping the slave")
    sys.exit(0)


if __name__ == "__main__":
    main()
