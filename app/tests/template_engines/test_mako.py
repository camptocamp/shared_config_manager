import os
import pathlib

from shared_config_manager import template_engines


def test_ok(temp_dir):
    engine = template_engines.create_engine("test", {"type": "mako", "data": {"param": "world"}})

    file_path = os.path.join(temp_dir, "file1")
    with open(file_path + ".mako", "w") as out:
        out.write("Hello ${param}\n")

    files = [os.path.relpath(str(p), temp_dir) for p in pathlib.Path(temp_dir).glob("**/*")]
    engine.evaluate(temp_dir, files)

    with open(file_path) as input:
        assert input.read() == "Hello world\n"
