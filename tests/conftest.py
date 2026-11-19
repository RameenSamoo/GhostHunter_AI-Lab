import sys
from pathlib import Path

# Make the project root importable (config, core, ...) when running pytest.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
