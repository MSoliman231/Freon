from PySide6.QtGui import QIcon, QPixmap

import paths

ASSETS_DIR = paths.resource_dir() / "Assets"


def asset_path(name):
    return str(ASSETS_DIR / name)


def icon(name):
    return QIcon(asset_path(name))


def pixmap(name):
    return QPixmap(asset_path(name))