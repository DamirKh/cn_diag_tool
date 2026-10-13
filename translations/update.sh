#!/usr/bin/env bash
# Update the Qt .ts catalogs from the sources (requires PyQt6's pylupdate6).
set -euo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
root="$(cd "$here/.." && pwd)"
cd "$root"

PYLUPDATE="${PYLUPDATE:-.venv/bin/pylupdate6}"
command -v "$PYLUPDATE" >/dev/null 2>&1 || PYLUPDATE="pylupdate6"

# .ui sources (context = form class name) + Python sources (tr()/translate()/NOOP)
sources=(
    ui/cn_diag_tool.main.ui
    ui/FloatingTable.ui
    ui/config_helper.ui
    cn_diag_tool.py
    i18n.py
)

"$PYLUPDATE" --no-obsolete --ts translations/cn_diag_tool_ru.ts "${sources[@]}"

unfinished=$(grep -c 'type="unfinished"' translations/cn_diag_tool_ru.ts || true)
echo "untagged/unfinished messages: ${unfinished}"
