import datetime
import subprocess
import logging
import os
import re
import sys
import time

import json
from fileinput import filename

from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QCoreApplication, QT_TRANSLATE_NOOP
from PyQt6.QtCore import QSettings
from PyQt6.QtGui import QCursor, QColor, QBrush, QFont
from PyQt6 import QtWidgets, QtCore, QtGui
from PyQt6.QtWidgets import QMainWindow, QApplication, QProgressDialog, QVBoxLayout, QMessageBox, QLabel, QDialog, \
    QWidget, QTableWidgetItem, QTableWidget, QGridLayout, QGroupBox, QCheckBox, QLineEdit, QDialogButtonBox, \
    QHeaderView, QFileDialog, QButtonGroup

import user_data
import ver
import i18n

#https://stackoverflow.com/a/66104687/8124158
QtCore.QDir.addSearchPath('asset', user_data.asset_dir)

from cn_diag_tool_ui import Ui_MainWindow
from cndt_config_dialog import Ui_Dialog
from Plc_connection_worker import PLCConnectionWorker
from cn_lib import scan_cn
from pycomm3.exceptions import CommError, RequestError

import floating_table_ui



# from DragTable import DraggableTableWidget

logging.basicConfig(
    stream=sys.stdout,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.DEBUG
)

MEDIA_CONVERTER = '=/='
RED = QColor('red')
GREEN = QColor('green')
GREY = QColor('grey')
YELLOW = QColor('yellow')
LED_blink_period = 300  # msec
TICK_TACK = False
My_ROLE = QtCore.Qt.ItemDataRole.UserRole + 1
HOR_HEADER_FONT = QFont()


class HeaderData(object):
    def __init__(self, sid: str, comment: str = '', hint: str = '', longread: str = '', size: int = None, woc: bool = False):
        self.sid = sid
        self.comment = comment
        self.hint = hint
        self.longread = longread
        self.size = size
        self.woc = woc  # warning on change


