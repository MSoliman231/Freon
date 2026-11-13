import os
import sys
from pathlib import Path

FROZEN = getattr(sys, "frozen", False)  # True when running as FREON.exe


def resource_dir():
    """Folder with the files packed inside the program (the Assets folder, ...)."""
    if FROZEN:
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
    return Path(__file__).resolve().parent


def data_dir():
    """Folder where the app saves its data. Always writable."""
    if FROZEN:
        base = Path(os.environ.get("APPDATA", str(Path.home()))) / "FREON"
    else:
        base = Path(__file__).resolve().parent  # while developing: next to the code
    base.mkdir(parents=True, exist_ok=True)
    return base