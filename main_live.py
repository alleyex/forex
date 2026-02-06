import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent
SRC_DIR = ROOT_DIR / "src"
root_str = str(ROOT_DIR)
src_str = str(SRC_DIR)
if src_str in sys.path:
    sys.path.remove(src_str)
sys.path.insert(0, src_str)
if root_str in sys.path:
    sys.path.remove(root_str)

from app.entrypoints.live import main


if __name__ == "__main__":
    sys.exit(main())
