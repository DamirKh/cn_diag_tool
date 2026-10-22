"""Builds the XLSX report for the diagnostic table.

The module is deliberately Qt-free: callers extract plain values from the
widgets and pass them here, which keeps the export testable without a GUI.
"""
from dataclasses import dataclass

import openpyxl
from openpyxl.comments import Comment
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

TEXT = "text"
INT = "int"
FLOAT = "float"
LED = "led"

HEADER_FILL = PatternFill("solid", fgColor="305496")
CROSS_HEADER_COLOR = "C55A11"
HEADER_FONT = Font(bold=True, color="FFFFFF")
THIN = Side(style="thin", color="BFBFBF")
BORDER = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)
LEFT = Alignment(horizontal="left", vertical="center")
RIGHT = Alignment(horizontal="right", vertical="center")
CENTER = Alignment(horizontal="center", vertical="center", wrap_text=True)
WRAP = Alignment(horizontal="left", vertical="top", wrap_text=True)


@dataclass
class ColumnSpec:
    header: str = ""
    hint: str = ""
    longread: str = ""
    kind: str = TEXT
    logical_index: int = -1
    header_fill: str = ""


def map_cross_rows(main_labels, cross_labels):
    """Maps each main-table row to a cross-table row by label (k-th duplicate)."""
    positions = {}
    for index, label in enumerate(cross_labels):
        positions.setdefault(label, []).append(index)
    occurrences = {}
    result = []
    for label in main_labels:
        occurrence = occurrences.get(label, 0)
        occurrences[label] = occurrence + 1
        candidates = positions.get(label, [])
        result.append(candidates[occurrence] if occurrence < len(candidates) else None)
    return result


def parse_cell(kind: str, text) -> object:
    """Converts a cell's displayed text to the value stored in the workbook."""
    text = (text or "").strip()
    if not text:
        return None
    if kind == FLOAT:
        try:
            return float(text)
        except ValueError:
            return text
    if kind in (INT, LED):
        try:
            return int(text)
        except ValueError:
            return text
    return text


def _is_number(value) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _set_value(cell, value) -> None:
    """Writes a value, keeping '=...' strings as text instead of formulas."""
    cell.value = value
    if isinstance(value, str) and value.startswith("="):
        cell.data_type = "s"


def _led_fill(value):
    if not isinstance(value, int) or isinstance(value, bool):
        return None
    if value == 0:
        color = "D9D9D9"
    elif value in (1, 2):
        color = "C6EFCE"
    elif 3 <= value <= 7:
        color = "FFC7CE"
    else:
        return None
    return PatternFill("solid", fgColor=color)


def _style_data_cell(cell, spec, value):
    cell.border = BORDER
    if _is_number(value):
        if spec.kind == FLOAT:
            cell.number_format = "0.00"
            cell.alignment = RIGHT
        elif spec.kind == LED:
            cell.number_format = "0"
            cell.alignment = CENTER
            fill = _led_fill(value)
            if fill is not None:
                cell.fill = fill
        else:
            cell.number_format = "0"
            cell.alignment = RIGHT
    else:
        cell.number_format = "@"
        cell.alignment = LEFT


def _autosize(ws, ncols: int, header_row: int) -> None:
    for index in range(1, ncols + 1):
        letter = get_column_letter(index)
        longest = 0
        for row in range(header_row, ws.max_row + 1):
            value = ws.cell(row=row, column=index).value
            if value is not None:
                longest = max(longest, len(str(value)))
        width = min(max(12 if index == 1 else 10, longest + 2), 40)
        ws.column_dimensions[letter].width = width


def _add_legend(wb, legend, sheet_name: str, title: str) -> None:
    ws = wb.create_sheet(title=sheet_name or "Legend")
    ws.column_dimensions["A"].width = 100
    title_cell = ws.cell(row=1, column=1)
    _set_value(title_cell, title)
    title_cell.font = Font(bold=True, size=12)
    row = 3
    for heading, lines in legend:
        heading_cell = ws.cell(row=row, column=1)
        _set_value(heading_cell, heading)
        heading_cell.font = Font(bold=True)
        row += 1
        for line in lines:
            cell = ws.cell(row=row, column=1)
            _set_value(cell, line)
            cell.alignment = WRAP
            row += 1
        row += 1


def write_xlsx(filename, columns, rows, metadata=None, *, title="ControlNet diagnostic tool",
               corner_label="Node", sheet_name="Diagnostics", legend=None,
               legend_sheet_name="LED states", legend_title="LED state legend") -> None:
    """Writes the report and raises on I/O or formatting errors.

    Args:
        filename: destination .xlsx path.
        columns: ColumnSpec list in visual order.
        rows: iterable of (row_label, values) where values align with columns.
        metadata: iterable of (label, value) lines placed above the table.
        legend: optional iterable of (heading, [lines]) written to a second sheet.
    """
    columns = list(columns)
    rows = list(rows)
    metadata = list(metadata or [])
    ncols = len(columns) + 1
    last_col = get_column_letter(ncols)

    workbook = openpyxl.Workbook()
    sheet = workbook.active
    sheet.title = sheet_name or "Sheet"

    row = 1
    if ncols > 1:
        sheet.merge_cells(f"A{row}:{last_col}{row}")
    title_cell = sheet.cell(row=row, column=1)
    _set_value(title_cell, title)
    title_cell.font = Font(bold=True, size=14)
    title_cell.alignment = LEFT
    sheet.row_dimensions[row].height = 22
    row += 1

    for label, value in metadata:
        label_cell = sheet.cell(row=row, column=1)
        _set_value(label_cell, label)
        label_cell.font = Font(bold=True)
        label_cell.alignment = LEFT
        if ncols > 1:
            sheet.merge_cells(start_row=row, start_column=2, end_row=row, end_column=ncols)
        _set_value(sheet.cell(row=row, column=2), "" if value is None else value)
        row += 1
    if metadata:
        row += 1

    header_row = row
    corner = sheet.cell(row=header_row, column=1)
    _set_value(corner, corner_label)
    corner.fill = HEADER_FILL
    corner.font = HEADER_FONT
    corner.alignment = CENTER
    corner.border = BORDER
    for index, spec in enumerate(columns, start=2):
        cell = sheet.cell(row=header_row, column=index)
        _set_value(cell, spec.header or spec.hint)
        cell.fill = PatternFill("solid", fgColor=spec.header_fill) if spec.header_fill else HEADER_FILL
        cell.font = HEADER_FONT
        cell.alignment = CENTER
        cell.border = BORDER
        if spec.hint:
            cell.comment = Comment(spec.hint, "cn_diag_tool")
    sheet.row_dimensions[header_row].height = 45

    first_data_row = header_row + 1
    for offset, (label, values) in enumerate(rows):
        current = first_data_row + offset
        label_cell = sheet.cell(row=current, column=1)
        _set_value(label_cell, label)
        label_cell.border = BORDER
        label_cell.alignment = LEFT
        for index, spec in enumerate(columns, start=2):
            value = values[index - 2] if index - 2 < len(values) else None
            cell = sheet.cell(row=current, column=index)
            _set_value(cell, value)
            _style_data_cell(cell, spec, value)
    last_data_row = first_data_row + len(rows) - 1

    if rows:
        sheet.auto_filter.ref = f"A{header_row}:{last_col}{last_data_row}"
    sheet.freeze_panes = f"B{first_data_row}"

    _autosize(sheet, ncols, header_row)

    if legend:
        _add_legend(workbook, legend, legend_sheet_name, legend_title)

    workbook.save(filename)
