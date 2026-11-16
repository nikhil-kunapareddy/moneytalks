# PyInstaller spec for MoneyTalks.app. Build with: packaging/build_macos.sh <version>
# -*- mode: python ; coding: utf-8 -*-
import os

ROOT = os.path.abspath(os.path.join(SPECPATH, ".."))
VERSION = os.environ.get("MONEYTALKS_VERSION", "0.0.0")

a = Analysis(
    [os.path.join(ROOT, "app.py")],
    pathex=[ROOT],
    datas=[
        (os.path.join(ROOT, "src", "visualizations", "templates"), "src/visualizations/templates"),
        (os.path.join(ROOT, "src", "visualizations", "assets", "icon-128.png"), "src/visualizations/assets"),
    ],
    excludes=["tkinter", "matplotlib", "IPython", "pytest", "notebook"],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="MoneyTalks",
    console=False,
    argv_emulation=False,
    codesign_identity=None,
)

coll = COLLECT(exe, a.binaries, a.datas, name="MoneyTalks")

app = BUNDLE(
    coll,
    name="MoneyTalks.app",
    icon=os.path.join(SPECPATH, "MoneyTalks.icns"),
    bundle_identifier="io.github.nikhil-kunapareddy.moneytalks",
    version=VERSION,
    info_plist={
        "CFBundleDisplayName": "MoneyTalks",
        "CFBundleShortVersionString": VERSION,
        "CFBundleVersion": VERSION,
        "LSMinimumSystemVersion": "12.0",
        "NSHighResolutionCapable": True,
        "LSApplicationCategoryType": "public.app-category.finance",
    },
)
