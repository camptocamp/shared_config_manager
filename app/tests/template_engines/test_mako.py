import os
import pathlib

from shared_config_manager import template_engines


def test_ok(temp_dir) -> None:
    engine = template_engines.create_engine("test", {"type": "mako", "data": {"param": "world"}})

    file_path = pathlib.Path(temp_dir) / "file1"
    with file_path.with_suffix(".mako").open("w") as out:
        out.write("Hello ${param}\n")

    files = [pathlib.Path(os.path.relpath(str(p), temp_dir)) for p in pathlib.Path(temp_dir).glob("**/*")]
    engine.evaluate(temp_dir, files)

    with file_path.open() as input_:
        assert input_.read() == "Hello world\n"