LABELS = [
    HeaderData('Serial',
               comment=QT_TRANSLATE_NOOP("LABELS", "SN"),
               hint=QT_TRANSLATE_NOOP("LABELS", "Module serial number"),
               longread=QT_TRANSLATE_NOOP("LABELS", "Module serial number (8 hex digits)."),
               woc=True,
               ),
     HeaderData('Name',
                comment=QT_TRANSLATE_NOOP("LABELS", "Type"),
                hint=QT_TRANSLATE_NOOP("LABELS", "Module type"),
                longread=QT_TRANSLATE_NOOP("LABELS", "Module catalog type/number (e.g. 1756-CNB)."),
                woc=True,
                ),
    HeaderData('Rev',
               comment=QT_TRANSLATE_NOOP("LABELS", "Rev"),
               hint=QT_TRANSLATE_NOOP("LABELS", "Revision"),
               longread=QT_TRANSLATE_NOOP("LABELS", "Module firmware revision, major.minor."),
               woc=True,
               ),
    HeaderData('reply_time',
               comment=QT_TRANSLATE_NOOP("LABELS", "Reply"),
               hint=QT_TRANSLATE_NOOP("LABELS", "Response time, us"),
               longread=QT_TRANSLATE_NOOP("LABELS", "Response time to a diagnostic request, microseconds.\nIncludes overhead, so it is approximate and not very informative."),
               ),
    HeaderData('LED_A',
               comment=QT_TRANSLATE_NOOP("LABELS", "A"),
               hint=QT_TRANSLATE_NOOP("LABELS", "Channel A indicator"),
               longread=QT_TRANSLATE_NOOP("LABELS", "Channel A indicator state (values 0-7):\n0 - off; 1 - solid green; 2 - flashing green;\n3 - flashing red; 4 - red+green;\n5 - railroad red; 6 - railroad red+green; 7 - solid red.\nStates with no link to the module cannot be shown."),
               ),
    HeaderData('LED_B',
               comment=QT_TRANSLATE_NOOP("LABELS", "B"),
               hint=QT_TRANSLATE_NOOP("LABELS", "Channel B indicator"),
               longread=QT_TRANSLATE_NOOP("LABELS", "Channel B indicator state (values 0-7):\n0 - off; 1 - solid green; 2 - flashing green;\n3 - flashing red; 4 - red+green;\n5 - railroad red; 6 - railroad red+green; 7 - solid red.\nStates with no link to the module cannot be shown."),
               ),
    HeaderData('channel_A_frame_error',
               comment=QT_TRANSLATE_NOOP("LABELS", "A err"),
               hint=QT_TRANSLATE_NOOP("LABELS", "Channel A framing errors"),
               longread=QT_TRANSLATE_NOOP("LABELS", "Frames received on channel A with a framing error.\nWidth: 8 bits.\nIndicates a channel A physical-layer problem - cable, connector, terminator, noise."),
               woc=True,
               ),
    HeaderData('channel_A_frame_error/s',
               comment=QT_TRANSLATE_NOOP("LABELS", "A err/s"),
               hint=QT_TRANSLATE_NOOP("LABELS", "Channel A errors per second"),
               longread=QT_TRANSLATE_NOOP("LABELS", "Increment of the channel A error counter over the last second."),
               ),
    HeaderData('channel_B_frame_error',
               comment=QT_TRANSLATE_NOOP("LABELS", "B err"),
               hint=QT_TRANSLATE_NOOP("LABELS", "Channel B framing errors"),
               longread=QT_TRANSLATE_NOOP("LABELS", "Frames received on channel B with a framing error.\nWidth: 8 bits.\nIndicates a channel B physical-layer problem - cable, connector, terminator, noise."),
               woc=True,
               ),
    HeaderData('channel_B_frame_error/s',
               comment=QT_TRANSLATE_NOOP("LABELS", "B err/s"),
               hint=QT_TRANSLATE_NOOP("LABELS", "Channel B errors per second"),
               longread=QT_TRANSLATE_NOOP("LABELS", "Increment of the channel B error counter over the last second."),
               ),
    HeaderData('selected_channel_frame_error',
               comment=QT_TRANSLATE_NOOP("LABELS", "Err"),
               hint=QT_TRANSLATE_NOOP("LABELS", "Active channel errors"),
               longread=QT_TRANSLATE_NOOP("LABELS", "Frames received on the active (selected) channel with a framing error.\nWidth: 8 bits.\nIndicates a physical-layer problem on the current active channel."),
               woc=True,
               ),
    HeaderData('selected_channel_frame_error/s',
               comment=QT_TRANSLATE_NOOP("LABELS", "Err/s"),
               hint=QT_TRANSLATE_NOOP("LABELS", "Active channel errors per second"),
               longread=QT_TRANSLATE_NOOP("LABELS", "Increment of the active-channel error counter over the last second."),
               ),
    HeaderData('Active_Channel',
               comment=QT_TRANSLATE_NOOP("LABELS", "Act."),
               hint=QT_TRANSLATE_NOOP("LABELS", "Active channel"),
               longread=QT_TRANSLATE_NOOP("LABELS", "Channel selected as active for reception: A or B."),
               ),
    HeaderData('Redundancy_Warning',
               comment=QT_TRANSLATE_NOOP("LABELS", "Redund."),
               hint=QT_TRANSLATE_NOOP("LABELS", "Redundancy lost"),
               longread=QT_TRANSLATE_NOOP("LABELS", "Redundancy loss flag.\nActive when the backup channel/network is unavailable."),
               ),
    HeaderData('good_frames_transmitted',
               comment=QT_TRANSLATE_NOOP("LABELS", "⇑"),
               hint=QT_TRANSLATE_NOOP("LABELS", "Good frames transmitted"),
               longread=QT_TRANSLATE_NOOP("LABELS", "Successfully transmitted frames (Good Tx).\nWidth: 24 bits.\nThe «⇑/s» column is more informative."),
               ),
    HeaderData('good_frames_transmitted/s',
               comment=QT_TRANSLATE_NOOP("LABELS", "⇑/s"),
               hint=QT_TRANSLATE_NOOP("LABELS", "Transmitted frames/s"),
               longread=QT_TRANSLATE_NOOP("LABELS", "Increment of the good-transmit counter over the last second."),
               ),
    HeaderData('good_frames_transmitted_avg',
               comment=QT_TRANSLATE_NOOP("LABELS", "⇑ avg"),
               hint=QT_TRANSLATE_NOOP("LABELS", "Average TX/s since scan start"),
               longread=QT_TRANSLATE_NOOP("LABELS", "Average number of successfully transmitted frames per second since the scan started.\nThe 24-bit counter wrap is taken into account."),
               ),
    HeaderData('aborted_frame_transmitted',
               comment=QT_TRANSLATE_NOOP("LABELS", "⇞"),
               hint=QT_TRANSLATE_NOOP("LABELS", "Transmit abort"),
               longread=QT_TRANSLATE_NOOP("LABELS", "Transmit abort counter (Tx-Abort): a packet was aborted because the module could not feed data onto the wire fast enough.\nWidth: 8 bits.\nIndicates module overload or a physical-layer problem."),
               woc=True,
               ),
    HeaderData('good_frames_received',
               comment=QT_TRANSLATE_NOOP("LABELS", "⇓"),
               hint=QT_TRANSLATE_NOOP("LABELS", "Good frames received"),
               longread=QT_TRANSLATE_NOOP("LABELS", "Successfully received frames (Good Rx).\nWidth: 24 bits.\nThe «⇓/s» column is more informative."),
               ),
    HeaderData('good_frames_received/s',
               comment=QT_TRANSLATE_NOOP("LABELS", "⇓/s"),
               hint=QT_TRANSLATE_NOOP("LABELS", "Received frames/s"),
               longread=QT_TRANSLATE_NOOP("LABELS", "Increment of the good-receive counter over the last second."),
               ),
    HeaderData('good_frames_received_avg',
               comment=QT_TRANSLATE_NOOP("LABELS", "⇓ avg"),
               hint=QT_TRANSLATE_NOOP("LABELS", "Average RX/s since scan start"),
               longread=QT_TRANSLATE_NOOP("LABELS", "Average number of successfully received frames per second since the scan started.\nThe 24-bit counter wrap is taken into account."),
               ),
    HeaderData('aborted_frames_received',
               comment=QT_TRANSLATE_NOOP("LABELS", "⇟"),
               hint=QT_TRANSLATE_NOOP("LABELS", "Receive abort"),
               longread=QT_TRANSLATE_NOOP("LABELS", "Receive abort counter (Rx-Abort): reception of a packet from the wire was aborted.\nWidth: 8 bits."),
               ),
    HeaderData('noise_hits',
               comment=QT_TRANSLATE_NOOP("LABELS", "∿"),
               hint=QT_TRANSLATE_NOOP("LABELS", "Noise hits"),
               longread=QT_TRANSLATE_NOOP("LABELS", "Noise-hit counter: the start of a frame could not be detected because of noise.\nWidth: 8 bits.\nIndicates signal quality; growth means electromagnetic interference (grounding, shielding, cable routing)."),
               woc=True,
               ),
    HeaderData('noise_hits/s',
               comment=QT_TRANSLATE_NOOP("LABELS", "∿/s"),
               hint=QT_TRANSLATE_NOOP("LABELS", "Noise hits/s"),
               longread=QT_TRANSLATE_NOOP("LABELS", "Increment of the noise-hit counter over the last second."),
               ),
    HeaderData('collisions',
               comment=QT_TRANSLATE_NOOP("LABELS", "⇆"),
               hint=QT_TRANSLATE_NOOP("LABELS", "Collisions"),
               longread=QT_TRANSLATE_NOOP("LABELS", "Collision counter: the node tried to transmit while the channel was already busy with another node.\nWidth: 8 bits.\nIn a CTDMA network the norm is close to zero; growth means noise, interference or misconfiguration."),
               woc=True,
               ),
    HeaderData('collisions/s',
               comment=QT_TRANSLATE_NOOP("LABELS", "⇆/s"),
               hint=QT_TRANSLATE_NOOP("LABELS", "Collisions/s"),
               longread=QT_TRANSLATE_NOOP("LABELS", "Increment of the collision counter over the last second."),
               ),
    HeaderData('highwaters',
               comment=QT_TRANSLATE_NOOP("LABELS", "OVRL"),
               hint=QT_TRANSLATE_NOOP("LABELS", "LLC buffer overflow"),
               longread=QT_TRANSLATE_NOOP("LABELS", "LLC buffer overflow/starvation: transmit underflow, receive overflow.\nWidth: 8 bits.\nIndicates receive buffers are full or transmission cannot keep up."),
               woc=True,
               ),
    HeaderData('nut_overloads',
               comment=QT_TRANSLATE_NOOP("LABELS", "NUT\nOVRL"),
               hint=QT_TRANSLATE_NOOP("LABELS", "NUT overload"),
               longread=QT_TRANSLATE_NOOP("LABELS", "Number of NUTs with no time left for the unscheduled part.\nWidth: 8 bits.\nIndicates the NUT is too small or the schedule is overloaded."),
               ),
    HeaderData('nut_overloads/s',
               comment=QT_TRANSLATE_NOOP("LABELS", "NUT\nOVRL/c"),
               hint=QT_TRANSLATE_NOOP("LABELS", "NUT overload/s"),
               longread=QT_TRANSLATE_NOOP("LABELS", "Increment of the NUT-overload counter over the last second."),
               woc=True,
               ),
    HeaderData('slot_overloads',
               comment=QT_TRANSLATE_NOOP("LABELS", "SLOT\nOVRL"),
               hint=QT_TRANSLATE_NOOP("LABELS", "Slot overload"),
               longread=QT_TRANSLATE_NOOP("LABELS", "Scheduled-slot overload: more scheduled data was queued for one NUT than SchedMaxFrame allows.\nWidth: 8 bits."),
               woc=True,
               ),
    HeaderData('slot_overloads/s',
               comment=QT_TRANSLATE_NOOP("LABELS", "SLOT\nOVRL/s"),
               hint=QT_TRANSLATE_NOOP("LABELS", "Slot overload/s"),
               longread=QT_TRANSLATE_NOOP("LABELS", "Increment of the scheduled-slot overload counter over the last second."),
               ),
    HeaderData('blockages',
               comment=QT_TRANSLATE_NOOP("LABELS", "BLOCK"),
               hint=QT_TRANSLATE_NOOP("LABELS", "Transmit blockage"),
               longread=QT_TRANSLATE_NOOP("LABELS", "Transmit blockage: a single L-packet exceeds SchedMaxFrame and does not fit into the allowed transmit time.\nWidth: 8 bits."),
               woc=True,
               ),
    HeaderData('blockages/s',
               comment=QT_TRANSLATE_NOOP("LABELS", "BLOCK\n    /s"),
               hint=QT_TRANSLATE_NOOP("LABELS", "Blockage/s"),
               longread=QT_TRANSLATE_NOOP("LABELS", "Increment of the transmit-blockage counter over the last second."),
               ),
    HeaderData('non_concurrence',
               comment=QT_TRANSLATE_NOOP("LABELS", "NON\nCNCR"),
               hint=QT_TRANSLATE_NOOP("LABELS", "Non-concurrence"),
               longread=QT_TRANSLATE_NOOP("LABELS", "Non-concurrence: two or more nodes could not agree whose turn it is to transmit (mismatch of transmitted/received message counts).\nWidth: 8 bits."),
               woc=True,
               ),
    HeaderData('non_concurrence/s',
               comment=QT_TRANSLATE_NOOP("LABELS", "NON\nCNCR/s"),
               hint=QT_TRANSLATE_NOOP("LABELS", "Non-concurrence/s"),
               longread=QT_TRANSLATE_NOOP("LABELS", "Increment of the non-concurrence counter over the last second."),
               ),
    HeaderData('lonely_counter',
               comment=QT_TRANSLATE_NOOP("LABELS", "LNLY"),
               hint=QT_TRANSLATE_NOOP("LABELS", "Moderator timeouts"),
               longread=QT_TRANSLATE_NOOP("LABELS", "Number of timeouts waiting for the moderator: the node heard nothing from the network for 8 or more NUTs.\nWidth: 8 bits.\nIndicates a lonely network, a break, or a missing moderator."),
               woc=True,
               ),
    HeaderData('duplicate_node',
               comment=QT_TRANSLATE_NOOP("LABELS", "DUP"),
               hint=QT_TRANSLATE_NOOP("LABELS", "Duplicate address"),
               longread=QT_TRANSLATE_NOOP("LABELS", "Another node with the same MAC ID was detected (address conflict).\nWidth: 8 bits.\nThe norm is 0; a non-zero value means two devices share one address."),
               woc=True,
               ),
    HeaderData('mod_mac_id',
               comment=QT_TRANSLATE_NOOP("LABELS", "MOD\nMAC"),
               hint=QT_TRANSLATE_NOOP("LABELS", "Moderator MAC ID"),
               longread=QT_TRANSLATE_NOOP("LABELS", "MAC ID of the current moderator node (lowest address on the network).\nInformational value, not an error counter."),
               ),
    HeaderData('non_lowman_mods',
               comment=QT_TRANSLATE_NOOP("LABELS", "nLOW\nmods"),
               hint=QT_TRANSLATE_NOOP("LABELS", "Non-lowman frames"),
               longread=QT_TRANSLATE_NOOP("LABELS", "Number of moderator frames received from nodes with different network parameters (non-lowman) - network parameter mismatch events.\nWidth: 8 bits."),
               woc=True,
               ),
    HeaderData('rogue_count',
               comment=QT_TRANSLATE_NOOP("LABELS", "ROG"),
               hint=QT_TRANSLATE_NOOP("LABELS", "Rogue events"),
               longread=QT_TRANSLATE_NOOP("LABELS", "Rogue events: nodes transmitting outside the schedule or incorrectly.\nWidth: 8 bits.\nIndicates a network problem."),
               woc=True,
               ),
]

