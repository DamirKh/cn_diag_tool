import datetime
import subprocess
import logging
import os
import sys
import time

import json
from fileinput import filename

from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtCore import QSettings
from PyQt6.QtGui import QCursor, QColor, QBrush, QFont
from PyQt6 import QtWidgets, QtCore, QtGui
from PyQt6.QtWidgets import QMainWindow, QApplication, QProgressDialog, QVBoxLayout, QMessageBox, QLabel, QDialog, \
    QWidget, QTableWidgetItem, QTableWidget, QGridLayout, QGroupBox, QCheckBox, QLineEdit, QDialogButtonBox, \
    QHeaderView, QFileDialog, QButtonGroup

import user_data
import ver

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
               comment='номер',
               hint='Серийный номер модуля',
               woc=True,
               ),
    HeaderData('Name',
               comment='Name',
               hint='Имя/каталожный номер модуля',
               woc=True,
               ),
    HeaderData('Rev',
               comment='Rev',
               hint='Ревизия (версия) модуля',
               woc=True,
               ),
    HeaderData('reply_time',
               comment='Ответ',
               hint='Время ответа, мкс',
               longread="""Время ответа в микросекундах. 
               Возможно, показания некоректны и малоинформативны""",
               ),
    HeaderData('LED_A',
               comment='A',
               hint='Состояние индикатора A',
               longread="""Состояние индикатора на модуле. 
               Состояния при которых нет связи с модулем не могут быть отображены, потому что нет связи с модулем""",
               ),
    HeaderData('LED_B',
               comment='B',
               hint='Состояние индикатора B',
               longread="""Состояние индикатора на модуле. 
               Состояния при которых нет связи с модулем не могут быть отображены, потому что нет связи с модулем""",
               ),
    HeaderData('channel_A_frame_error',
               comment='A err',
               hint='Счетчик ошибок канала A',
               longread="Счетчик ошибок канала A\n"
                        "8 bit",
               woc=True,
               ),
    HeaderData('channel_A_frame_error/s',
               comment='A err/s',
               hint='Ошибки канала A в секунду',
               longread="""Ошибки по каналу А за последнюю секунду""",
               ),
    HeaderData('channel_B_frame_error',
               comment='B err',
               hint='Счетчик ошибок канала B',
               longread="""Счетчик ошибок канала B 
               (8bit)""",
               woc=True,
               ),
    HeaderData('channel_B_frame_error/s',
               comment='B err/s',
               hint='Ошибки канала B в секунду',
               longread="""Ошибки по каналу B за последнюю секунду""",
               ),
    HeaderData('selected_channel_frame_error',
               comment='Err',
               hint='Счетчик ошибок по активному каналу',
               longread="Счетчик ошибок по активному каналу\n"
                        "8 bit",
               woc=True,
               ),
    HeaderData('selected_channel_frame_error/s',
               comment='Err/s',
               hint='Ошибки по активному каналу',
               longread="""Ошибки по активному каналу за последнюю секунду""",
               ),
    HeaderData('Active_Channel',
               comment='Акт.',
               hint='Активный канал',
               longread="""Канал, выбранный активным на данный момент""",
               ),
    HeaderData('Redundancy_Warning',
               comment='Резерв',
               hint='Флаг отсутсвия резерва',
               longread="""Флаг отсутсвия резерва
               активируется в случае отсутсвия резервного канала""",
               ),

    HeaderData('good_frames_transmitted',
               comment='⇑',
               hint='Счетчик успешно переданных кадров',
               longread="""Счетчик успешно переданных кадров\n24 бита\nБолее информативно поле '⇑/с'""",
               ),
    HeaderData('good_frames_transmitted/s',
               comment='⇑/с',
               hint='Передано успешно',
               longread="""Успешно передано кадров за последнюю секунду""",
               ),
    HeaderData('aborted_frame_transmitted',
               comment='⇞',
               hint='Счетчик оборыва передачи',
               longread="""Счетчик обрыва передачи\n8 бит""",
               woc=True,
               ),
    HeaderData('good_frames_received',
               comment='⇓',
               hint='Счетчик успешно принятых кадров',
               longread="""Счетчик успешно принятых кадров\n24 бита\nБолее информативно поле '⇓/с'""",
               ),
    HeaderData('good_frames_received/s',
               comment='⇓/с',
               hint='Принято успешно',
               longread="""Успешно принято кадров за последнюю секунду""",
               ),
    HeaderData('aborted_frames_received',
               comment='⇟',
               hint='Счетчик обрыва приема',
               longread="""Счетчик обрыва приема\n8 бит""",
               ),

    HeaderData('noise_hits',
               comment='∿',
               hint='Счетчик шумовых срабатываний',
               longread="""В сети Allen-Bradley ControlNet «количество шумовых срабатываний» означает, сколько раз в сети связи сигнал отклоняется от ожидаемого, что может указывать на наличие шумовых помех. Это количество является диагностическим индикатором качества сигнала и потенциальных проблем со связью в сети ControlNet.
В ControlNet шумом называют нежелательные электрические сигналы, которые могут нарушить заданный сигнал связи, приводя к ошибкам и потенциальным сбоям связи.
Что такое шумовое срабатывание?
Шумовое срабатывание — это единичный случай отклонения принятого сигнала от ожидаемого из-за шума.

Количество шумовых срабатываний служит мерой качества сигнала. Более высокое количество указывает на наличие шумовых помех в сети, что может привести к снижению производительности связи и потенциальным ошибкам связи.

При устранении неполадок связи в ControlNet мониторинг количества шумовых срабатываний является важным этапом. Высокое значение указывает на необходимость исследования источника шума и принятия мер по его снижению, таких как заземление, экранирование или прокладка кабелей.
""",
               woc=True,
               ),
    HeaderData('noise_hits/s',
               comment='∿/с',
               hint='Приращение шума за секунду',
               longread="""Приращение счетчика шумовых срабатываний за последнюю секунду""",
               ),

    HeaderData('collisions',
               comment='⇆',
               hint='Счетчик коллизий',
               longread="В сети Allen-Bradley ControlNet количество коллизий — это диагностическое значение, "
                        "указывающее, сколько раз устройство в сети обнаруживало потенциальную коллизию" 
                        "во время передачи данных. ControlNet использует схему множественного доступа" 
                        "с временным разделением каналов (TDMA), которая по своей сути является детерминированной" 
                        "и минимизирует коллизии. Однако коллизии всё равно могут возникать из-за таких факторов," 
                        "как сетевой шум или неправильная настройка. Количество коллизий позволяет оценить" 
                        "состояние сети и выявить потенциальные проблемы.\n"
                        "Счетчик 8 бит",
               woc=True,
               ),
    HeaderData('collisions/s',
               comment='⇆/с',
               hint='',
               longread="""Приращение счетчика коллизий за последнюю секунду""",
               ),

    HeaderData('highwaters',
               comment='OVRL',
               hint='Перегрузка',
               longread="""Перегрузка""",
               woc=True,
               ),
    HeaderData('nut_overloads',
               comment='NUT\nOVRL',
               hint='NUT перегрузка',
               longread="""NUT перегрузка""",
               ),
    HeaderData('nut_overloads/s',
               comment='NUT\nOVRL/c',
               hint='NUT перегрузка/с',
               longread="""Приращение счетчика 'NUT перегрузка' за последнюю секунду""",
               woc=True,
               ),
    HeaderData('slot_overloads',
               comment='SLOT\nOVRL',
               hint='slot_overloads',
               longread="""""",
               woc=True,
               ),
    HeaderData('slot_overloads/s',
               comment='SLOT\nOVRL/s',
               hint='slot_overloads',
               longread="""Приращение счетчика 'slot_overloads' за последнюю секунду """,
               ),
    HeaderData('blockages',
               comment='BLOCK',
               hint='',
               longread="""""",
               woc=True,
               ),
    HeaderData('blockages/s',
               comment='BLOCK\n    /s',
               hint='',
               longread="""""",
               ),
    HeaderData('non_concurrence',
               comment='NON\nCNCR',
               hint='Несогласованность',
               longread="""
               В Allen-Bradley ControlNet термин «счетчик несогласованности» относится к счетчику, который отслеживает количество пропущенных или неудавшихся запланированных подключений к устройству в сети. Этот счетчик помогает диагностировать проблемы со связью и потенциальные проблемы с детерминированной производительностью сети.

Запланированные подключения:
ControlNet использует запланированные подключения для обеспечения детерминированной связи между устройствами в режиме реального времени. Эти подключения предварительно настроены и им выделены определенные временные интервалы для обмена данными.

Несогласованность:
Когда запланированное подключение не устанавливается в течение выделенного временного интервала, это считается событием несогласованности. Это может произойти по разным причинам, таким как перегрузка сети, недоступность устройства или ошибки связи.
""",
               woc=True,
               ),
    HeaderData('non_concurrence/s',
               comment='NON\nCNCR/s',
               hint='',
               longread="""""",
               ),
    # rarely used
    HeaderData('lonely_counter',
               comment='LNLY',
               hint='lonely_counter',
               longread="""
               В сети Allen-Bradley ControlNet «одинокий счётчик» относится к счётчику сетевых ошибок, который увеличивается при обнаружении состояния «одиночества» или «несоответствия сети» в сети ControlNet. Этот счётчик является внутренним диагностическим инструментом модуля 1756-CNB ControlNet. Он срабатывает, когда узел сети не видит достаточного количества других узлов для формирования корректной сети или при несоответствии сетевых параметров.

Резервирование ControlNet и «одинокие» сети:
ControlNet разработан для резервирования, то есть он может переключаться между несколькими контроллерами для поддержания работы сети. Однако во время переключений или в определённых конфигурациях сеть может стать «одинокой», если в ней недостаточно активных узлов для корректной работы.""",
               woc=True,
               ),
    HeaderData('duplicate_node',
               comment='DUP',
               hint='duplicate_node',
               longread="""duplicate_node""",
               woc=True,
               ),
    HeaderData('mod_mac_id',
               comment='MOD\nMAC',
               hint='mod_mac_id',
               longread="""mod_mac_id""",
               ),
    HeaderData('non_lowman_mods',
               comment='nLOW\nmods',
               hint='non_lowman_mods',
               longread="""non_lowman_mods""",
               woc=True,
               ),
    HeaderData('rogue_count',
               comment='ROG',
               hint='rogue_count',
               longread="""""",
               woc=True,
               ),
]

