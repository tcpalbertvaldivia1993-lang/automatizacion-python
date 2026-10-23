# Lets the tests import cleaning.py and the other modules from the project root folder.
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
