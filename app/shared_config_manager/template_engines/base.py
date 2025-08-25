import logging
import os
from pathlib import Path
from typing import cast

from prometheus_client import Counter, Gauge

from shared_config_manager.configuration import (
    TemplateEnginesConfig,
    TemplateEnginesStatus,
)

_LOG = logging.getLogger(__name__)
_ENV_PREFIXES = os.environ.get("SCM_ENV_PREFIXES", "MUTUALIZED_").split(":")
_ERROR_COUNTER = Counter(
    "sharedconfigmanager_template_error_counter",
    "Number of template errors",
    ["source", "type"],
)
_ERROR_GAUGE = Gauge("sharedconfigmanager_template_error_status", "Template in error", ["source", "type"])


class BaseEngine:
    """Base class for template engines."""

    def __init__(self, source_id: str, config: TemplateEnginesConfig, extension: str) -> None:
        self._source_id = source_id
        self._config = config
        self._extension = extension
        if self._config.get("environment_variables", False):
            self._data = _filter_env(cast("dict[str, str]", os.environ))
            self._data.update(config.get("data", {}))
        else:
            self._data = config.get("data", {})

    def evaluate(self, root_dir: Path, files: list[Path]) -> None:
        dest_dir = self._get_dest_dir(root_dir)
        _LOG.info(
            "Evaluating templates %s -> %s with data keys: %s",
            root_dir,
            dest_dir,
            ", ".join(self._data.keys()),
        )

        for sub_path in files:
            src_path = root_dir / sub_path
            dest_path = dest_dir / sub_path
            dest_path.parent.mkdir(parents=True, exist_ok=True)
            if src_path.suffix == "." + self._extension:
                dest_path = dest_path.parent / dest_path.stem
                _LOG.debug("Evaluating template: %s -> %s", src_path, dest_path)
                try:
                    self._evaluate_file(src_path, dest_path)
                    _ERROR_GAUGE.labels(source=self._source_id, type=self.get_type()).set(0)
                except Exception:  # noqa: BLE001
                    _LOG.warning(
                        "Failed applying the %s template: %s",
                        self._config["type"],
                        src_path,
                        exc_info=True,
                    )
                    _ERROR_COUNTER.labels(source=self._source_id, type=self.get_type()).inc()
                    _ERROR_GAUGE.labels(source=self._source_id, type=self.get_type()).set(1)
            elif src_path != dest_path and not src_path.is_dir() and not dest_path.exists():
                os.link(src_path, dest_path)

    def _get_dest_dir(self, root_dir: Path) -> Path:
        if "dest_sub_dir" in self._config:
            return root_dir / self._config["dest_sub_dir"]
        return root_dir

    def _evaluate_file(self, src_path: Path, dst_path: Path) -> None:
        pass

    def get_type(self) -> str:
        return self._config["type"]

    def get_stats(self, stats: TemplateEnginesStatus) -> None:
        if self._config.get("environment_variables", False):
            stats["environment_variables"] = _filter_env(cast("dict[str, str]", os.environ))


def _filter_env(env: dict[str, str]) -> dict[str, str]:
    return {key: value for key, value in env.items() if any(key.startswith(i) for i in _ENV_PREFIXES)}
