# AGENTS.md

PyQt6 desktop app for diagnosing Allen-Bradley **ControlNet** modules over CIP (via `pycomm3`).
Windows-oriented, single-user, GUI-only. Source strings are largely Russian.

## Commands

- Install deps: `pip install -r requirements.txt` (Python 3.12; `.venv/` already exists).
- Run app: `python cn_diag_tool.py` (entrypoint: `DiagWindow` at `cn_diag_tool.py:1119`).
- Build exe: `pyinstaller cn_diag_tool.spec` (produces `cn_tool`; Windows-targeted).

There is **no test suite, linter, or CI** in this repo. Do not invent `pytest`/lint commands.

## Generated UI files — regenerate, don't hand-edit

`cn_diag_tool_ui.py`, `cndt_config_dialog.py`, `floating_table_ui.py` are `pyuic6` output from
`ui/*.ui`. Edit the `.ui` sources and run `./rebuild_ui.sh` (uses `./tmp/` for intermediates);
never hand-edit the generated `.py`. Icons use the `asset:` scheme (not Qt resources), so the
script rewrites `:/asset/` → `asset:`.

`cn_diag_tool_ui.py` imports and instantiates `DragTable.DraggableTableWidget` as the main
`tableWidget`, so table behavior (row drag, config persistence, `export_to_excel`) lives in
`DragTable.py`. The commented-out import in `cn_diag_tool.py:35` is stale — ignore it.

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

- `cn_diag_tool.spec` generates `_build_info.py` (gitignored) with the baked-in commit hash.
- `changelog.txt` is read at runtime and shown in the About/Changelog dialog — update it when bumping features.
- `change.log` is a scratch file, not user-facing.
