"""Otoge Input Viewer - cx_Freeze build settings."""

import os
import sys
from pathlib import Path

from cx_Freeze import Executable, setup

ROOT = Path(__file__).resolve().parent


def existing_include_files(*pairs: tuple[str, str]) -> list[tuple[str, str]]:
    result = []
    for source, target in pairs:
        source_path = ROOT / source
        if source_path.exists():
            result.append((str(source_path), target))
    return result


include_files: list[tuple[str, str]] = []

try:
    import PySide6

    pyside6_path = Path(PySide6.__file__).parent
    plugins_dir = pyside6_path / "plugins"
    if plugins_dir.exists():
        for plugin_name in ("platforms", "imageformats", "styles", "iconengines", "tls"):
            plugin_dir = plugins_dir / plugin_name
            if plugin_dir.exists():
                include_files.append((str(plugin_dir), f"lib/PySide6/plugins/{plugin_name}"))

    translations_dir = pyside6_path / "translations"
    if translations_dir.exists():
        for translation_name in ("qt_ja.qm", "qtbase_ja.qm"):
            translation_file = translations_dir / translation_name
            if translation_file.exists():
                include_files.append((str(translation_file), f"lib/PySide6/translations/{translation_name}"))

    qt_conf = ROOT / "qt.conf"
    qt_conf.write_text(
        "[Paths]\n"
        "Prefix = .\n"
        "Binaries = .\n"
        "Plugins = lib/PySide6/plugins\n",
        encoding="utf-8",
    )
    include_files.append((str(qt_conf), "qt.conf"))
except ImportError:
    print("Warning: PySide6 not found. Build may not work correctly.")

include_files += existing_include_files(
    ("html", "html"),
    ("version.txt", "version.txt"),
)

build_exe_options = {
    "packages": [
        "PySide6.QtCore",
        "PySide6.QtGui",
        "PySide6.QtWidgets",
        "bs4",
        "packaging",
        "pygame",
        "requests",
        "websockets",
    ],
    "includes": [
        "asyncio",
        "ctypes",
        "ctypes.util",
        "ctypes.wintypes",
        "icon",
        "settings",
        "update",
    ],
    "excludes": [
        "distutils",
        "matplotlib",
        "pandas",
        "pip",
        "pyarmor",
        "PyInstaller",
        "setuptools",
        "test",
        "tkinter",
        "unittest",
        "PySide6.Qt3DCore",
        "PySide6.Qt3DRender",
        "PySide6.QtCharts",
        "PySide6.QtDataVisualization",
        "PySide6.QtMultimedia",
        "PySide6.QtNetwork",
        "PySide6.QtOpenGL",
        "PySide6.QtPrintSupport",
        "PySide6.QtQml",
        "PySide6.QtQuick",
        "PySide6.QtSql",
        "PySide6.QtTest",
        "PySide6.QtWebEngineCore",
        "PySide6.QtWebEngineWidgets",
    ],
    "include_files": include_files,
    "include_msvcr": True,
    "zip_include_packages": [],
    "zip_exclude_packages": ["*"],
    "optimize": 2,
    "build_exe": "otoge_input_viewer",
}

base = "Win32GUI" if sys.platform == "win32" else None
icon_path = "icon.ico" if os.path.exists("icon.ico") else None

executables = [
    Executable(
        script="otoge_input_viewer.pyw",
        base=base,
        target_name="otoge_input_viewer.exe" if sys.platform == "win32" else "otoge_input_viewer",
        icon=icon_path,
        shortcut_name="otoge_input_viewer",
        shortcut_dir="DesktopFolder",
    ),
    Executable(
        script="update.py",
        base=base,
        target_name="update.exe" if sys.platform == "win32" else "update",
        icon=icon_path,
    ),
]

setup(
    name="otoge_input_viewer",
    version="1.0.0",
    description="Otoge Input Viewer for OBS",
    options={"build_exe": build_exe_options},
    executables=executables,
)
