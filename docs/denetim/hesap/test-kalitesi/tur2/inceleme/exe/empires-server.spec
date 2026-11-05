# -*- mode: python -*-
import os
block_cipher = None


a = Analysis([r'<HOME>\Desktop\Raise\raisetheempires-pr\.claude\worktrees\agent-af55f7e566ce73807\empires-server.py'],
             pathex=[r'<HOME>\Desktop\Raise\raisetheempires-pr\.claude\worktrees\agent-af55f7e566ce73807'],
             binaries=[],
             datas=[],
             hiddenimports=['engineio.async_drivers.threading'],
             hookspath=[],
             runtime_hooks=[],
             excludes=[],
             win_no_prefer_redirects=False,
             win_private_assemblies=False,
             cipher=block_cipher,
             noarchive=False)
pyz = PYZ(a.pure, a.zipped_data,
             cipher=block_cipher)
exe = EXE(pyz,
          a.scripts,
          a.binaries,
          a.zipfiles,
          a.datas,
          [],
          name='empires-server',
          debug=False,
          bootloader_ignore_signals=False,
          strip=False,
          upx=True,
          runtime_tmpdir=None,
          console=True, icon=r'<HOME>\Desktop\Raise\raisetheempires-pr\.claude\worktrees\agent-af55f7e566ce73807\build-tools\icon.ico')
