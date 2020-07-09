import os
import pathlib

from shared_config_manager import template_engines


def test_ok(temp_dir):
    os.environ["MUTUALIZED_TEST_ENV"] = "yall"
    engine = template_engines.create_engine(
        "test", {"type": "shell", "environment_variables": True, "data": {"param": "world"}}
    )

    file_path = os.path.join(temp_dir, "file1")
    with open(file_path + ".tmpl", "w") as out:
        out.write("Hello ${param} ${MUTUALIZED_TEST_ENV}\n")

    files = [os.path.relpath(str(p), temp_dir) for p in pathlib.Path(temp_dir).glob("**/*")]
    engine.evaluate(temp_dir, files)

    with open(file_path) as input:
        assert input.read() == "Hello world yall\n"


def test_dest_sub_dir(temp_dir):
    os.environ["MUTUALIZED_TEST_ENV"] = "yall"
    engine = template_engines.create_engine(
        "test",
        {"type": "shell", "dest_sub_dir": "copy", "environment_variables": True, "data": {"param": "world"}},
    )

    file_path = os.path.join(temp_dir, "file1")
    with open(file_path + ".tmpl", "w") as out:
        out.write("Hello ${param} ${MUTUALIZED_TEST_ENV}\n")
    with open(os.path.join(temp_dir, "file2"), "w") as out:
        out.write("Hello\n")

    files = [os.path.relpath(str(p), temp_dir) for p in pathlib.Path(temp_dir).glob("**/*")]
    engine.evaluate(temp_dir, files)

    with open(os.path.join(temp_dir, "copy", "file1")) as input:
        assert input.read() == "Hello world yall\n"

    with open(os.path.join(temp_dir, "copy", "file2")) as input:
        assert input.read() == "Hello\n"
    assert not os.path.exists(os.path.join(temp_dir, "copy", "copy"))
