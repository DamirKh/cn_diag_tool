import logging
log = logging.getLogger(__name__)
import pandas as pd
from PyQt6 import QtCore, QtGui, QtWidgets
from PyQt6.QtCore import Qt, QTimer, QEvent
from PyQt6.QtGui import QCursor

from Plc_connection_worker import PLCConnectionWorker
from form_tab2_widget_ui import Ui_FormTabWidget

import pycomm3
# from helper import MyUpdateTimer

class TableModel(QtCore.QAbstractTableModel):
    def __init__(self, data):
        super().__init__()
        self._data: pd.DataFrame = data

    def flags(self, index) -> Qt.ItemFlag:
        """Set flags for editable items."""
        # print(index.column())
        _flags = QtCore.Qt.ItemFlag.ItemIsSelectable | QtCore.Qt.ItemFlag.ItemIsEnabled
        if index.column() == 1 or index.column() == 2:  # Current value column
            pass
        else:
            _flags = _flags | QtCore.Qt.ItemFlag.ItemIsEditable

        return _flags

    def get_tags(self):
        # Get a list of tag names, excluding empty ones
        return [tag for tag in self._data['Tag Name'] if tag]

    def get_tag_value_pairs(self, column_index):
        """
        Gets a list of (tag_name, value) pairs for the specified column,
        excluding pairs where either the tag name or value is empty.

        Args:
            column_index (integer): The index of the column to retrieve values from.

        Returns:
            list: A list of tuples, where each tuple is (tag_name, value).
        """
        tag_value_pairs = []
        for row in range(self.rowCount(QtCore.QModelIndex())):
            tag_name = self._data.iloc[row, 0]
            value = self._data.iloc[row, column_index]

            # Check if both tag_name and value are non-empty
            if tag_name and value:
                try:
                    value = eval(value)
                except Exception as e:
                    log.error(f"{e}")
                    continue
                tag_value_pairs.append((tag_name, value))
        return tag_value_pairs

    def set_current_values(self, tag_list: list[pycomm3.tag]):
        for tag in tag_list:
            # Find matching tag names (can be multiple matches)
            matching_rows = self._data.index[
                self._data['Tag Name'] == tag.tag
                ].tolist()

            # Set the 'Current Value' for all matching rows
            for row in matching_rows:
                self._data.loc[row, 'Read'] = str(tag.value)
                self._data.loc[row, 'Type'] = str(tag.type)

        # Emit dataChanged signal for the entire column
        top_left = self.index(0, 1)  # Row 0, Column 1 ('Current Value')
        bottom_right = self.index(
            self.rowCount(QtCore.QModelIndex()) - 1, 2
        )
        self.dataChanged.emit(top_left, bottom_right)

    def data(self, index, role):
        if role in (Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.EditRole):
            value = self._data.iloc[index.row(), index.column()]
            return str(value)
        if role == Qt.ItemDataRole.DecorationRole:
            value = self._data.iloc[index.row(), index.column()]
            if value =='None':
                return QtGui.QColor('red')
            if index.column()>2 and value:
                try:
                    t = eval(value)
                    if isinstance(t, str):
                        return QtGui.QColor('yellow')
                    return
                except Exception:
                    return QtGui.QColor('red')

    def setData(self, index, value, role=Qt.ItemDataRole.EditRole):
        """Save data when edited."""
        if role == Qt.ItemDataRole.EditRole:
            # Save the edited value to your DataFrame
            row = index.row()
            col = index.column()
            self._data.iloc[row, col] = value
            self.dataChanged.emit(index, index)  # Notify view of change
            return True
        return False

    def headerData(self, section, orientation, role):
        if role == Qt.ItemDataRole.DisplayRole:
            if orientation == Qt.Orientation.Horizontal:
                return str(self._data.columns[section])

        if orientation == Qt.Orientation.Vertical:
            return str(self._data.index[section])

    def rowCount(self, index):
        return self._data.shape[0]

    def columnCount(self, index):
        return self._data.shape[1]

    def add_new_column(self, index=None):
        if index is None:
            index = self.columnCount(QtCore.QModelIndex())
        new_column_name = f"Set {index-2}"
        self._data.insert(index, new_column_name, "")
        self.layoutChanged.emit()

    def add_new_row(self):
        row_count = self.rowCount(QtCore.QModelIndex())
        self._data.loc[row_count] = ''
        self.layoutChanged.emit()


