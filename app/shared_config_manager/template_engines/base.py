import logging
import os
from typing import Dict, List, cast

from c2cwsgiutils import broadcast
from prometheus_client import Counter, Gauge

from shared_config_manager.configuration import TemplateEnginesConfig, TemplateEnginesStatus

_LOG = logging.getLogger(__name__)
_ENV_PREFIXES = os.environ.get("SCM_ENV_PREFIXES", "MUTUALIZED_").split(":")
_ERROR_COUNTER = Counter(
    "sharedconfigmanager_template_error_counter", "Number of template errors", ["source", "type"]
)
_ERROR_GAUGE = Gauge("sharedconfigmanager_template_error_status", "Template in error", ["source", "type"])


class BaseEngine:
    def __init__(self, source_id: str, config: TemplateEnginesConfig, extension: str) -> None:
        self._source_id = source_id
        self._config = config
        self._extension = extension
        if self._config.get("environment_variables", False):
            self._data = _filter_env(cast(Dict[str, str], os.environ))
            self._data.update(config.get("data", {}))
        else:
            self._data = config.get("data", {})

    def evaluate(self, root_dir: str, files: List[str]) -> None:
        extension_len = len(self._extension) + 1
        dest_dir = self._get_dest_dir(root_dir)
        _LOG.info(
            "Evaluating templates %s -> %s with data keys: %s",
            root_dir,
            dest_dir,
            ", ".join(self._data.keys()),
        )

        for sub_path in files:
            src_path = os.path.join(root_dir, sub_path)
            dest_path = os.path.join(dest_dir, sub_path)
            os.makedirs(os.path.dirname(dest_path), exist_ok=True)
            if src_path.endswith("." + self._extension):
                dest_path = dest_path[:-extension_len]
                _LOG.debug("Evaluating template: %s -> %s", src_path, dest_path)
                try:
                    self._evaluate_file(src_path, dest_path)
                    _ERROR_GAUGE.labels(source=self._source_id, type=self.get_type()).set(0)
                except Exception:
                    _LOG.warning(
                        "Failed applying the %s template: %s", self._config["type"], src_path, exc_info=True
                    )
                    _ERROR_COUNTER.labels(source=self._source_id, type=self.get_type()).inc()
                    _ERROR_GAUGE.labels(source=self._source_id, type=self.get_type()).set(1)
            elif src_path != dest_path and not os.path.isdir(src_path) and not os.path.exists(dest_path):
                os.link(src_path, dest_path)

    def _get_dest_dir(self, root_dir: str) -> str:
        if "dest_sub_dir" in self._config:
            return os.path.join(root_dir, self._config["dest_sub_dir"])
        else:
            return root_dir

    def _evaluate_file(self, src_path: str, dst_path: str) -> None:
        pass

    def get_type(self) -> str:
        return self._config["type"]

    def get_stats(self, stats: TemplateEnginesStatus) -> None:
        if self._config.get("environment_variables", False):
            stats["environment_variables"] = _filter_env(cast(Dict[str, str], os.environ))


def _filter_env(env: Dict[str, str]) -> Dict[str, str]:
    result = {}
    for key, value in env.items():
        if any(key.startswith(i) for i in _ENV_PREFIXES):
            result[key] = value
    return result