# sid -> logical column index (column order is fixed by LABELS; only visual order changes)
COLUMN_INDEX = {label.sid: index for index, label in enumerate(LABELS)}

# text columns stay left-aligned, all other (numeric) columns are right-aligned
TEXT_SIDS = {'Serial', 'Name', 'Rev', 'Active_Channel', 'Redundancy_Warning'}


def alignment_for_sid(sid: str):
    """Left alignment for text columns, right alignment for numeric ones."""
    horizontal = Qt.AlignmentFlag.AlignLeft if sid in TEXT_SIDS else Qt.AlignmentFlag.AlignRight
    return horizontal | Qt.AlignmentFlag.AlignVCenter


def data_item(sid: str, text: str) -> QTableWidgetItem:
    """Creates a table cell with alignment based on the column type."""
    item = QTableWidgetItem(text)
    item.setTextAlignment(alignment_for_sid(sid))
    return item


def tr_label(text: str) -> str:
    """Translates a LABELS string (the list is built before the translator exists)."""
    return QCoreApplication.translate("LABELS", text)


# ControlNet base path: "<address>/bp/<slot>/..." (address is IPv4 or a hostname)
_CN_PATH_START = re.compile(r'^[A-Za-z0-9.-]+/bp/\d+/', re.IGNORECASE)

CN_PATH_HELP = QT_TRANSLATE_NOOP("PathHelp",
    "<b>ControlNet path format</b><br><br>"
    "<code>&lt;address&gt;/bp/&lt;slot&gt;/cnet</code> - base path: the controller address and the "
    "backplane slot holding the ControlNet module.<br>"
    "<code>/&lt;node&gt;/bp/&lt;slot&gt;/cnet</code> - an extra hop for a chain of ControlNet "
    "networks (the node the bridge sits on).<br><br>"
    "The path always ends with <code>/cnet</code>; the program appends node numbers itself.<br>"
    "The address is an IPv4 or a host name.<br><br>"
    "<b>Examples:</b><br>"
    "<code>11.120.20.129/bp/5/cnet/1/bp/2/cnet/2/bp/2/cnet/2/bp/2/cnet</code><br>"
    "<code>11.120.20.129/bp/5/cnet/1/bp/2/cnet/2/bp/2/cnet</code>"
)


def validate_cn_path(path: str):
    """Validates a ControlNet base path; returns (ok, error_message)."""
    p = (path or '').strip()
    if not p:
        return False, QCoreApplication.translate("Path", 'Path is empty')
    if not _CN_PATH_START.match(p):
        return False, QCoreApplication.translate("Path", 'Path must start with <address>/bp/<number>/')
    if not p.lower().endswith('/cnet'):
        return False, QCoreApplication.translate("Path", 'Path must end with /cnet')
    return True, ''


class GeometrySaver(QWidget):
    def geometry_saver_init(self, settings_key: str):
        self.geometry_saver_settings = Glob_settings
        self._geometry_settings_key = settings_key
        self.restore_geometry()
        # QDialog closes through done() (accept/reject), which does not emit closeEvent,
        # so also persist on the finished signal when available.
        finished = getattr(self, 'finished', None)
        if finished is not None:
            finished.connect(self._save_geometry_on_finish)

    def _save_geometry_on_finish(self, _result=None):
        self.save_geometry()

    def save_geometry(self):
        if self._geometry_settings_key:
            self.geometry_saver_settings.setValue(self._geometry_settings_key, self.saveGeometry())
            log.debug(f'Geometry {self._geometry_settings_key} saved')

    def restore_geometry(self):
        if self._geometry_settings_key:
            geometry = self.geometry_saver_settings.value(self._geometry_settings_key)
            if geometry is not None:
                try:
                    self.restoreGeometry(geometry)
                    log.debug(f'Geometry {self._geometry_settings_key} restored')
                except TypeError as e:
                    log.error(f"Error restoring geometry: {e}")
            else:
                log.debug(f'No geometry settings found for {self._geometry_settings_key}')

    def closeEvent(self, event):  # Override closeEvent if not using a main window.
        self.save_geometry()
        super().closeEvent(event)


class ConfigureDialog(QDialog, GeometrySaver):
    filterChanged = QtCore.pyqtSignal(int, str)  # Define the signal

    def __init__(self, table_widget: QTableWidget, parent=None):
        super().__init__(parent)
        self.setWindowTitle(self.tr("Configure Data View"))
        self.tableWidget = table_widget

        # Use a QTableWidget for the configuration options
        self.configTable = QTableWidget(0, 3, self)  # 0 rows initially, 3 columns
        self.configTable.setHorizontalHeaderLabels(
            [self.tr("Column Name"), self.tr("Description"), self.tr("Visibility")])
        header = self.configTable.horizontalHeader()
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)  # Stretch column Hint
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)  # Fit checkbox

        try:
            for col in range(self.tableWidget.columnCount()):
                header_item = self.tableWidget.horizontalHeaderItem(col)
                if not header_item or not header_item.text():
                    continue  # do not configure the column without header or text in header
                header_data:HeaderData = header_item.data(My_ROLE)
                column_name = header_item.text()

                row = self.configTable.rowCount()
                self.configTable.insertRow(row)

                name_item = QTableWidgetItem(column_name)
                name_item.setFlags(name_item.flags() & ~QtCore.Qt.ItemFlag.ItemIsEditable)  # Make name read-only
                self.configTable.setItem(row, 0, name_item)

                hint = QTableWidgetItem(tr_label(header_data.hint))
                hint.setToolTip(tr_label(header_data.longread))
                self.configTable.setItem(row, 1, hint)

                check_box = QtWidgets.QCheckBox()
                check_box.setChecked(not self.tableWidget.isColumnHidden(col))
                check_box.stateChanged.connect(lambda state, col=col: self.toggle_column_visibility(col, state))
                self.configTable.setCellWidget(row, 2, check_box)

        except IndexError as e:
            QMessageBox.critical(self, self.tr("Error"), str(e))
            raise  # Reraise for external handling

        # Layout
        main_layout = QtWidgets.QVBoxLayout(self)  # Use a QVBoxLayout
        main_layout.addWidget(self.configTable)  # Add the table to the layout

        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        main_layout.addWidget(button_box)
        self.geometry_saver_init(settings_key="ConfigDialog")

    def toggle_column_visibility(self, column_index, state):
        if state == 2:  # Checked (Qt.CheckState.Checked is 2)
            self.tableWidget.setColumnHidden(column_index, False)
        elif state == 0:  # Unchecked (Qt.CheckState.Unchecked is 0)
            self.tableWidget.setColumnHidden(column_index, True)


class QTextEditLogger(logging.Handler, QtCore.QObject):
    appendPlainText = QtCore.pyqtSignal(str)

    def __init__(self, parent):
        super().__init__()
        QtCore.QObject.__init__(self)
        self.widget = QtWidgets.QPlainTextEdit(parent)
        self.widget.setReadOnly(True)
        self.appendPlainText.connect(self.widget.appendPlainText)

    def emit(self, record):
        msg = self.format(record)
        self.appendPlainText.emit(msg)


