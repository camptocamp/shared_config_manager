from . import base, mako, shell

ENGINES = {"mako": mako.MakoEngine, "shell": shell.ShellEngine}


def create_engine(source_id, config) -> base.BaseEngine:
    global ENGINES
    type_ = config["type"]
    return ENGINES[type_](source_id, config)
