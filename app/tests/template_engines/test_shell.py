import os

from shared_config_manager import template_engines


def test_ok(temp_dir) -> None:
    os.environ["MUTUALIZED_TEST_ENV"] = "yall"
    engine = template_engines.create_engine(
        "test",
        {"type": "shell", "environment_variables": True, "data": {"param": "world"}},
    )

    file_path = temp_dir / "file1"
    tmpl_file_path = temp_dir / "file1.tmpl"
    with open(tmpl_file_path, "w") as out:
        out.write("Hello ${param} ${MUTUALIZED_TEST_ENV}\n")

    files = [p.relative_to(temp_dir) for p in temp_dir.glob("**/*")]
    engine.evaluate(temp_dir, files)

    with open(file_path) as input:
        assert input.read() == "Hello world yall\n"


def test_dest_sub_dir(temp_dir) -> None:
    os.environ["MUTUALIZED_TEST_ENV"] = "yall"
    engine = template_engines.create_engine(
        "test",
        {"type": "shell", "dest_sub_dir": "copy", "environment_variables": True, "data": {"param": "world"}},
    )

    tmpl_file_path = temp_dir / "file1.tmpl"
    with open(tmpl_file_path, "w") as out:
        out.write("Hello ${param} ${MUTUALIZED_TEST_ENV}\n")
    with (temp_dir / "file2").open("w") as out:
        out.write("Hello\n")

    files = [p.relative_to(temp_dir) for p in temp_dir.glob("**/*")]
    engine.evaluate(temp_dir, files)

    with open(temp_dir / "copy" / "file1") as input:
        assert input.read() == "Hello world yall\n"

    with open(temp_dir / "copy" / "file2") as input:
        assert input.read() == "Hello\n"
    assert not (temp_dir / "copy" / "copy").exists()