class StatusBarLogger(logging.Handler, QtCore.QObject):
    updateStatusBar = QtCore.pyqtSignal(str)

    def __init__(self, statusbar, level = logging.INFO):
        logging.Handler.__init__(self, level)
        QtCore.QObject.__init__(self)
        self.statusbar = statusbar
        self.updateStatusBar.connect(self.statusbar.showMessage)

    def emit(self, record):
        msg = self.format(record)
        self.updateStatusBar.emit(msg)


class Header_Item_NodeNum(QTableWidgetItem):
    def __init__(self, node_num: int, *args, **kwargs):
        color = QColor('yellow')
        super().__init__(*args, **kwargs)
        assert 0 < node_num < 100
        self.setText(f'[{node_num:02}]')
        # self.setBackground(QBrush(color))
        self.setData(Qt.ItemDataRole.UserRole, node_num)


class Item_Placeholder(QTableWidgetItem):
    def __init__(self, *args, **kwargs):
        color = QColor('peru')
        super().__init__(*args, **kwargs)
        self.setBackground(QBrush(color))


class CrossTableDialog(QDialog, floating_table_ui.Ui_Dialog, GeometrySaver):
    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self.setWindowTitle(self.tr("Bad Frame Cross Table"))

        self.setupUi(self)
        self.connectSignalsSlots()
        self.geometry_saver_init(settings_key="CrossTableDialog")
        # node number -> columns currently showing a complaint count (for clearing stale cells)
        self._complaint_cols = {}
        self.hide()

    def connectSignalsSlots(self):
        pass

    def fill_table(self, from_table: QTableWidget):
        log.debug('Fill crosstable')
        self.tableWidget.clear()
        self._complaint_cols = {}
        rows = from_table.rowCount()
        self.tableWidget.setRowCount(rows)
        self.tableWidget.setColumnCount(rows)
        for row in range(rows):
            visual_index = from_table.verticalHeader().visualIndex(row)
            V_item = QTableWidgetItem(from_table.verticalHeaderItem(row).text())
            H_item = QTableWidgetItem(from_table.verticalHeaderItem(row).text())
            self.tableWidget.setColumnWidth(row, 15)
            self.tableWidget.setVerticalHeaderItem(visual_index, V_item)
            self.tableWidget.setHorizontalHeaderItem(visual_index, H_item)
            if V_item.text() == MEDIA_CONVERTER:
                placeholder = Item_Placeholder()
                for c in range(self.tableWidget.columnCount()):
                    self.tableWidget.setItem(visual_index, c, placeholder.clone())
                    self.tableWidget.setItem(c, visual_index, placeholder.clone())

    def update_diag_data(self, node_num, diag_data: dict):
        """Updates diagnostics in the crosstable for the specified node.

        Each node has an 8-byte error log (#err_0..#err_7); every non-zero byte holds the
        number of a node this node "complains" about. The same target may appear in several
        bytes, so the cell shows how many complaints point to that node.

        Args:
            node_num: The node number to update.
            diag_data: A dictionary where keys correspond to column header labels
                       and values are the data to be displayed.
        """
        source_text = f'[{node_num:02}]'
        row = None
        for r in range(self.tableWidget.rowCount()):
            item = self.tableWidget.verticalHeaderItem(r)
            if item and item.text() == source_text:
                row = r
                break
        if row is None:
            return

        # count complaints per target node number
        counts = {}
        for key, value in diag_data.items():
            if isinstance(key, str) and key.startswith('#err_') and value:
                counts[value] = counts.get(value, 0) + 1

        columns = {}
        for col in range(self.tableWidget.columnCount()):
            header_item = self.tableWidget.horizontalHeaderItem(col)
            if header_item:
                columns[header_item.text()] = col

        shown_cols = set()
        for target_num, count in counts.items():
            col = columns.get(f'[{target_num:02}]')
            if col is None:
                continue
            item = QTableWidgetItem(str(count))
            item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            item.setData(Qt.ItemDataRole.DecorationRole, YELLOW if target_num == node_num else RED)
            self.tableWidget.setItem(row, col, item)
            shown_cols.add(col)

        # clear cells that no longer have a complaint
        for col in self._complaint_cols.get(node_num, set()) - shown_cols:
            self.tableWidget.setItem(row, col, QTableWidgetItem(''))
        self._complaint_cols[node_num] = shown_cols


class LogWindow(QDialog, GeometrySaver):
    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self.setWindowTitle(self.tr("Log Viewer"))
        self.logTextBox = QTextEditLogger(self)
        # log to text box
        self.logTextBox.setFormatter(
            logging.Formatter(
                '%(asctime)s %(levelname)s %(module)s %(funcName)s %(message)s'))
        logging.getLogger().addHandler(self.logTextBox)
        logging.getLogger().setLevel(logging.INFO)

        # Create a layout
        layout = QVBoxLayout()
        layout.addWidget(self.logTextBox.widget)
        self.setLayout(layout)
        self.geometry_saver_init(settings_key="LogWindowGeometry")
        self.hide()


class HelperConfigDialog(QDialog, Ui_Dialog):
    def __init__(self, callback, timer_value, confirmation, parent=None):
        super().__init__(parent)
        self.setupUi(self)
        self._callback = callback
        self.connectSignalsSlots()
        self.spinBox.setValue(timer_value)
        self.checkBox.setChecked(confirmation)

    def connectSignalsSlots(self):
        self.spinBox.valueChanged.connect(self._callback)


