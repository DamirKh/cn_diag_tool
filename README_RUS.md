# ControlNet Diagnostic Tool

**Язык:** Русский | [English](README.md)

[![build-windows](https://github.com/DamirKh/cn_diag_tool/actions/workflows/build-windows.yml/badge.svg)](https://github.com/DamirKh/cn_diag_tool/actions/workflows/build-windows.yml)
[![license: GPL-3.0](https://img.shields.io/badge/license-GPL--3.0-blue.svg)](LICENSE)

Десктопное приложение (PyQt6) для диагностики модулей **Allen-Bradley ControlNet** по CIP
(через [`pycomm3`](https://github.com/ottowayi/pycomm3)). Основной таргет — Windows (сборка и
поставка), приложение запускается и на Linux/macOS. Интерфейс — английский/русский/французский.

## Возможности

- **Сканирование сети ControlNet** по CIP-пути (`Scan CN`) — поиск узлов и запуск их опроса.
- **Показ/пауза** опроса (`Show`/`Pause`).
- **Счётчики и диагностика** в реальном времени: ошибки кадров каналов A/B и активного канала,
  шумовые срабатывания, коллизии, перегрузки NUT/слота, блокировки, несогласованность,
  «одинокие»/дубликаты узлов, rogue-события и др. (ControlNet Object, атрибут `0x82`).
- **Индикаторы LEDs**: каналы A/B, активный канал, потеря резерва.
- **Идентификация модуля**: серийный номер (`SN`), тип (`Type`), ревизия (`Rev`).
- **Кросс-таблица ошибок** с числом «жалоб» каждого узла на другие узлы.
- **Медиаконвертеры** (`=/=`) как отдельные строки с произвольным текстом «номера».
- **Сайты** — сохранение/загрузка раскладки сети и данных модулей в JSON (порядок строк,
  серийники, имена/типы, ревизии, медиаконвертеры).
- **Экспорт в Excel**, сброс счётчиков, подтверждение (Acknowledge) изменений.
- **Помощь и валидация** формата ControlNet-пути.
- **Многоязычный интерфейс** (en/ru/fr), переключение в `Config → Language`.

> Большая часть функций требует реального оборудования ControlNet/PLC; без него доступен только
> интерфейс и разбор сохранённых сайтов.

## Требования

- Python **3.12**
- Зависимости из [`requirements.txt`](requirements.txt): `pycomm3`, `PyQt6`, `pandas`, `openpyxl`

## Запуск из исходников

```bash
pip install -r requirements.txt
python cn_diag_tool.py
```

Пользовательские данные (настройки, сайты, раскладка таблицы) хранятся в
`%APPDATA%/CN_diag_tool` (Windows) или `~/.config/CN_diag_tool` (Linux/macOS).

## Сборка под Windows

Готовый установщик собирается PyInstaller (`cn_diag_tool.spec`) + Inno Setup
(`installer/cn_tool.iss`):

```powershell
.\build_win.ps1
```

Результат — `installer\Output\cn_tool-<версия>-setup.exe`. PyInstaller **не умеет
кросс-компиляцию**, поэтому сборка возможна только на Windows. Подробнее — в
[`BUILD.md`](BUILD.md).

CI ([`.github/workflows/build-windows.yml`](.github/workflows/build-windows.yml)) собирает
установщик на `windows-latest` при пуше тега `v*` и прикрепляет его к GitHub Release.

## Языки интерфейса

Исходные строки — английские; переводы лежат в `translations/*.ts` и читаются напрямую
(`lrelease` не нужен). Чтобы добавить язык — см. [`translations/README.md`](translations/README.md).

## Добавление языка

Кратко: зарегистрировать код в `i18n.LANGUAGES`, выполнить `./translations/update.sh <lang>`
и заполнить полученный каталог `translations/cn_diag_tool_<lang>.ts`.

## Лицензия

[GNU General Public License v3.0](LICENSE). Иконки — Fugue Icons (C) 2013 Yusuke Kamiyamane.
