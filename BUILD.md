# Сборка под Windows

PyInstaller **не умеет кросс-компиляцию**, поэтому `.exe` и установщик собираются только на
Windows (локально или на CI `windows-latest`). Сборка на Linux/macOS невозможна.

## Что нужно установить

- Windows 10/11 x64.
- **Python 3.12** (python.org), при установке — галочка «Add Python to PATH».
- **Git for Windows** (даёт Git Bash и PowerShell).
- **Inno Setup 6** — https://jrsoftware.org/isdl.php (нужен только для установщика).

Зависимости Python ставить вручную не нужно — скрипт создаёт venv и ставит сам.

## Быстрая сборка

```powershell
git clone <repo> cn_diag_tool
cd cn_diag_tool
.\build_win.ps1
```

Результат: `installer\Output\cn_tool-<версия>-setup.exe`.

Если PowerShell блокирует запуск скрипта:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\build_win.ps1
# или
powershell -ExecutionPolicy Bypass -File .\build_win.ps1
```

## Что делает `build_win.ps1`

1. определяет версию из `git describe --tags` (фолбэк — `major.minor` из `ver.py`);
2. создаёт venv `.venv-build` и ставит `requirements.txt` + `requirements-build.txt`;
3. `pyinstaller cn_diag_tool.spec` → one-dir `dist\cn_tool\`;
4. `ISCC.exe` → `installer\Output\cn_tool-<ver>-setup.exe`.

## Ручная сборка (по шагам)

```powershell
python -m venv .venv-build
.\.venv-build\Scripts\python -m pip install -r requirements.txt -r requirements-build.txt
.\.venv-build\Scripts\python -m PyInstaller --noconfirm --clean cn_diag_tool.spec
& "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" /DMyAppVersion=1.1 /DMyAppVerFile=1.1.0 installer\cn_tool.iss
```

Только portable-папка без установщика — достаточно первых трёх команд (`dist\cn_tool\`).

## Версия

- тег `v1.1` → установщик `1.1` (file version `1.1.0`);
- без тега берётся `major.minor` из `ver.py`;
- `git describe` пишется в `_build_info.py` (gitignored) и показывается в About.

## GitHub Actions

Workflow `.github/workflows/build-windows.yml` запускается на тег `v*` (и вручную
`workflow_dispatch`), собирает установщик и прикрепляет его к GitHub Release.

Основной remote проекта — bare-git сервер, поэтому для CI нужно зеркало на GitHub:

```bash
git remote add github git@github.com:<owner>/<repo>.git
git push github main --tags
```

## Частые проблемы

| Симптом | Причина / решение |
|---|---|
| `python not found` | Python не в PATH — переустановить с «Add to PATH» |
| `ISCC.exe not found` | Не установлен Inno Setup 6 |
| PowerShell не запускает `.ps1` | `Set-ExecutionPolicy -Scope Process Bypass` |
| SmartScreen/антивирус ругается | Нет подписи кода; UPX отключён (`upx=False`), но предупреждение возможно |
| Установщик не находит файлы | Сначала должна отработать `pyinstaller` (папка `dist\cn_tool\`) |