class DiagWindow(QMainWindow, Ui_MainWindow):
    labels = [l.sid for l in LABELS]

    def __init__(self, config_file_path, parent=None):
        super().__init__(parent)
        self._reset_enabled = False
        self.setupUi(self)
        self.statusbar.showMessage("Start application")

        self.my_status_updater = StatusBarLogger(self.statusbar)
        self.my_status_updater.setFormatter(
            logging.Formatter('%(message)s')
        )
        logging.getLogger().addHandler(self.my_status_updater)

        # self.tableWidget = DraggableTableWidget(parent=self.centralwidget)
        # self.tableWidget.setObjectName("tableWidget")

        self.logger_window = LogWindow(self)
        self.MyCrossTable = CrossTableDialog(parent=self)
        self.connectSignalsSlots()
        self._app_config_file_path = config_file_path
        self._config_file_path = None
        self._confirm_on_close = True
        self._site_changed = False
        self._restarting = False
        self._saved_snapshot = self._snapshot()  # baseline for "unsaved changes" checks
        self._prev_update_time = time.monotonic_ns()

        self._app: QtWidgets.QApplication = QtWidgets.QApplication.instance()
        # creating a label widget for status bar
        self.status_bar_label_1 = QLabel("Not connected yet")

        self.status_bar_label_1.setStyleSheet("border :1px solid blue;")
        # adding label to status bar
        self.statusBar().addPermanentWidget(self.status_bar_label_1)

        self._workers = {}
        self._retired_workers = []
        self._site_loaded = False
        self._paused = False

        # Create a timer for periodic LED blinkers
        self.led_blink_timer = QTimer(self)
        self.led_blink_timer.setSingleShot(False)
        self.led_blink_timer.setInterval(300)
        self.led_blink_timer.timeout.connect(self.led_blinker)
        self.load_app_config()
        self.tableWidget._config_file = user_data.get_user_data_path() / 'main_table.json'

        try:
            with open(os.path.join(user_data.basedir, 'changelog.txt'), encoding='utf-8') as chlog:
                self.changelog = chlog.read()
        except OSError as e:
            log.warning(f'changelog.txt not found: {e}')
            self.changelog = ''


    @property
    def config_file_path(self):
        return self._config_file_path

    @config_file_path.setter
    def config_file_path(self, value: str):
        self._config_file_path = value
        self.setWindowTitle(self.tr("ControlNet diagnostic tool") + f"  {value}")

    def non_fatal(self, message):
        self.statusBar().showMessage(message, 10000)

    def _build_site_config(self):
        """Collects the current site state (same structure as the saved JSON)."""
        config = {'CN': {'path': self.lineEditConnectionPath.text()}}

        # rows in visual (top-to-bottom) order: node "[NN]" or media converter "=/="
        header = self.tableWidget.verticalHeader()
        order = sorted(range(self.tableWidget.rowCount()), key=header.visualIndex)
        config['rows'] = [
            item.text()
            for item in (self.tableWidget.verticalHeaderItem(row) for row in order)
            if item
        ]

        # per-node identity values, keyed by the "[NN]" row label
        config['serials'] = self._identity_column_values('Serial')
        config['names'] = self._identity_column_values('Name')
        config['revs'] = self._identity_column_values('Rev')

        # free-text "Serial" ("номер") column of media converter rows, in rows order
        serial_col = COLUMN_INDEX['Serial']
        media = []
        for row in order:
            item = self.tableWidget.verticalHeaderItem(row)
            if item and item.text() == MEDIA_CONVERTER:
                cell = self.tableWidget.item(row, serial_col)
                media.append(cell.text() if cell else '')
        if any(media):
            config['media'] = media

        return config

    def _snapshot(self):
        return json.dumps(self._build_site_config(), sort_keys=True, ensure_ascii=False)

    def _has_unsaved_changes(self):
        return self._saved_snapshot is None or self._snapshot() != self._saved_snapshot

    def save_site_config(self, filename=None):
        """Saves site configuration to a JSON file."""

        filename = filename or self.config_file_path
        if not filename:
            self.save_site_config_as()
            return
        config = self._build_site_config()

        try:
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=4)  # Use indent for readability
            log.info(f"Configuration saved to {filename}")
            self._site_changed = False
            self._saved_snapshot = self._snapshot()
            return True
        except (IOError, OSError) as e:
            log.error(f"Error saving configuration: {e}")
            # Use a QMessageBox for error dialog:
            QMessageBox.critical(self, self.tr("Error Saving Configuration"),
                                 self.tr("Could not save configuration to") + f" {filename}:\n{e}")
            return False

    def save_app_config(self):
        config = {}
        # confirmation on tab close
        config['Close_tab_confirm'] = self._confirm_on_close
        # timer setting
        config['Blinker'] = self.led_blink_timer.interval()
        try:
            with open(self._app_config_file_path, 'w') as f:
                json.dump(config, f, indent=4)  # Use indent for readability
            log.info(f'Application configuration saved to {self._app_config_file_path}')
            return True
        except (IOError, OSError) as e:
            log.error(f"Error saving configuration: {e}")
            return False

    def load_app_config(self):
        """Loads the application configuration from a JSON file."""
        try:
            with open(self._app_config_file_path, 'r') as f:
                config: dict = json.load(f)
                self._confirm_on_close = config.get('Close_tab_confirm', True)
                self.led_blink_timer.setInterval(config.get('Blinker', LED_blink_period))
            log.info(f'Application configuration loaded from {self._app_config_file_path}')
            return True
        except FileNotFoundError:
            log.warning("Configuration file not found. Using defaults.")
        except json.JSONDecodeError as e:
            log.error(f"Error decoding JSON configuration: {e}")
        self._confirm_on_close = True
        self.led_blink_timer.setInterval(LED_blink_period)

    def save_site_config_as(self):
        """Saves the application configuration to a user-specified JSON file."""
        prposed_filename_or_dir = self.config_file_path or user_data.get_user_data_path()/'sites'
        filename, _ = QFileDialog.getSaveFileName(
            self,
            self.tr("Save Site Configuration As..."),
            str(prposed_filename_or_dir),  # Default directory (empty string for user's home directory)
            self.tr("JSON Files (*.json);;All Files (*)"),  # Filter
        )

        if filename:  # Check if the user selected a file
            if not filename.lower().endswith(".json"):
                filename += ".json"  # Add .json extension if not present
            if self.save_site_config(filename=filename): # if success
                self.config_file_path = filename  # update path in-place for future 'save' calls
            else:
                pass

    @staticmethod
    def _parse_site_rows(config: dict) -> list:
        """Returns ordered row entries ("[NN]" or MEDIA_CONVERTER) from a site config.

        Supports the legacy "nodes" mapping (entry -> visual index) as a fallback.
        """
        rows = config.get('rows')
        if rows is not None:
            return rows
        items = []
        for key, value in config.get('nodes', {}).items():
            if key == MEDIA_CONVERTER:
                items.extend((visual, MEDIA_CONVERTER) for visual in value)
            else:
                items.append((value, key))
        items.sort(key=lambda item: item[0])
        return [entry for _, entry in items]

    def load_site_config(self, site_conf_filename):
        """Loads the application configuration from a JSON file."""
        try:
            with open(site_conf_filename, 'r') as f:
                config = json.load(f)

            # Load ControlNet Settings
            plc_settings = config.get('CN', {})  # Get CN settings with fallback
            plc_path = plc_settings.get('path', "")
            self.lineEditConnectionPath.setText(plc_path)

            self._stop_workers()
            self.tableWidget.clearContents()
            self.tableWidget.setRowCount(0)

            self.pushButtonScan.setEnabled(True)
            self._setup_columns()

            # load rows in saved (visual) order, restoring identity values when present
            identity_maps = {
                'Serial': config.get('serials', {}),
                'Name': config.get('names', {}),
                'Rev': config.get('revs', {}),
            }
            media_notes = config.get('media', [])
            media_index = 0
            for entry in self._parse_site_rows(config):
                row = self.tableWidget.rowCount()
                self.tableWidget.insertRow(row)
                if entry == MEDIA_CONVERTER:
                    self.tableWidget.setVerticalHeaderItem(row, QTableWidgetItem(MEDIA_CONVERTER))
                    if media_index < len(media_notes) and media_notes[media_index]:
                        self.tableWidget.setItem(row, COLUMN_INDEX['Serial'],
                                                 data_item('Serial', str(media_notes[media_index])))
                    media_index += 1
                    continue
                self.tableWidget.setVerticalHeaderItem(row, Header_Item_NodeNum(int(entry[1:-1])))
                for sid, mapping in identity_maps.items():
                    value = mapping.get(entry)
                    if value:
                        self.tableWidget.setItem(row, COLUMN_INDEX[sid], data_item(sid, str(value)))
            self.tableWidget.load_configuration()
            self._site_loaded = True
            self._site_changed = False
            self._saved_snapshot = self._snapshot()  # fresh baseline after loading
            self._paused = False
            self._update_run_buttons()
            log.info(f"Configuration loaded from {site_conf_filename}")

        except FileNotFoundError:
            log.warning("Configuration file not found. Using defaults.")
        except json.JSONDecodeError as e:
            log.error(f"Error decoding JSON configuration: {e}")

    def load_site_from_file(self):
        """Load the application configuration from a user-specified JSON file."""
        filename, _ = QFileDialog.getOpenFileName(
            self,
            self.tr("Load Site Configuration From..."),
            str(user_data.get_user_data_path()/'sites'),  # Default directory (empty string for user's home directory)
            self.tr("JSON Files (*.json);;All Files (*)"),  # Filter
        )

        if filename:  # Check if the user selected a file
            self.load_site_config(site_conf_filename=filename)
            self.config_file_path = filename  # update path in-place for future 'save' calls

    def on_connection_lost(self, text_error: str):
        log.error(f"Lost connection {text_error}")
        QMessageBox.warning(self, self.tr("Connection to PLC lost"), text_error)
        pass

    def connectSignalsSlots(self):
        self.pushButtonScan.clicked.connect(self.onButtonScan)
        self.pushButtonPathHelp.clicked.connect(self.show_path_help)
        self.lineEditConnectionPath.textChanged.connect(self.on_path_changed)
        self.pushButtonShow.clicked.connect(self.onButtonShow)
        self.pushButtonPause.clicked.connect(self.onButtonPause)
        # exclusive pair: exactly one of Show/Pause stays pressed
        self._run_button_group = QButtonGroup(self)
        self._run_button_group.setExclusive(True)
        self._run_button_group.addButton(self.pushButtonShow)
        self._run_button_group.addButton(self.pushButtonPause)
        self.actionAbout.triggered.connect(self.about)
        self.actionLoad_site.triggered.connect(self.load_site_from_file)
        self.actionSave.triggered.connect(self.save_site_config)
        self.actionSave_as.triggered.connect(self.save_site_config_as)
        self.actionRead_Timer.triggered.connect(self.on_read_timer_conf)
        self.actionEnable_writing_to_PLC.triggered.connect(self.on_write_enable)
        self.actionOpen_config_folder.triggered.connect(self.on_open_folder)
        self.actionShow_log.triggered.connect(self.show_log)
        self.actionShow_CrossTable.triggered.connect(self.show_crosstable)
        self.actionTable_Config.triggered.connect(self.config_dialog)
        self.actionExport_to_Excel.triggered.connect(self.export_to)
        self.tableWidget.rowsMoved.connect(self.sync_crosstable_rows)
        self.actionDrop_Counters.triggered.connect(self.onResetCounters)
        self.actionChangelog.triggered.connect(self.onChangeLog)
        self.actionAck.triggered.connect(self.acknowledge)
        self.actionDrop_all.triggered.connect(self.on_drop_all)
        self.pushButtonRemoveMediaConverter.clicked.connect(self.remove_media_converter)
        self.tableWidget.itemSelectionChanged.connect(self._update_remove_button)
        self._setup_language_menu()

    def _setup_language_menu(self):
        """Builds the Config -> Language submenu from the available languages."""
        current = i18n.configured_language(Glob_settings)
        self._language_group = QtGui.QActionGroup(self)
        self._language_group.setExclusive(True)
        self._language_menu = QtWidgets.QMenu(self.tr("Language"), self)
        for code, name in i18n.LANGUAGES.items():
            action = QtGui.QAction(name, self)
            action.setCheckable(True)
            action.setChecked(code == current)
            action.triggered.connect(lambda _checked, lang=code: self.on_language_changed(lang))
            self._language_group.addAction(action)
            self._language_menu.addAction(action)
        self.menuConfig_2.addMenu(self._language_menu)

    def on_language_changed(self, language):
        """Stores the chosen language and restarts the application to apply it."""
        if language == i18n.configured_language(Glob_settings):
            return
        log.info(f'Language changed to {language}, restarting')
        Glob_settings.setValue('Language', language)
        Glob_settings.sync()
        self._restart()

    def _restart(self):
        """Restarts the current application (used after a language change)."""
        self._restarting = True  # bypass the unsaved-changes prompt, do not persist it
        self._stop_workers()
        program = sys.executable
        args = sys.argv[1:]
        if not getattr(sys, 'frozen', False):
            args = [sys.argv[0], *args]
        started = QtCore.QProcess.startDetached(program, args)
        if isinstance(started, tuple):
            started = started[0]
        if not started:
            log.error('Failed to restart the application')
            self._restarting = False
            return
        QApplication.quit()

    def onChangeLog(self):
        QMessageBox.information(
            self,
            self.tr('Changelog'),
            self.changelog,
        )

    def onResetCounters(self):
        log.debug("Reset counters")
        for node_num, w in self._workers.items():
            assert isinstance(w, PLCConnectionWorker)
            w.reset_counters()
            log.debug(f'reset [{node_num:02}]')

    def config_dialog(self):
        log.debug("Open config dialog")
        dialog = ConfigureDialog(self.tableWidget, self)  # Pass tableWidget and parent
        dialog.exec()  # Show modally

    def sync_crosstable_rows(self):
        """Synchronizes the row order of the CrossTableDialog with self.tableWidget."""
        self._site_changed = True
        if self.MyCrossTable is not None:  # Check if dialog was created.
            log.debug(f'Synchronise table')
            self.MyCrossTable.fill_table(self.tableWidget)

    def show_log(self):
        self.logger_window.show()

    def show_crosstable(self):
        log.debug('Hit show crosstable')
        self.MyCrossTable.show()

    def export_to(self):
        if len(self._workers):
            filename, _ = QFileDialog.getSaveFileName(
                self,
                self.tr("Export data to..."),
                "",  # Default directory (empty string for user's home directory)
                self.tr("XLSX Files (*.xlsx);;All Files (*)"),  # Filter
            )

            if filename:  # Check if the user selected a file
                if not filename.lower().endswith(".xlsx"):
                    filename += ".xlsx"  # Add .xlsx extension if not present
                if self.tableWidget.export_to_excel(filename=filename):  # if success
                    QMessageBox.information(self, self.tr("Success Exporting Data"),
                                         self.tr("Data exported to") + f" {filename}")
                    pass
                else:
                    QMessageBox.critical(self, self.tr("Error Exporting Data"),
                                         self.tr("Could not export data to") + f" {filename}:\n"
                                         + self.tr("See log window for details"))

    def add_media_converter(self):
        cn_media_converter_item = QTableWidgetItem(MEDIA_CONVERTER)

        log.debug("Hit add media converter")
        new_row = self.tableWidget.rowCount()
        self.tableWidget.insertRow(new_row)
        self.tableWidget.setVerticalHeaderItem(new_row, cn_media_converter_item)
        self._site_changed = True

    def _selected_media_rows(self):
        """Returns the selected row indexes whose vertical header is a media converter."""
        rows = []
        selection = self.tableWidget.selectionModel()
        if selection is None:
            return rows
        for index in selection.selectedRows():
            item = self.tableWidget.verticalHeaderItem(index.row())
            if item and item.text() == MEDIA_CONVERTER:
                rows.append(index.row())
        return rows

    def _update_remove_button(self):
        self.pushButtonRemoveMediaConverter.setEnabled(bool(self._selected_media_rows()))

    def remove_media_converter(self):
        """Removes the selected media converter row(s)."""
        rows = sorted(self._selected_media_rows(), reverse=True)
        if not rows:
            return
        log.debug(f"Remove {len(rows)} media converter row(s)")
        for row in rows:
            self.tableWidget.removeRow(row)
        self._site_changed = True
        self.MyCrossTable.fill_table(self.tableWidget)
        self._update_remove_button()

    def on_write_enable(self, state):
        log.debug(f"Counters reset enabled = {state}")
        self._reset_enabled = state
        # self.actionDrop_Counters.setEnabled(state and self.running_count>0)

    def on_open_folder(self):
        directory_path = user_data.get_user_data_path()
        log.info(f"Opening folder {directory_path}")
        if sys.platform == "win32":
            os.startfile(directory_path)
        elif sys.platform == "darwin":
            subprocess.run(["open", directory_path])
        elif sys.platform == "linux":
            subprocess.run(["xdg-open", directory_path])
        else:
            QMessageBox.warning(self, self.tr("Error"),
                                self.tr("Unsupported platform:") + f" {sys.platform}")

    def on_read_timer_conf(self):
        old_value = self.led_blink_timer.interval()
        dialog = HelperConfigDialog(parent=self,
                                    timer_value=self.led_blink_timer.interval(),
                                    confirmation=self._confirm_on_close,
                                    callback=self.led_blink_timer.setInterval)
        result = dialog.exec()
        if result:
            self._confirm_on_close = dialog.checkBox.checkState().value == QtCore.Qt.CheckState.Checked.value
        else:
            self.led_blink_timer.setInterval(old_value)

    def _setup_columns(self):
        """Creates the diagnostic columns and their headers from LABELS."""
        self.tableWidget.setColumnCount(len(LABELS))
        for column, header_data in enumerate(LABELS):
            column_header_item = QTableWidgetItem(tr_label(header_data.comment))
            column_header_item.setData(My_ROLE, header_data)
            column_header_item.setToolTip(tr_label(header_data.longread))
            font = column_header_item.font()  # Get the current font
            font.setPointSize(12)  # Set the desired point size (e.g., 12)
            column_header_item.setFont(font)  # Set the modified font back
            self.tableWidget.setHorizontalHeaderItem(column, column_header_item)

    def _set_identity_value(self, row, sid, value):
        """Sets an identity cell (Serial/Name/Rev), highlighting a changed value."""
        if value in (None, ''):
            return
        text = str(value)
        col = COLUMN_INDEX[sid]
        item = self.tableWidget.item(row, col)
        if item is None:
            self.tableWidget.setItem(row, col, data_item(sid, text))
        else:
            if item.text() != text:
                item.setData(Qt.ItemDataRole.DecorationRole, YELLOW)
            item.setText(text)
            item.setTextAlignment(alignment_for_sid(sid))

    def _identity_column_values(self, sid):
        """Collects non-empty values of an identity column, keyed by row label ("[NN]")."""
        col = COLUMN_INDEX[sid]
        values = {}
        for row in range(self.tableWidget.rowCount()):
            item = self.tableWidget.verticalHeaderItem(row)
            if not item or item.text() == MEDIA_CONVERTER:
                continue
            cell = self.tableWidget.item(row, col)
            if cell and cell.text():
                values[item.text()] = cell.text()
        return values

    def _find_row_by_node(self, node_num: int):
        """Returns the table row for a node number, or None."""
        text = f'[{node_num:02}]'
        for row in range(self.tableWidget.rowCount()):
            item = self.tableWidget.verticalHeaderItem(row)
            if item and item.text() == text:
                return row
        return None

    def _update_run_buttons(self):
        """Show/Pause form an exclusive pair: one stays pressed, the other released."""
        has_workers = bool(self._workers)
        self.pushButtonShow.setEnabled(has_workers)
        self.pushButtonPause.setEnabled(has_workers)
        (self.pushButtonPause if self._paused else self.pushButtonShow).setChecked(True)

    def _stop_workers(self, timeout_ms=10000):
        """Stops all polling workers and waits for their threads to finish.

        A running QThread must never be destroyed, so a worker that does not stop
        within the timeout is kept referenced (and cleaned up on finish) instead.
        """
        workers = list(self._workers.values())
        self._workers = {}
        for worker in workers:
            worker.stop()
        for worker in workers:
            if not worker.wait(timeout_ms):
                log.warning(f'Worker [{worker.node_num:02}] did not stop within {timeout_ms} ms; deferring cleanup')
                try:
                    worker.signals.read_done.disconnect()
                except (TypeError, RuntimeError):
                    pass
                self._retired_workers.append(worker)
        self._retired_workers = [worker for worker in self._retired_workers if not worker.isFinished()]

    def on_path_changed(self, text: str):
        """Live feedback for the ControlNet path field."""
        if not text.strip():
            self.lineEditConnectionPath.setStyleSheet('')
            self.lineEditConnectionPath.setToolTip('')
            return
        ok, err = validate_cn_path(text)
        if ok:
            self.lineEditConnectionPath.setStyleSheet('border: 1px solid #2e7d32;')
            self.lineEditConnectionPath.setToolTip(self.tr('Path format is valid'))
        else:
            self.lineEditConnectionPath.setStyleSheet('border: 1px solid #c62828;')
            self.lineEditConnectionPath.setToolTip(err)

    def show_path_help(self):
        """Shows a reference for the ControlNet path format."""
        box = QMessageBox(self)
        box.setWindowTitle(self.tr('ControlNet path'))
        box.setIcon(QMessageBox.Icon.Information)
        box.setTextFormat(Qt.TextFormat.RichText)
        box.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        box.setText(QCoreApplication.translate("PathHelp", CN_PATH_HELP))
        box.exec()

    def onButtonScan(self):
        """Scans the ControlNet network for nodes and (re)starts polling workers."""
        _path = self.lineEditConnectionPath.text().strip()
        ok, err = validate_cn_path(_path)
        if not ok:
            QMessageBox.warning(self, self.tr("ControlNet path"),
                                f"{err}.\n\n{self.tr('Press \"?\" for help.')}")
            return
        self._stop_workers()
        self.lineEditConnectionPath.setEnabled(False)
        self.pushButtonScan.setEnabled(False)
        self._app.instance().setOverrideCursor(QCursor(Qt.CursorShape.BusyCursor))
        try:
            nodes, paths, identity = scan_cn(_path, p=log.debug)
        except (TimeoutError, CommError) as e:
            log.critical(f"Error Scanning ControlNet (no route to IP address?) {e}")
            QMessageBox.critical(self, self.tr("Error Scanning ControlNet"),
                                 self.tr("Failed to scan ControlNet!\n(no route to the IP address?)")
                                 + f"\n\n{e}")
            self._update_run_buttons()
            return
        except RequestError as e:
            log.critical(f"Error Scanning ControlNet (bad connection path?) {e}")
            QMessageBox.critical(self, self.tr("Error Scanning ControlNet"),
                                 self.tr("Failed to scan ControlNet!\n(bad connection path?)")
                                 + f"\n\n{e}")
            self._update_run_buttons()
            return
        except Exception as e:
            log.exception("Unexpected error while scanning ControlNet")
            QMessageBox.critical(self, self.tr("Error Scanning ControlNet"),
                                 self.tr("Failed to scan ControlNet!") + f"\n\n{e}")
            self._update_run_buttons()
            return
        finally:
            self._app.instance().restoreOverrideCursor()
            self.lineEditConnectionPath.setEnabled(True)
            self.pushButtonScan.setEnabled(True)
        log.info(f'ControlNet [{_path}] scan complete')

        self._setup_columns()

        if not self._site_loaded:
            self.tableWidget.setRowCount(len(nodes))

        for row, (cn_module_serial, cn_path) in enumerate(paths.items()):
            node_num = int(cn_path.split('/')[-1])

            if self._site_loaded:
                target_row = self._find_row_by_node(node_num)
                if target_row is None:
                    # node found on network but absent in the loaded site: append at the end
                    target_row = self.tableWidget.rowCount()
                    self.tableWidget.insertRow(target_row)
                    self.tableWidget.setVerticalHeaderItem(target_row, Header_Item_NodeNum(node_num))
                    self._site_changed = True
                    log.info(f'Node [{node_num:02}] found on network but absent in the loaded site; appended')
            else:
                target_row = row
                self.tableWidget.setVerticalHeaderItem(target_row, Header_Item_NodeNum(node_num))
            # identity cells are "warning on change": highlight if they differ from the previous value
            info = identity.get(node_num, {})
            self._set_identity_value(target_row, 'Serial', cn_module_serial)
            self._set_identity_value(target_row, 'Name', info.get('product_name'))
            self._set_identity_value(target_row, 'Rev', info.get('rev'))

            cn_node_worker = PLCConnectionWorker(node_num)
            cn_node_worker.path = cn_path
            cn_node_worker.signals.read_done.connect(self.update_diag_data)
            cn_node_worker.signals.read_done.connect(self.MyCrossTable.update_diag_data)
            cn_node_worker.start()
            self._workers[node_num] = cn_node_worker

        self.tableWidget.load_configuration()
        self.MyCrossTable.fill_table(self.tableWidget)
        self.pushButtonAddMediaConverter.setEnabled(True)
        self.led_blink_timer.start()
        self._paused = False
        self._update_run_buttons()

    def onButtonPause(self):
        log.info('Pause reading')
        for node_num, worker in self._workers.items():
            assert isinstance(worker, PLCConnectionWorker)
            worker.pause(True)
            log.debug(f'paused [{node_num:02}]')
        self._paused = True
        self._update_run_buttons()

    def onButtonShow(self):
        log.info('Resume reading')
        for node_num, worker in self._workers.items():
            assert isinstance(worker, PLCConnectionWorker)
            worker.pause(False)
            log.debug(f'resumed [{node_num:02}]')
        self._paused = False
        self._update_run_buttons()

    def led_blinker(self):
        global TICK_TACK
        TICK_TACK = not TICK_TACK

        for col in range(self.tableWidget.columnCount()):
            horisontal_header_item = self.tableWidget.horizontalHeaderItem(col)
            column_data: HeaderData = horisontal_header_item.data(My_ROLE) if horisontal_header_item else None
            if column_data and column_data.sid in ('LED_A', 'LED_B'):
                # found LED column
                key = horisontal_header_item.text()
                for row in range(self.tableWidget.rowCount()):
                    vertical_header_item = self.tableWidget.verticalHeaderItem(row)
                    if vertical_header_item and vertical_header_item.text() == MEDIA_CONVERTER:
                        continue

                    cell_item = self.tableWidget.item(row, col)
                    try:
                        value = int(cell_item.text())
                    except ValueError:
                        continue
                    except AttributeError:
                        continue

                    match value:
                        case 0:
                            cell_item.setData(Qt.ItemDataRole.DecorationRole, GREY)
                        case 1:
                            cell_item.setData(Qt.ItemDataRole.DecorationRole, GREEN)
                        case 2:
                            if TICK_TACK:
                                cell_item.setData(Qt.ItemDataRole.DecorationRole, GREEN)
                            else:
                                cell_item.setData(Qt.ItemDataRole.DecorationRole, GREY)
                        case 3:
                            if TICK_TACK:
                                cell_item.setData(Qt.ItemDataRole.DecorationRole, RED)
                            else:
                                cell_item.setData(Qt.ItemDataRole.DecorationRole, GREY)
                        case 4:
                            if TICK_TACK:
                                cell_item.setData(Qt.ItemDataRole.DecorationRole, RED)
                            else:
                                cell_item.setData(Qt.ItemDataRole.DecorationRole, GREEN)
                        case 5:
                            if key == 'LED_A' and TICK_TACK:
                                cell_item.setData(Qt.ItemDataRole.DecorationRole, RED)
                            else:
                                cell_item.setData(Qt.ItemDataRole.DecorationRole, GREY)
                            if key == 'LED_B' and not TICK_TACK:
                                cell_item.setData(Qt.ItemDataRole.DecorationRole, RED)
                            else:
                                cell_item.setData(Qt.ItemDataRole.DecorationRole, GREY)
                        case 6:
                            if key == 'LED_A' and TICK_TACK:
                                cell_item.setData(Qt.ItemDataRole.DecorationRole, RED)
                            else:
                                cell_item.setData(Qt.ItemDataRole.DecorationRole, GREEN)
                            if key == 'LED_B' and not TICK_TACK:
                                cell_item.setData(Qt.ItemDataRole.DecorationRole, RED)
                            else:
                                cell_item.setData(Qt.ItemDataRole.DecorationRole, GREEN)
                        case 7:
                            cell_item.setData(Qt.ItemDataRole.DecorationRole, RED)

        self.status_bar_label_1.setText((f"Number of running workers: {self.running_count}"))
        self.actionDrop_Counters.setEnabled(self._reset_enabled and self.running_count > 0)

    @property
    def running_count(self):
        return sum(worker.isRunning() for worker in self._workers.values())

    def acknowledge(self):
        """reset warnings"""
        for col in range(self.tableWidget.columnCount()):
            horisontal_header_item = self.tableWidget.horizontalHeaderItem(col)
            column_data: HeaderData = horisontal_header_item.data(My_ROLE) if horisontal_header_item else None
            if column_data and column_data.woc:
                for row in range(self.tableWidget.rowCount()):
                    vertical_header_item = self.tableWidget.verticalHeaderItem(row)
                    if vertical_header_item and vertical_header_item.text() == MEDIA_CONVERTER:
                        continue
                    cell_item = self.tableWidget.item(row, col)
                    if cell_item is not None:
                        cell_item.setData(Qt.ItemDataRole.DecorationRole, None)

    def update_diag_data(self, node_num, diag_data: dict):
        """Updates diagnostic data in the table for the specified node using a dictionary.

        Args:
            node_num: The node number to update.
            diag_data: A dictionary where keys correspond to column header labels
                       and values are the data to be displayed.
        """

        for row in range(self.tableWidget.rowCount()):
            item = self.tableWidget.verticalHeaderItem(row)
            if item and item.text() == f'[{node_num:02}]':
                # found row with current node number
                for key, value in diag_data.items():
                    if key not in DiagWindow.labels:
                        continue
                    # Find the column index based on the header label (PyQt6 change).
                    try:
                        # In PyQt6, horizontalHeaderItem() returns a QTableWidgetItem or None
                        # We need to iterate through the header items.
                        for col in range(self.tableWidget.columnCount()):
                            header_item = self.tableWidget.horizontalHeaderItem(col)
                            column_data: HeaderData = header_item.data(My_ROLE) if header_item else None
                            if column_data and column_data.sid == key:
                                break  # Found the column
                        else:  # Loop completed without finding the header
                            raise ValueError(f"Header '{key}' not found")
                    except ValueError as e:
                        log.debug(f'{e}')
                        continue

                    try:
                        if key.endswith('_avg'):
                            str_value = f"{float(value):.2f}"
                        else:
                            str_value = str(value)
                    except (TypeError, ValueError) as e:
                        str_value = f"Error: {e}"
                    item = self.tableWidget.item(row, col)
                    if item:
                        if column_data.woc:
                            # warning sign if value changed
                            old_text = item.text()
                            if old_text!=str_value:
                                item.setData(Qt.ItemDataRole.DecorationRole, YELLOW)
                        item.setText(str_value)
                        item.setTextAlignment(alignment_for_sid(key))
                    else:
                        self.tableWidget.setItem(row, col, data_item(key, str_value))

    def on_drop_all(self):
        """Stops polling and clears all data, as if the program was just started."""
        if self._confirm_on_close and self._has_unsaved_changes():
            reply = QMessageBox.question(self, self.tr('Drop all'),
                self.tr("Drop all data? Any unsaved changes will be lost."),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No)
            if reply != QMessageBox.StandardButton.Yes:
                return
        log.info('Drop all: resetting to initial state')

        self._stop_workers()
        self.led_blink_timer.stop()

        # main table
        self.tableWidget.clearContents()
        self.tableWidget.setRowCount(0)
        self.tableWidget.setColumnCount(0)

        # cross table
        self.MyCrossTable.tableWidget.clear()
        self.MyCrossTable.tableWidget.setRowCount(0)
        self.MyCrossTable.tableWidget.setColumnCount(0)
        self.MyCrossTable._complaint_cols = {}

        # site / connection state
        self._config_file_path = None
        self._site_loaded = False
        self._site_changed = False
        self._paused = False
        self.setWindowTitle(self.tr("ControlNet diagnostic tool"))
        self.lineEditConnectionPath.clear()
        self._saved_snapshot = self._snapshot()  # empty baseline after reset
        self.lineEditConnectionPath.setEnabled(True)
        self.pushButtonScan.setEnabled(True)
        self.pushButtonAddMediaConverter.setEnabled(False)
        self.actionEnable_writing_to_PLC.setChecked(False)
        self._reset_enabled = False
        self.actionDrop_Counters.setEnabled(False)
        self._update_run_buttons()
        self.status_bar_label_1.setText("Not connected yet")

    def closeEvent(self, event):
        self.save_app_config()
        if not self._restarting and self._confirm_on_close and self._has_unsaved_changes():
            reply = QMessageBox.question(self, self.tr('Close the program?'),
                self.tr("Are you sure to quit? Any unsaved changes will be lost."),
                QMessageBox.StandardButton.Yes |
                QMessageBox.StandardButton.No, QMessageBox.StandardButton.No)

            if reply != QMessageBox.StandardButton.Yes:
                event.ignore()
                return
        # persist geometry of the detached dialogs that may only have been hidden, not closed
        self.logger_window.save_geometry()
        self.MyCrossTable.save_geometry()
        self._stop_workers()
        event.accept()

    def about(self):
        QMessageBox.about(
            self,
            self.tr("About ControlNet Diagnostic Tool"),
            f"<p>{self.tr('Version:')} {ver.strng}</p>"
            f"<p>{self.tr('Commit:')} {ver.commit}</p>"
            f"<p>{self.tr('By using ControlNet Diagnostic Tool')}</p>"
            f"<p>{self.tr('you can significantly improve the troubleshooting speed of ControlNet networks.')}</p>"
            f"<p> - PyQt6</p>"
            f"<p> - Qt Designer6</p>"
            f"<p> - Python3.12</p>"
            f"<p> {self.tr('Fugue Icons (C) 2013 Yusuke Kamiyamane. All rights reserved.')}</p>"
            f"{self.tr('System:')} {os.name}"
        )

    def about_pyqt(self):
        QMessageBox.aboutQt(self)


