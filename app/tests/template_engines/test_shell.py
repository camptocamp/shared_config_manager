import os
from shared_config_manager import template_engines


def test_ok(temp_dir):
    os.environ['MUTUALIZED_TEST_ENV'] = "yall"
    engine = template_engines.create_engine({
        'type': 'shell',
        'environment_variables': True,
        'data': {
            'param': 'world'
        }
    })

    file_path = os.path.join(temp_dir, 'file1')
    with open(file_path + '.tmpl', 'w') as out:
        out.write("Hello ${param} ${MUTUALIZED_TEST_ENV}\n")

    engine.evaluate(temp_dir)

    with open(file_path) as input:
        assert input.read() == "Hello world yall\n"