class FormTabWidget(QtWidgets.QWidget, Ui_FormTabWidget):
    empty_row_data = ['', '', '', '']
    new_table_columns = [
        'Tag Name',
        'Type',
        'Read',
        'Set',
    ]

    def __init__(self, worker: PLCConnectionWorker, timer, data=None):
        super().__init__()
        self._worker = worker
        self._timer = timer
        self._worker.signals.read_done.connect(self.update_from_worker)
        self.setupUi(self)

        my_data_row = data or self.empty_row_data.copy()

        data = pd.DataFrame(
            [
                my_data_row,
            ],
            columns=self.new_table_columns.copy()
        )

        # self.tableView = MyTableView(self)
        self.tableView.horizontalHeader().setSectionsClickable(True)
        self.tableView.horizontalHeader().sectionClicked.connect(self.on_header_clicked)
        self.tableView.horizontalHeader().sectionResized.connect(self.column_resized)

        self.model = TableModel(data)
        self.tableView.setModel(self.model)
        self._visible = False
        self._control_pressed = False

        self.connectSignalsSlots()

    def connectSignalsSlots(self):
        # Connect signals for Control key press
        self.tableView.installEventFilter(self)  # Install event filter
        self.pushButtonPlusColumn.clicked.connect(self.add_new_column)
        self.pushButtonPlusRow.clicked.connect(self.add_new_row)
        self.checkBoxRead.stateChanged.connect(self.on_checkbox_checked)

        # Create a timer for periodic updates
        self.update_timer = QTimer(self)
        self.update_timer.setInterval(self._timer.value)
        self.update_timer.timeout.connect(self.read_tag_values_from_PLC_command)


    def get_table_data(self):
        """
        Retrieves the tag data from the table as a list of lists.

        Returns:
            list: A list of lists, where each inner list represents a row
                  in the table, and each element in the inner list is a string
                  value from the corresponding cell.
        """

        tag_data = []  # Initialize as an empty list
        for row in range(self.model.rowCount(QtCore.QModelIndex())):
            row_data = []
            for col in range(self.model.columnCount(QtCore.QModelIndex())):
                cell_value = self.model.data(self.model.index(row, col), Qt.ItemDataRole.DisplayRole)
                row_data.append(cell_value)
            tag_data.append(row_data)
        return tag_data

    def you_are_visible(self, visible):
        self._visible = visible
        if visible:
            # print("I'm visible")
            self.on_checkbox_checked(self.checkBoxRead.checkState().value)
        else:
            self.on_checkbox_checked(QtCore.Qt.CheckState.Unchecked.value)

    def on_checkbox_checked(self, state):
        if state == QtCore.Qt.CheckState.Checked.value:
            log.debug("Start periodically reading")
            self.update_timer.start()  # Start the timer when checked
            self.update_timer.singleShot(10, self.read_tag_values_from_PLC_command)
        else:
            log.debug("Stop periodically reading")
            self.update_timer.stop()   # Stop the timer when unchecked

    def on_header_clicked(self, logicalIndex):
        """Handle clicks on header labels."""
        match logicalIndex:
            case 0:
                pass
                # print(f"Clicked on Tag Name")
            case 1:
                # Tag's type
                pass
            case 2:
                # print(f"Read data")
                self.read_tag_values_from_PLC_command()
            case _:
                # print(f"Write data column {logicalIndex}")
                if self._control_pressed:
                    self.download_to_plc(logicalIndex)

    def eventFilter(self, obj, event):
        if obj == self.tableView and event.type() == QEvent.Type.KeyPress:
            if event.key() == Qt.Key.Key_Control:
                self._control_pressed = True
                # print('CTRL+')
                self.setCursor(Qt.CursorShape.PointingHandCursor)  # Change cursor to pointing hand
                return True  # Consume the event
        elif obj == self.tableView and event.type() == QEvent.Type.KeyRelease:
            if event.key() == Qt.Key.Key_Control:
                self._control_pressed = False
                # print('CTRL-')
                self.setCursor(Qt.CursorShape.ArrowCursor)  # Change cursor back to arrow
                return True  # Consume the event
        return super().eventFilter(obj, event)

    def download_to_plc(self, logical_index):
        """Write tags to PLC"""
        if self._worker.pooling:
            tags_to_write = self.model.get_tag_value_pairs(logical_index)
            log.debug(f"Write {len(tags_to_write)} tags to PLC")
            self._worker.write_tags = tags_to_write


    def column_resized(self, index, old_size, new_size):
        pass

    def add_new_row(self):
        self.model.add_new_row()

    def add_new_column(self):
        self.model.add_new_column()

    def read_tag_values_from_PLC_command(self):
        if self._worker.pooling:
            self.update_timer.setInterval(self._timer.value)
            _tags = self.model.get_tags()
            self._worker.read_tags = _tags

    def update_from_worker(self, tags_list):
        if not self._visible:
            return
        log.debug(f"Update {len(tags_list)} values from PLC")
        self.model.set_current_values(tags_list)
