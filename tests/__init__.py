"""Testpaket – ermöglicht auch „python -m unittest tests.test_player“ vom Projektordner aus."""
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
for _p in (os.path.dirname(_HERE), _HERE):        # Programmordner (Module) und tests/ (helpers.py)
    if _p not in sys.path:
        sys.path.insert(0, _p)
