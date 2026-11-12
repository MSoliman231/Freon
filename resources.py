from pathlib import Path

from PySide6.QtGui import QIcon, QPixmap

ASSETS_DIR = Path(__file__).resolve().parent / "assets"


def asset_path(name):
    return str(ASSETS_DIR / name)


def icon(name):
    return QIcon(asset_path(name))


def pixmap(name):
    return QPixmap(asset_path(name))