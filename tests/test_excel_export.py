"""Tests for the Excel report builder (no GUI required).

Run from the repository root:
    python -m unittest discover -s tests -v
"""
import os
import tempfile
import unittest

import openpyxl

import excel_export as x


class ParseCellTest(unittest.TestCase):
    def test_text_preserves_leading_zeros(self):
        self.assertEqual(x.parse_cell(x.TEXT, "00A1B2C3"), "00A1B2C3")

    def test_int(self):
        self.assertEqual(x.parse_cell(x.INT, "12345"), 12345)

    def test_float(self):
        self.assertEqual(x.parse_cell(x.FLOAT, "1.23"), 1.23)

    def test_led_is_int(self):
        self.assertEqual(x.parse_cell(x.LED, "7"), 7)

    def test_non_numeric_falls_back_to_text(self):
        self.assertEqual(x.parse_cell(x.INT, "N/A"), "N/A")
        self.assertEqual(x.parse_cell(x.FLOAT, "N/A"), "N/A")

    def test_empty_is_none(self):
        self.assertIsNone(x.parse_cell(x.INT, ""))
        self.assertIsNone(x.parse_cell(x.TEXT, "   "))


class WriteXlsxTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = os.path.join(self.tmp.name, "report.xlsx")
        self.columns = [
            x.ColumnSpec(header="SN", hint="Module serial number",
                         longread="8 hex digits", kind=x.TEXT, logical_index=0),
            x.ColumnSpec(header="⇑", hint="Good frames transmitted",
                         kind=x.INT, logical_index=1),
            x.ColumnSpec(header="⇑ avg", hint="Average TX/s since scan start",
                         kind=x.FLOAT, logical_index=2),
            x.ColumnSpec(header="A", hint="Channel A indicator",
                         longread="0 - off; 1 - solid green", kind=x.LED,
                         logical_index=3),
        ]
        self.rows = [
            ("[01]", ["00A1B2C3", 12345, 12.34, 1]),
            ("[02]", [None, 0, 0.0, 7]),
            ("[03]", ["00FF00FF", 5, 1.0, 0]),
            ("=/=", [None, None, None, None]),
        ]
        self.metadata = [
            ("Version", "1.3"),
            ("ControlNet path", "10.0.0.1/bp/0/cnet"),
        ]
        x.write_xlsx(
            self.path, self.columns, self.rows, self.metadata,
            title="ControlNet diagnostic tool",
            corner_label="Node",
            sheet_name="Diagnostics",
            legend=[("A — Channel A indicator", ["0 - off", "1 - solid green"])],
            legend_sheet_name="LED states",
            legend_title="LED state legend",
        )
        self.wb = openpyxl.load_workbook(self.path)
        self.ws = self.wb["Diagnostics"]

    def tearDown(self):
        self.wb.close()
        self.tmp.cleanup()

    def test_metadata_block(self):
        self.assertEqual(self.ws["A1"].value, "ControlNet diagnostic tool")
        self.assertEqual(self.ws["A2"].value, "Version")
        self.assertEqual(self.ws["B2"].value, "1.3")
        self.assertEqual(self.ws["A3"].value, "ControlNet path")
        self.assertEqual(self.ws["B3"].value, "10.0.0.1/bp/0/cnet")

    def test_header_row_uses_short_labels_and_hint_comments(self):
        # title + 2 metadata lines + blank line -> header is row 5
        self.assertEqual(self.ws["A5"].value, "Node")
        self.assertEqual(self.ws["B5"].value, "SN")
        self.assertEqual(self.ws["C5"].value, "⇑")
        self.assertEqual(self.ws["D5"].value, "⇑ avg")
        self.assertEqual(self.ws["E5"].value, "A")
        self.assertTrue(self.ws["B5"].font.bold)
        self.assertEqual(self.ws["B5"].comment.text, "Module serial number")
        self.assertEqual(self.ws["E5"].comment.text, "Channel A indicator")
        self.assertEqual(self.ws["B5"].fill.fgColor.rgb[-6:], "305496")

    def test_cross_column_header_uses_custom_fill(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "cross.xlsx")
            columns = [x.ColumnSpec(header="[05]", kind=x.INT,
                                    header_fill=x.CROSS_HEADER_COLOR)]
            x.write_xlsx(path, columns, [("[01]", [3])], [("Version", "1.3")])
            wb = openpyxl.load_workbook(path)
            try:
                self.assertEqual(wb["Diagnostics"]["B4"].fill.fgColor.rgb[-6:],
                                 x.CROSS_HEADER_COLOR)
            finally:
                wb.close()

    def test_freeze_panes_and_autofilter(self):
        self.assertEqual(self.ws.freeze_panes, "B6")
        self.assertEqual(self.ws.auto_filter.ref, "A5:E9")

    def test_text_cell_stays_text(self):
        cell = self.ws["B6"]
        self.assertEqual(cell.value, "00A1B2C3")
        self.assertIsInstance(cell.value, str)
        self.assertEqual(cell.number_format, "@")

    def test_numbers_are_numeric(self):
        integer = self.ws["C6"]
        self.assertEqual(integer.value, 12345)
        self.assertIsInstance(integer.value, int)
        self.assertEqual(integer.number_format, "0")
        average = self.ws["D6"]
        self.assertEqual(average.value, 12.34)
        self.assertIsInstance(average.value, float)
        self.assertEqual(average.number_format, "0.00")

    def test_led_cells_are_colored(self):
        self.assertEqual(self.ws["E6"].value, 1)
        self.assertEqual(self.ws["E6"].fill.fgColor.rgb[-6:], "C6EFCE")
        self.assertEqual(self.ws["E7"].value, 7)
        self.assertEqual(self.ws["E7"].fill.fgColor.rgb[-6:], "FFC7CE")
        self.assertEqual(self.ws["E8"].value, 0)
        self.assertEqual(self.ws["E8"].fill.fgColor.rgb[-6:], "D9D9D9")
        self.assertIsNone(self.ws["E9"].value)

    def test_legend_sheet(self):
        self.assertIn("LED states", self.wb.sheetnames)
        legend = self.wb["LED states"]
        self.assertEqual(legend["A1"].value, "LED state legend")
        self.assertEqual(legend["A3"].value, "A — Channel A indicator")
        self.assertEqual(legend["A4"].value, "0 - off")
        self.assertEqual(legend["A5"].value, "1 - solid green")

    def test_columns_are_autosized(self):
        self.assertGreaterEqual(self.ws.column_dimensions["B"].width, 10)


