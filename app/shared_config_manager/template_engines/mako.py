from .base import BaseEngine
import mako.template


class MakoEngine(BaseEngine):
    def __init__(self, config):
        super().__init__(config, '**/*.mako')

    def _evaluate_file(self, path):
        template = mako.template.Template(filename=path)
        with open(path[:-5], 'w') as output:
            output.write(template.render(**self._data))
