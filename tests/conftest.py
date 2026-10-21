# Permite que los tests importen limpieza.py desde la carpeta raíz del proyecto.
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
