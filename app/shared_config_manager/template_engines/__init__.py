from .import base, mako, shell

ENGINES = {
    'mako': mako.MakoEngine,
    'shell': shell.ShellEngine
}


def create_engine(config) -> base.BaseEngine:
    global ENGINES
    type_ = config['type']
    return ENGINES[type_](config)
