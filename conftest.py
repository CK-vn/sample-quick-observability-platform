"""Root conftest.py.

Ensures the repo root is on sys.path so tests can import `cdk/*` modules
directly (e.g. `import cdk.dashboard_stack`) and `lambda/*` modules via
`importlib.import_module("lambda.log_transform.index")` -- `lambda` is a
reserved keyword in Python so it cannot be imported with a plain `import`
statement, only via `importlib`.
"""
import os
import sys

REPO_ROOT = os.path.dirname(os.path.abspath(__file__))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)