if __name__ == "__main__":
    log = logging.getLogger(__name__)
    log.setLevel(logging.DEBUG)
    log.info('Start application')

    # PyQt6 aborts the process on an unhandled exception raised inside a slot;
    # logging it instead keeps the application alive and surfaces the traceback.
    def _log_unhandled_exception(exc_type, exc_value, exc_tb):
        log.critical("Unhandled exception", exc_info=(exc_type, exc_value, exc_tb))
    sys.excepthook = _log_unhandled_exception

    app_config_dir_path = user_data.get_user_data_path()
    sites_path = app_config_dir_path / 'sites'
    app_config_file_path = app_config_dir_path / 'config.json'

    Glob_settings = QSettings(user_data.Organisation, user_data.AppName)

    # Create the directory if it doesn't exist
    if not app_config_dir_path.exists():
        app_config_dir_path.mkdir(parents=True, exist_ok=True)
        log.info(f"Config dir created {app_config_dir_path}")
    if not sites_path.exists():
        sites_path.mkdir(parents=True, exist_ok=True)
        log.info(f"sites dir created {sites_path}")

    app = QApplication(sys.argv)
    _translators = i18n.install_translations(app, i18n.configured_language(Glob_settings))
    app.setWindowIcon(QtGui.QIcon(os.path.join(user_data.asset_dir, 'cn_media.ico')))

    win = DiagWindow(app_config_file_path)
    win.show()
    sys.exit(app.exec())