# sid -> logical column index (column order is fixed by LABELS; only visual order changes)
COLUMN_INDEX = {label.sid: index for index, label in enumerate(LABELS)}


class GeometrySaver(QWidget):
    def geometry_saver_init(self, settings_key: str):
        self.geometry_saver_settings = Glob_settings
        self._geometry_settings_key = settings_key
        self.restore_geometry()

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
        self.setWindowTitle("Configure Data View")
        self.tableWidget = table_widget

        # Use a QTableWidget for the configuration options
        self.configTable = QTableWidget(0, 3, self)  # 0 rows initially, 3 columns
        self.configTable.setHorizontalHeaderLabels(["Column Name", "Description", "Visibility"])
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

                hint = QTableWidgetItem(header_data.hint)
                hint.setToolTip(header_data.longread)
                self.configTable.setItem(row, 1, hint)

                check_box = QtWidgets.QCheckBox()
                check_box.setChecked(not self.tableWidget.isColumnHidden(col))
                check_box.stateChanged.connect(lambda state, col=col: self.toggle_column_visibility(col, state))
                self.configTable.setCellWidget(row, 2, check_box)

        except IndexError as e:
            QMessageBox.critical(self, "Error", str(e))
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
        self.setWindowTitle("Bad Frame Cross Table")

        self.setupUi(self)
        self.connectSignalsSlots()
        self.geometry_saver_init(settings_key="CrossTableDialog")
        self.hide()

    def connectSignalsSlots(self):
        pass

    def fill_table(self, from_table: QTableWidget):
        log.debug('Fill crosstable')
        self.tableWidget.clear()
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
        """Updates diagnostic data in the crosstable for the specified node.

        Args:
            node_num: The node number to update.
            diag_data: A dictionary where keys correspond to column header labels
                       and values are the data to be displayed.
        """

        for row in range(self.tableWidget.rowCount()):
            item = self.tableWidget.verticalHeaderItem(row)
            if item and item.text() == f'[{node_num:02}]':
                for key, value in diag_data.items():
                    # ## Node intersection updates here
                    if type(key) == type('') and key.startswith('#err_'):
                        if value:
                            error_node_num_in_log = f'[{value:02}]'

                            for col in range(self.tableWidget.columnCount()):
                                header_item = self.tableWidget.horizontalHeaderItem(col)
                                if header_item and header_item.text() == error_node_num_in_log:
                                    err_item = QTableWidgetItem('')
                                    if error_node_num_in_log == item.text():
                                        err_item.setData(Qt.ItemDataRole.DecorationRole, QtGui.QColor('yellow'))
                                        # err_item.setData(Qt.ItemDataRole.UserRole)
                                    else:
                                        err_item.setData(Qt.ItemDataRole.DecorationRole, QtGui.QColor('red'))
                                    self.tableWidget.setItem(row, col, err_item)
                                    break  # Found the column
                    # ## End of Node intersection updates


