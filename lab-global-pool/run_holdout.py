# launcher holdout
import subprocess
import sys
from pathlib import Path

subprocess.run([sys.executable, str(Path(__file__).parent / "run_lab.py"), "holdout"], check=True)
