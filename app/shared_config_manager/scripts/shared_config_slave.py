#!/usr/bin/env python3

import argparse
import asyncio
import logging
import logging.config
import signal
from types import FrameType

import aiofiles
import c2casgiutils.config
import prometheus_client
import yaml
from c2casgiutils import broadcast
from c2casgiutils.tools import logging_ as logging_tools

from shared_config_manager import config, slave_status
from shared_config_manager.sources import base, registry

_stop_event = asyncio.Event()
_LOGGER = logging.getLogger("shared_config_slave")


def main() -> None:
    """Run the shared config slave."""
    asyncio.run(_async_main())


async def _async_main() -> None:
    """Run the shared config slave."""
    parser = argparse.ArgumentParser(description="Run the shared config slave")
    parser.parse_args()

    async with aiofiles.open("logging.yaml") as logging_file:
        logging_config = yaml.safe_load(await logging_file.read())
        logging.config.dictConfig(logging_config)

    config.settings.is_slave = True

    if c2casgiutils.config.settings.prometheus.port is not None:
        prometheus_client.start_http_server(c2casgiutils.config.settings.prometheus.port)

    signal.signal(signal.SIGTERM, _sig_term)

    await broadcast.startup()
    await logging_tools.startup(None)  # type: ignore[arg-type]
    await base.init()
    await slave_status.init()
    await registry.init(slave=True)
    await _stop_event.wait()
    _LOGGER.info("Shutting down the shared config slave")


def _sig_term(signum: int, frame: FrameType | None) -> None:
    del signum, frame
    _LOGGER.info("Got a SIGTERM, stopping the slave")
    _stop_event.set()


if __name__ == "__main__":
    main()
