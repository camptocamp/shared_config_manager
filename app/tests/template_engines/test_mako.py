import os
from shared_config_manager import template_engines


def test_ok(temp_dir):
    engine = template_engines.create_engine({
        'type': 'mako',
        'data': {
            'param': 'world'
        }
    })

    file_path = os.path.join(temp_dir, 'file1')
    with open(file_path + '.mako', 'w') as out:
        out.write("Hello ${param}\n")

    engine.evaluate(temp_dir)

    with open(file_path) as input:
        assert input.read() == "Hello world\n"
