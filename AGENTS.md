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

There is **no test suite or linter** in this repo. Do not invent `pytest`/lint commands.

## Generated UI files — regenerate, don't hand-edit

`cn_diag_tool_ui.py`, `cndt_config_dialog.py`, `floating_table_ui.py` are `pyuic6` output from
`ui/*.ui`. Edit the `.ui` sources and run `./rebuild_ui.sh` (uses `./tmp/` for intermediates);
never hand-edit the generated `.py`. Icons use the `asset:` scheme (not Qt resources), so the
script rewrites `:/asset/` → `asset:`.

`cn_diag_tool_ui.py` imports and instantiates `DragTable.DraggableTableWidget` as the main
`tableWidget`, so table behavior (row drag, config persistence, `export_to_excel`) lives in
`DragTable.py`. The commented-out import in `cn_diag_tool.py:35` is stale — ignore it.

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
- `Plc_connection_worker.py` — `PLCConnectionWorker`, one `QThread` per CN node; polls CIP counters/LEDs, emits Qt signals.
- `cn_lib.py` — `scan_cn()` scans CN node numbers `0..99` at a CIP path for modules.
- `cip_request.py` — `pycomm3` CIP message definitions and `Struct` decoders (counter/LED/identity layouts).
- `ver.py` — version from `major.minor` plus `git describe`; fallback to generated `_build_info.py`.

An unrelated tag read/write tab (`form_tab_widget.py`, `form_tab2_widget_ui.py`) was removed as a
leftover from the source monorepo; it referenced `PLCConnectionWorker` attributes (`pooling`,
`read_tags`, `write_tags`) that no longer exist. `ui/FormTab2.ui` is its orphaned source.

Runtime flow: user enters a CIP path → `scan_cn` finds nodes → each node gets a `PLCConnectionWorker`
polling loop. Most functionality is untestable without real ControlNet hardware/PLC.

## Config & user data

`user_data.get_user_data_path()` → `~/.config/CN_diag_tool` (Linux/macOS) or
`%APPDATA%/CN_diag_tool` (Windows). Holds `config.json`, `main_table.json`, and `sites/*.json`.
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