class LogWindow(QDialog, GeometrySaver):
    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self.setWindowTitle("Log Viewer")
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

        with open( os.path.join(user_data.basedir, 'changelog.txt')) as chlog:
            self.changelog = chlog.read()


    @property
    def config_file_path(self):
        return self._config_file_path

    @config_file_path.setter
    def config_file_path(self, value: str):
        self._config_file_path = value
        self.setWindowTitle(f"ControlNet diagnostic tool  {value}")

    def non_fatal(self, message):
        self.statusBar().showMessage(message, 10000)

    def save_site_config(self, filename=None):
        """Saves site configuration to a JSON file."""

        filename = filename or self.config_file_path
        if not filename:
            self.save_site_config_as()
            return
        config = {}

        # CN Settings
        config['CN'] = {
            'path': self.lineEditConnectionPath.text(),
        }

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

        try:
            with open(filename, 'w') as f:
                json.dump(config, f, indent=4)  # Use indent for readability
            log.info(f"Configuration saved to {filename}")
            self._site_changed = False
            return True
        except (IOError, OSError) as e:
            log.error(f"Error saving configuration: {e}")
            # Use a QMessageBox for error dialog:
            QMessageBox.critical(self, "Error Saving Configuration",
                                 f"Could not save configuration to {filename}:\n{e}")
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
            "Save Site Configuration As...",
            str(prposed_filename_or_dir),  # Default directory (empty string for user's home directory)
            "JSON Files (*.json);;All Files (*)",  # Filter
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
            for entry in self._parse_site_rows(config):
                row = self.tableWidget.rowCount()
                self.tableWidget.insertRow(row)
                if entry == MEDIA_CONVERTER:
                    self.tableWidget.setVerticalHeaderItem(row, QTableWidgetItem(MEDIA_CONVERTER))
                    continue
                self.tableWidget.setVerticalHeaderItem(row, Header_Item_NodeNum(int(entry[1:-1])))
                for sid, mapping in identity_maps.items():
                    value = mapping.get(entry)
                    if value:
                        self.tableWidget.setItem(row, COLUMN_INDEX[sid], QTableWidgetItem(str(value)))
            self.tableWidget.load_configuration()
            self._site_loaded = True
            self._site_changed = False
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
            "Load Site Configuration From...",
            str(user_data.get_user_data_path()/'sites'),  # Default directory (empty string for user's home directory)
            "JSON Files (*.json);;All Files (*)",  # Filter
        )

        if filename:  # Check if the user selected a file
            self.load_site_config(site_conf_filename=filename)
            self.config_file_path = filename  # update path in-place for future 'save' calls

    def on_connection_lost(self, text_error: str):
        log.error(f"Lost connection {text_error}")
        QMessageBox.warning(self, f"Connection to PLC lost", text_error)
        pass

    def connectSignalsSlots(self):
        self.pushButtonScan.clicked.connect(self.onButtonScan)
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

    def onChangeLog(self):
        QMessageBox.information(
            self,
            'Changelog',
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
                "Export data to...",
                "",  # Default directory (empty string for user's home directory)
                "XLSX Files (*.xlsx);;All Files (*)",  # Filter
            )

            if filename:  # Check if the user selected a file
                if not filename.lower().endswith(".xlsx"):
                    filename += ".xlsx"  # Add .xlsx extension if not present
                if self.tableWidget.export_to_excel(filename=filename):  # if success
                    QMessageBox.information(self, "Success Exporting Data",
                                         f"Data exported to {filename}")
                    pass
                else:
                    QMessageBox.critical(self, "Error Exporting Data",
                                         f"Could not export data to {filename}:\n See log window for details")

    def add_media_converter(self):
        cn_media_converter_item = QTableWidgetItem(MEDIA_CONVERTER)

        log.debug("Hit add media converter")
        new_row = self.tableWidget.rowCount()
        self.tableWidget.insertRow(new_row)
        self.tableWidget.setVerticalHeaderItem(new_row, cn_media_converter_item)
        self._site_changed = True

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
            QMessageBox.warning(self, "Error", f"Unsupported platform: {sys.platform}")

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
            column_header_item = QTableWidgetItem(header_data.comment)
            column_header_item.setData(My_ROLE, header_data)
            column_header_item.setToolTip(header_data.longread)
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
            self.tableWidget.setItem(row, col, QTableWidgetItem(text))
        else:
            if item.text() != text:
                item.setData(Qt.ItemDataRole.DecorationRole, YELLOW)
            item.setText(text)

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

    def onButtonScan(self):
        """Scans the ControlNet network for nodes and (re)starts polling workers."""
        _path = self.lineEditConnectionPath.text()
        self._stop_workers()
        self.lineEditConnectionPath.setEnabled(False)
        self.pushButtonScan.setEnabled(False)
        self._app.instance().setOverrideCursor(QCursor(Qt.CursorShape.BusyCursor))
        try:
            nodes, paths, identity = scan_cn(_path, p=log.debug)
        except (TimeoutError, CommError) as e:
            log.critical(f"Error Scanning ControlNet (no route to IP address?) {e}")
            QMessageBox.critical(self, "Error Scanning ControlNet",
                                 f"Error occurs while scanning ControlNet!\n(no route to IP address?)\n\n"
                                 f"{e}")
            self._update_run_buttons()
            return
        except RequestError as e:
            log.critical(f"Error Scanning ControlNet (bad connection path?) {e}")
            QMessageBox.critical(self, "Error Scanning ControlNet",
                                 f"Error occurs while scanning ControlNet!\n(bad connection path?)\n\n"
                                 f"{e}")
            self._update_run_buttons()
            return
        except Exception as e:
            log.exception("Unexpected error while scanning ControlNet")
            QMessageBox.critical(self, "Error Scanning ControlNet",
                                 f"Error occurs while scanning ControlNet!\n\n{e}")
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
                    else:
                        new_item = QTableWidgetItem(str_value)
                        self.tableWidget.setItem(row, col, new_item)

    def closeEvent(self, event):
        self.save_app_config()
        if self._confirm_on_close and self._site_changed:
            reply = QMessageBox.question(self, 'Message',
                "Are you sure to quit? Any unsaved changes will be lost.", QMessageBox.StandardButton.Yes |
                QMessageBox.StandardButton.No, QMessageBox.StandardButton.No)

            if reply != QMessageBox.StandardButton.Yes:
                event.ignore()
                return
        self._stop_workers()
        event.accept()

    def about(self):
        QMessageBox.about(
            self,
            "About ControlNet Diagnostic Tool",
            f"<p>Version: {ver.strng}</p>"
            f"<p>Commit: {ver.commit}</p>"
            f"<p>By using ControlNet Diagnostic Tool</p>"
            f"<p>you can significantly improve the troubleshooting speed of ControlNet networks.</p>"
            f"<p> - PyQt6</p>"
            f"<p> - Qt Designer6</p>"
            f"<p> - Python3.12</p>"
            f"<p> Fugue Icons (C) 2013 Yusuke Kamiyamane. All rights reserved.</p>"
            f"System: {os.name}"
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
    app.setWindowIcon(QtGui.QIcon(os.path.join(user_data.asset_dir, 'cn_media.ico')))

    win = DiagWindow(app_config_file_path)
    win.show()
    sys.exit(app.exec())
