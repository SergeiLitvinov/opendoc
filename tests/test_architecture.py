"""Production imports stay inside the independent library boundary."""

import ast
import sys
from pathlib import Path

import opendoc


def test_production_imports_are_standard_library_or_document_modules():
    paths = list(Path(opendoc.__file__).parent.glob("*.py"))
    assert paths
    allowed = sys.stdlib_module_names | {"opendoc", "lxml"}
    for path in paths:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names = [item.name.split(".")[0] for item in node.names]
            elif isinstance(node, ast.ImportFrom) and node.level == 0:
                names = [(node.module or "").split(".")[0]]
            else:
                continue
            assert set(names) <= allowed, (path.name, names)
