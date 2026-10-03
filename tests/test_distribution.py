"""Release verification must reject contaminated or inconsistent artifacts."""

import io
import tarfile
import zipfile

import pytest

from tools.check_distribution import read_sdist, read_wheel

LICENSE = b"Approved license fixture"
PROJECT = b"""[project]
dynamic = ["version"]
[tool.setuptools.dynamic]
version = {attr = "opendoc.__version__"}
"""
METADATA = b"""Metadata-Version: 2.4
Name: opendoc
Version: 0.1.0
Requires-Python: >=3.11
License-Expression: MIT
License-File: LICENSE
Provides-Extra: math
Provides-Extra: dev
Provides-Extra: docs
Requires-Dist: lxml>=5.0; extra == "math"
"""


def _wheel(path, change=None):
    entries = {
        "opendoc/__init__.py": b'__version__ = "0.1.0"\n',
        "opendoc/py.typed": b"",
        "opendoc-0.1.0.dist-info/METADATA": METADATA,
        "opendoc-0.1.0.dist-info/licenses/LICENSE": LICENSE,
    }
    if change is not None:
        change(entries)
    with zipfile.ZipFile(path, "w") as archive:
        for name, value in entries.items():
            archive.writestr(name, value)


@pytest.mark.parametrize(
    "change",
    [
        lambda entries: entries.update({"consumer_app/main.py": b""}),
        lambda entries: entries.update({"opendoc/__pycache__/model.pyc": b""}),
        lambda entries: entries.update({"opendoc-0.1.0.dist-info/licenses/LICENSE": b"Different owner"}),
        lambda entries: entries.update({"opendoc-0.1.0.dist-info/METADATA": METADATA.replace(b"0.1.0", b"0.2.0")}),
        lambda entries: entries.update({"opendoc/__init__.py": b'__version__ = "0.2.0"\n'}),
    ],
)
def test_release_verifier_rejects_contaminated_or_inconsistent_wheel(tmp_path, change):
    path = tmp_path / "artifact.whl"
    _wheel(path)
    assert read_wheel(path, "0.1.0", LICENSE)["opendoc/py.typed"] == b""
    _wheel(path, change)
    with pytest.raises(ValueError):
        read_wheel(path, "0.1.0", LICENSE)


def test_release_verifier_rejects_duplicate_wheel_entry(tmp_path):
    path = tmp_path / "artifact.whl"
    _wheel(path)
    with zipfile.ZipFile(path, "a") as archive, pytest.warns(UserWarning, match="Duplicate"):
        archive.writestr("opendoc/py.typed", b"")
    with pytest.raises(ValueError, match="Duplicate"):
        read_wheel(path, "0.1.0", LICENSE)


@pytest.mark.parametrize(
    "unexpected", ["../outside", "src/consumer_app/main.py", "docs/.opendoc/cache", "tools/__pycache__/x.pyc"]
)
def test_release_verifier_rejects_sdist_contamination(tmp_path, unexpected):
    entries = {
        "PKG-INFO": METADATA,
        "LICENSE": LICENSE,
        "src/opendoc/__init__.py": b'__version__ = "0.1.0"\n',
        "src/opendoc/py.typed": b"",
        "pyproject.toml": PROJECT,
    }
    path = tmp_path / "artifact.tar.gz"

    def write():
        with tarfile.open(path, "w:gz") as archive:
            for name, data in entries.items():
                member = tarfile.TarInfo("opendoc-0.1.0/" + name)
                member.size = len(data)
                archive.addfile(member, io.BytesIO(data))

    write()
    assert read_sdist(path, "0.1.0", LICENSE)["LICENSE"] == LICENSE
    entries[unexpected] = b"unwanted"
    write()
    with pytest.raises(ValueError):
        read_sdist(path, "0.1.0", LICENSE)
