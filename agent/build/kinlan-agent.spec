# PyInstaller spec for KinLAN-Agent.exe (plan, Section 3.8; issue #91).
# Build from agent/:  pyinstaller build/kinlan-agent.spec --noconfirm
# One file, a console window (pairing asks for the code, setup prints what it did), and a UAC
# prompt on launch: raw sockets, the DPAPI token and the startup task all need administrator.

from PyInstaller.utils.hooks import collect_submodules

block_cipher = None

a = Analysis(
    ["../kinlan_agent/__main__.py"],
    pathex=[".."],
    datas=[("../kinlan_agent/data/oui.txt", "kinlan_agent/data")],  # vendor lookup (vendors.py)
    # Scapy and Rich load parts of themselves by name, so list them for the bundle.
    hiddenimports=collect_submodules("scapy.layers") + collect_submodules("rich")
    + ["win32crypt", "pywintypes"],
    excludes=["tkinter", "matplotlib", "numpy", "IPython"],
    noarchive=False,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    name="KinLAN-Agent",
    icon="kinlan.ico",
    console=True,
    uac_admin=True,
    upx=False,
    debug=False,
    strip=False,
)
