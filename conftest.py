"""Root conftest.py.

Ensures the repository root is on ``sys.path`` so tests can load Lambda
modules through :mod:`importlib`; ``lambda`` is a Python keyword and cannot
be used in a plain import statement.
"""
import os
import sys

REPO_ROOT = os.path.dirname(os.path.abspath(__file__))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)
