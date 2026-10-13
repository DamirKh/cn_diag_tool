#!/usr/bin/env bash
# Update Qt .ts catalogs from the sources (requires PyQt6's pylupdate6).
#
# Usage:
#   ./translations/update.sh            # update every existing catalog
#   ./translations/update.sh ru         # create/update translations/cn_diag_tool_ru.ts
#   ./translations/update.sh ru fr de   # several at once
set -euo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
root="$(cd "$here/.." && pwd)"
cd "$root"

PYLUPDATE="${PYLUPDATE:-.venv/bin/pylupdate6}"
command -v "$PYLUPDATE" >/dev/null 2>&1 || PYLUPDATE="pylupdate6"

# .ui sources (context = form class name) + Python sources (tr()/translate()/NOOP).
sources=(
    ui/cn_diag_tool.main.ui
    ui/FloatingTable.ui
    ui/config_helper.ui
    cn_diag_tool.py
    i18n.py
)

langs=("$@")
if [ ${#langs[@]} -eq 0 ]; then
    shopt -s nullglob
    for f in translations/cn_diag_tool_*.ts; do
        langs+=("$(basename "$f" .ts | sed 's/^cn_diag_tool_//')")
    done
    [ ${#langs[@]} -gt 0 ] || langs=(ru)
fi

for lang in "${langs[@]}"; do
    ts="translations/cn_diag_tool_${lang}.ts"
    "$PYLUPDATE" --no-obsolete --ts "$ts" "${sources[@]}"
    unfinished=$(grep -c 'type="unfinished"' "$ts" || true)
    echo "${ts}: unfinished messages: ${unfinished}"
done
