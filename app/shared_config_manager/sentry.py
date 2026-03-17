"""Sentry initialization helpers."""

import logging
import os

import c2casgiutils.config
import sentry_sdk

_LOGGER = logging.getLogger(__name__)


def init_sentry() -> None:
    """Initialize Sentry if configured."""
    sentry_config = c2casgiutils.config.settings.sentry
    if not sentry_config.dsn and "SENTRY_DSN" not in os.environ:
        return
    _LOGGER.info("Sentry is enabled with URL: %s", sentry_config.dsn)
    sentry_init_args = {
        key: value for key, value in sentry_config.model_dump().items() if value is not None and key != "tags"
    }
    sentry_sdk.init(**sentry_init_args)
    for tag, value in (sentry_config.tags or {}).items():
        sentry_sdk.set_tag(tag, value)
