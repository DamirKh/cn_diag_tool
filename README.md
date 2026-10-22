# ControlNet Diagnostic Tool

**Language:** English | [Русский](README_RUS.md)

[![build-windows](https://github.com/DamirKh/cn_diag_tool/actions/workflows/build-windows.yml/badge.svg)](https://github.com/DamirKh/cn_diag_tool/actions/workflows/build-windows.yml)
[![license: GPL-3.0](https://img.shields.io/badge/license-GPL--3.0-blue.svg)](LICENSE)

Desktop application (PyQt6) for diagnosing **Allen-Bradley ControlNet** modules over CIP
(via [`pycomm3`](https://github.com/ottowayi/pycomm3)). Primary target is Windows (build/packaging),
but the app also runs on Linux/macOS. The UI is available in English/Russian/French.

## Features

- **Scan a ControlNet network** over a CIP path (`Scan CN`) — find nodes and start polling them.
- **Show/Pause** polling (`Show`/`Pause`).
- **Real-time counters and diagnostics**: channel A/B and active-channel frame errors, noise hits,
  collisions, NUT/slot overloads, blockages, non-concurrence, lonely/duplicate nodes, rogue events,
  and more (ControlNet Object, attribute `0x82`).
- **LED states**: channels A/B, active channel, redundancy loss.
- **Module identity**: serial number (`SN`), type (`Type`), revision (`Rev`).
- **Bad-frame cross table** showing the number of "complaints" of each node against the others.
- **Media converters** (`=/=`) as separate rows with free-text "SN".
- **Sites** — save/load the network layout and module data as JSON (row order, serials, names/types,
  revisions, media converters).
- **Export to Excel**, reset counters, acknowledge changes.
- **ControlNet path help and validation.**
- **Multilingual UI** (en/ru/fr), switch in `Config → Language`.

> Most features require real ControlNet/PLC hardware; without it, only the UI and parsing of saved
> sites are available.

## Requirements

- Python **3.12**
- Dependencies from [`requirements.txt`](requirements.txt): `pycomm3`, `PyQt6`, `pandas`, `openpyxl`

## Run from source

```bash
pip install -r requirements.txt
python cn_diag_tool.py
```

User data (settings, sites, table layout) is stored in `%APPDATA%/CN_diag_tool` (Windows) or
`~/.config/CN_diag_tool` (Linux/macOS).

## Development workflow

- **UI layouts** live in `ui/*.ui`. Open them with **Qt Designer**, edit and save.
- After changing a `.ui`, regenerate the Python UI modules:
  ```bash
  ./rebuild_ui.sh
  ```
  It runs `pyuic6` and writes `cn_diag_tool_ui.py`, `floating_table_ui.py`,
  `cndt_config_dialog.py` (using `./tmp/` for intermediates). Never hand-edit the generated
  `*_ui.py` files.
- **User-facing strings** are English. Wrap them with `self.tr(...)` or
  `QCoreApplication.translate("Ctx", ...)`; for `LABELS` use `QT_TRANSLATE_NOOP("LABELS", ...)`.
  After changing strings run `./translations/update.sh` and translate the resulting `.ts`
  (Qt Linguist or any text editor).
- Run the app while developing: `python cn_diag_tool.py`.
- Run the tests (stdlib `unittest`, no `pytest`):
  ```bash
  python -m unittest discover -s tests -v
  ```

### Release

1. bump `ver.py` (`major`/`minor`) and add a `changelog.txt` entry;
2. commit and merge the work into `main`;
3. push a `v*` tag — CI builds the Windows installer and attaches it to a GitHub Release:
   ```bash
   git tag -a v1.3 -m v1.3
   git push github v1.3
   ```

## Build for Windows

The installer is built with PyInstaller (`cn_diag_tool.spec`) + Inno Setup (`installer/cn_tool.iss`):

```powershell
.\build_win.ps1
```

The result is `installer\Output\cn_tool-<version>-setup.exe`. PyInstaller **cannot cross-compile**,
so the bundle/installer can only be produced on Windows. See [`BUILD.md`](BUILD.md) for details.

CI ([`.github/workflows/build-windows.yml`](.github/workflows/build-windows.yml)) builds the
installer on `windows-latest` when a `v*` tag is pushed and attaches it to a GitHub Release.

## UI languages

Source strings are English; translations live in `translations/*.ts` and are read directly at
runtime (`lrelease` is not required). To add a language, see
[`translations/README.md`](translations/README.md).

In short: register the code in `i18n.LANGUAGES`, run `./translations/update.sh <lang>`, and fill the
generated `translations/cn_diag_tool_<lang>.ts`.

## License

[GNU General Public License v3.0](LICENSE). Icons — Fugue Icons (C) 2013 Yusuke Kamiyamane.
