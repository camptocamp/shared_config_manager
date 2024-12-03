from shared_config_manager.configuration import TemplateEnginesConfig
from shared_config_manager.template_engines import base, mako, shell

ENGINES = {"mako": mako.MakoEngine, "shell": shell.ShellEngine}


def create_engine(source_id: str, config: TemplateEnginesConfig) -> base.BaseEngine:
    """Create a template engine."""
    type_ = config["type"]
    return ENGINES[type_](source_id, config)
