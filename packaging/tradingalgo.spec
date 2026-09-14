# Version-controlled PyInstaller build definition for standalone TradingAlgo binaries.
from pathlib import Path

from PyInstaller.utils.hooks import collect_submodules

ROOT = Path(SPECPATH).parent.parent
SRC = ROOT / "src"
STATIC = SRC / "tradingalgo" / "web" / "static"

hiddenimports = collect_submodules("tradingalgo")
datas = [(str(STATIC), "tradingalgo/web/static")]


a = Analysis(
    [str(SRC / "tradingalgo" / "app.py")],
    pathex=[str(SRC)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["tkinter"],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="tradingalgo",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
)
