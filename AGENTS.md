# AGENTS.md

PyQt6 desktop app for diagnosing Allen-Bradley **ControlNet** modules over CIP (via `pycomm3`).
Windows-oriented, single-user, GUI-only. Source strings are largely Russian.

## Commands

- Install deps: `pip install -r requirements.txt` (Python 3.12; `.venv/` already exists).
- Run app: `python cn_diag_tool.py` (entrypoint: `DiagWindow` at `cn_diag_tool.py:1119`).
- Windows build + installer: `.\build_win.ps1` — PyInstaller `cn_diag_tool.spec` (one-dir `dist/cn_tool/`)
  then Inno Setup `installer/cn_tool.iss` (needs Inno Setup 6; build deps in `requirements-build.txt`).
- Raw bundle only: `pip install -r requirements-build.txt; pyinstaller cn_diag_tool.spec`.

PyInstaller **cannot cross-compile**: the bundle/installer can only be produced on Windows. CI
(`.github/workflows/build-windows.yml`) runs on `windows-latest` for `v*` tags and attaches the
installer to a GitHub Release. The repo's primary remote is a bare git server; nothing is built there.
To use CI, mirror to GitHub: `git remote add github git@github.com:<owner>/<repo>.git && git push github main --tags`.

Tests: `python -m unittest discover -s tests -v` (stdlib `unittest`, no `pytest`). There is no linter
configured. Counter rate/average math is covered in `tests/test_counter_math.py`, the sequential
poller in `tests/test_poller.py`, the one-session scan in `tests/test_scan_cn.py`, the Connection
Manager parsers in `tests/test_module_stats.py`; the Excel report builder and the remembered export
directory are covered in `tests/test_excel_export.py` and `tests/test_export_paths.py`.

## Generated UI files — regenerate, don't hand-edit

`cn_diag_tool_ui.py`, `cndt_config_dialog.py`, `floating_table_ui.py` are `pyuic6` output from
`ui/*.ui`. Edit the `.ui` sources and run `./rebuild_ui.sh` (uses `./tmp/` for intermediates);
never hand-edit the generated `.py`. Icons use the `asset:` scheme (not Qt resources), so the
script rewrites `:/asset/` → `asset:`.

`cn_diag_tool_ui.py` imports and instantiates `DragTable.DraggableTableWidget` as the main
`tableWidget`, so table behavior (row drag, config persistence) lives in `DragTable.py`;
`export_data` snapshots the table there, while `DiagWindow` assembles the report (column selection,
optional cross table, metadata) and the Qt-free `excel_export.py` writes it.
The commented-out import in `cn_diag_tool.py:35` is stale — ignore it.

## i18n (translations)

Source strings are **English**; translations live in `translations/cn_diag_tool_<lang>.ts`
(currently `ru` and `fr`). A custom `i18n.TsTranslator` (`i18n.py`) parses the `.ts` at runtime, so
**no `lrelease` is needed**. `en` is the default (no catalog). Language is stored in `QSettings` key
`Language` and changing it restarts the app (`Config → Language`). See `translations/README.md` for
how to add a language (register the code in `i18n.LANGUAGES`, run `./translations/update.sh <lang>`,
fill the catalog).

- Add/change user-facing strings with `self.tr(...)` / `QCoreApplication.translate("Ctx", "...")`.
  Log messages are intentionally not translated.
- UI strings are extracted from `ui/*.ui` (context = form class); `pylupdate6` does **not** see
  pyuic6's `_translate(...)` alias in the generated `.py`, so never rely on those.
- `LABELS` is built before the translator exists: wrap its text with `QT_TRANSLATE_NOOP("LABELS", ...)`
  and translate at the point of use via `tr_label()`.
- After changing strings run `./translations/update.sh` (runs `pylupdate6`, reports uncovered
  messages) and fill `translations/cn_diag_tool_ru.ts`.

## Architecture

- `cn_diag_tool.py` — main window and all UI logic (`DiagWindow`) + `HeaderData`/`LABELS` column schema.
- `cn_poller.py` — `ControlNetPoller`, one `QThread` for all CN nodes; one CIP session, sequential counters/LED polling, optional per-node class 0x06 Connection Manager stats.
- `counter_math.py` — `CounterTracker`, per-node counter rate/average math (wrap/reset aware).
- `module_stats.py` — parsers for the Connection Manager object (class 0x06): entry list, CPU, buffers.
- `cn_lib.py` — `scan_cn()` scans CN node numbers `0..99` at a CIP path for modules.
- `cip_request.py` — `pycomm3` CIP message definitions and `Struct` decoders (counter/LED/identity layouts).
- `excel_export.py` — Qt-free XLSX report builder (metadata block, typed cells, styling, LED legend).
- `export_paths.py` — remembers the last Excel export directory (QSettings), defaulting to `<config>/sites`.
- `ver.py` — version from `major.minor` plus `git describe`; fallback to generated `_build_info.py`.

An unrelated tag read/write tab (`form_tab_widget.py`, `form_tab2_widget_ui.py`) was removed as a
leftover from the source monorepo; it referenced attributes of the old polling worker (`pooling`,
`read_tags`, `write_tags`) that no longer exist. `ui/FormTab2.ui` is its orphaned source.

Runtime flow: user enters a CIP path → `scan_cn` finds nodes over one CIP session → one
`ControlNetPoller` polls all nodes sequentially over a single session, with a configurable cycle
(`Config → Read Timer`). While the Connection Manager window is open, the same poller also reads
class 0x06 attrs 9/1/11/12/13 per node every 5 s. Most functionality is untestable without real
ControlNet hardware/PLC.

## Config & user data

`user_data.get_user_data_path()` → `~/.config/CN_diag_tool` (Linux/macOS) or
`%APPDATA%/CN_diag_tool` (Windows). Holds `config.json`, `main_table.json`, and `sites/*.json`.
`config.json` stores the close confirmation, LED blink period and poll cycle (`Poll_interval`, ms).
Qt `QSettings` uses org `CPC`, app `CN_Diagnostic_Tool` (window geometry).

A site (a ControlNet network) is a JSON file: `{"CN": {"path": ...}, "rows": [...], "serials": {...},
"names": {...}, "revs": {...}, "media": [...]}`, where `rows` is the exact top-to-bottom table order
(a node is `"[NN]"`, a media converter is `"=/="`) and the optional `serials`/`names`/`revs` maps
`"[NN]"` to that module's serial number, product name and revision. `media` holds the free-text
"номер" (Serial) column of media-converter rows, one string per `"=/="` in `rows` order. The loader
also accepts the legacy `"nodes"` mapping (entry -> visual index) as a fallback.

- `cn_diag_tool.spec` generates `_build_info.py` (gitignored) with the baked-in commit hash.
- `changelog.txt` is read at runtime and shown in the About/Changelog dialog — update it when bumping features.
- `change.log` is a scratch file, not user-facing.
