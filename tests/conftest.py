import os.path
import sys

pytest_plugins = "pytester"

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))