class MapCrossRowsTest(unittest.TestCase):
    def test_maps_by_label(self):
        self.assertEqual(
            x.map_cross_rows(["[01]", "[02]", "=/="], ["[02]", "[01]", "=/="]),
            [1, 0, 2],
        )

    def test_duplicate_labels_use_occurrences(self):
        self.assertEqual(
            x.map_cross_rows(["=/=", "=/="], ["=/=", "=/=", "[01]"]),
            [0, 1],
        )

    def test_missing_label_maps_to_none(self):
        self.assertEqual(x.map_cross_rows(["[03]"], ["[01]"]), [None])
        self.assertEqual(x.map_cross_rows(["[03]", "[01]"], ["[01]"]), [None, 0])


class FormulaSafetyTest(unittest.TestCase):
    def test_text_starting_with_equals_is_not_a_formula(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "safe.xlsx")
            columns = [x.ColumnSpec(header="Type", hint="Module type", kind=x.TEXT)]
            x.write_xlsx(path, columns, [("[01]", ["=1+1"])], [("Site", "=danger")])
            wb = openpyxl.load_workbook(path)
            try:
                ws = wb["Diagnostics"]
                self.assertEqual(ws["B2"].value, "=danger")
                self.assertEqual(ws["B2"].data_type, "s")
                self.assertEqual(ws["B5"].value, "=1+1")
                self.assertEqual(ws["B5"].data_type, "s")
            finally:
                wb.close()


class WriteXlsxWithoutLegendTest(unittest.TestCase):
    def test_no_legend_sheet(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "no_legend.xlsx")
            columns = [x.ColumnSpec(header="SN", hint="Module serial number", kind=x.TEXT)]
            x.write_xlsx(path, columns, [("[01]", ["00A1"])], [("Version", "1.3")])
            wb = openpyxl.load_workbook(path)
            try:
                self.assertEqual(wb.sheetnames, ["Diagnostics"])
            finally:
                wb.close()


if __name__ == "__main__":
    unittest.main()
