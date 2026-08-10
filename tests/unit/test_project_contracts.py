import os
import subprocess
import sys
import tomllib
import zipfile
from inspect import signature
from pathlib import Path

import yaml
from yaml.constructor import ConstructorError

from matilda_brain.cli import cli
from matilda_brain.internal.hooks.server import on_serve
from matilda_brain.server import run_server

REPO_ROOT = Path(__file__).resolve().parents[2]


class UniqueKeyLoader(yaml.SafeLoader):
    pass


def construct_unique_mapping(loader, node, deep=False):
    mapping = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        if key in mapping:
            raise ConstructorError("mapping", node.start_mark, f"duplicate key: {key}", key_node.start_mark)
        mapping[key] = loader.construct_object(value_node, deep=deep)
    return mapping


UniqueKeyLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, construct_unique_mapping)


def load_project_contracts():
    with (REPO_ROOT / "pyproject.toml").open("rb") as project_file:
        project = tomllib.load(project_file)
    with (REPO_ROOT / "goobits.yaml").open(encoding="utf-8") as goobits_file:
        goobits = yaml.load(goobits_file, Loader=UniqueKeyLoader)
    return project, goobits


def test_goobits_config_has_unique_keys_and_matches_package_metadata():
    project, goobits = load_project_contracts()

    assert goobits["package_name"] == project["project"]["name"]
    assert goobits["cli"]["version"] == project["project"]["version"]
    assert goobits["command_name"] in project["project"]["scripts"]


def test_generated_cli_and_all_server_entry_points_default_to_loopback():
    _, goobits = load_project_contracts()
    configured_host = next(
        option for option in goobits["cli"]["commands"]["serve"]["options"] if option["name"] == "host"
    )
    serve_command = cli.commands["serve"]
    generated_host = next(parameter for parameter in serve_command.params if parameter.name == "host")

    assert configured_host["default"] == "127.0.0.1"
    assert generated_host.default == configured_host["default"]
    assert signature(on_serve).parameters["host"].default == configured_host["default"]
    assert signature(run_server).parameters["host"].default == configured_host["default"]


def test_declared_package_data_exists_in_the_source_package():
    project, _ = load_project_contracts()
    package_data = project["tool"]["setuptools"]["package-data"]

    for package_name, patterns in package_data.items():
        package_root = REPO_ROOT / "src" / package_name.replace(".", "/")
        assert package_root.is_dir()
        for pattern in patterns:
            assert list(package_root.glob(pattern)), f"Missing package data: {package_name}/{pattern}"


def test_built_wheel_is_importable_and_contains_runtime_contracts(tmp_path):
    wheel_dir = tmp_path / "wheel"
    wheel_dir.mkdir()
    subprocess.run(
        [
            sys.executable,
            "-m",
            "pip",
            "wheel",
            "--no-deps",
            "--no-build-isolation",
            "--wheel-dir",
            str(wheel_dir),
            ".",
        ],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    wheel_path = next(wheel_dir.glob("*.whl"))

    with zipfile.ZipFile(wheel_path) as wheel:
        names = set(wheel.namelist())
        assert "matilda_brain/py.typed" in names
        assert "matilda_brain/server.py" in names
        assert "matilda_brain/setup.sh" not in names
        assert any(name.endswith(".dist-info/entry_points.txt") for name in names)

    install_dir = tmp_path / "installed"
    subprocess.run(
        [sys.executable, "-m", "pip", "install", "--no-deps", "--target", str(install_dir), str(wheel_path)],
        check=True,
        capture_output=True,
        text=True,
    )
    env = {
        **os.environ,
        "PYTHONPATH": str(install_dir),
        "MATILDA_CONFIG": str(tmp_path / "missing.toml"),
        "EXPECTED_PACKAGE_ROOT": str(install_dir),
    }
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "import os; from pathlib import Path; import matilda_brain; "
                "from matilda_brain.server import create_app; "
                "assert Path(matilda_brain.__file__).resolve().is_relative_to(Path(os.environ['EXPECTED_PACKAGE_ROOT'])); "
                "assert create_app(api_token='wheel-test', allowed_origins=[])"
            ),
        ],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
