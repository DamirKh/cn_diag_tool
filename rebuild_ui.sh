#!/usr/bin/env bash
# Regenerate pyuic6 output from ui/*.ui (flat layout: sources in ui/, output in repo root).
set -euo pipefail

here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$here"

tmpdir="tmp"
mkdir -p "$tmpdir"

# ControlNet debug tool
pyuic6 -o "$tmpdir/cn_diag_tool_ui.py" ui/cn_diag_tool.main.ui
sed 's/:\/asset\//asset:/g' "$tmpdir/cn_diag_tool_ui.py" > cn_diag_tool_ui.py
rm "$tmpdir/cn_diag_tool_ui.py"

pyuic6 -o "$tmpdir/floating_table_ui.py" ui/FloatingTable.ui
sed 's/:\/asset\//asset:/g' "$tmpdir/floating_table_ui.py" > floating_table_ui.py
rm "$tmpdir/floating_table_ui.py"

pyuic6 -o cndt_config_dialog.py ui/config_helper.ui

#rcc -g python -o resources.py asset/asset.qrc
