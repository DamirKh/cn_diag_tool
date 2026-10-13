"""Minimal internationalisation support.

Uses Qt's ``.ts`` catalogs directly (parsed at runtime), so no ``lrelease`` is
required.  Strings are extracted with ``pylupdate6`` (see ``translations/update.sh``).
"""
import os
import sys
import xml.etree.ElementTree as ET

from PyQt6.QtCore import QTranslator, QLocale, QLibraryInfo


# language code -> name shown in the UI (in its own language)
LANGUAGES = {
    'en': 'English',
    'ru': 'Русский',
}
DEFAULT_LANGUAGE = 'en'


def translations_dir():
    """Directory that holds the .ts catalogs (works both from source and frozen)."""
    if getattr(sys, 'frozen', False):
        base = sys._MEIPASS
    else:
        base = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base, 'translations')


def system_language():
    """Best match for the current system locale, limited to supported languages."""
    code = QLocale.system().name().split('_')[0]
    return code if code in LANGUAGES else DEFAULT_LANGUAGE


def configured_language(settings):
    """Language from QSettings, falling back to the system language."""
    value = settings.value('Language') if settings is not None else None
    return value if value in LANGUAGES else system_language()


class TsTranslator(QTranslator):
    """A QTranslator that reads Qt ``.ts`` XML files directly (no compiled .qm)."""

    def __init__(self, filename=None, parent=None):
        super().__init__(parent)
        self._catalog = {}
        self._filename = None
        if filename:
            self.load_ts(filename)

    def load_ts(self, filename):
        try:
            root = ET.parse(filename).getroot()
        except (OSError, ET.ParseError):
            return False
        catalog = {}
        for context in root.findall('context'):
            name = context.findtext('name') or ''
            for message in context.findall('message'):
                source = message.findtext('source')
                if not source:
                    continue
                translation = message.find('translation')
                if translation is None or translation.get('type') == 'unfinished':
                    continue
                text = translation.text or ''
                if text:
                    catalog[(name, source)] = text
        self._catalog = catalog
        self._filename = filename
        return True

    def translate(self, context, sourceText, disambiguation=None, n=-1):
        # return None (not "") when unknown, so Qt falls back to other translators
        # (e.g. qtbase_ru for the standard dialog buttons) and then to the source text
        return self._catalog.get((context, sourceText)) or None


def install_translations(app, language):
    """Installs Qt's own translations and the application catalog.

    Returns the list of installed translators; the caller must keep it alive.
    """
    keep = []

    # Qt's built-in strings (QMessageBox buttons, QFileDialog, ...)
    qt_dir = QLibraryInfo.path(QLibraryInfo.LibraryPath.TranslationsPath)
    qt_translator = QTranslator()
    if qt_translator.load(f'qtbase_{language}', qt_dir):
        app.installTranslator(qt_translator)
        keep.append(qt_translator)

    if language != DEFAULT_LANGUAGE:
        ts_file = os.path.join(translations_dir(), f'cn_diag_tool_{language}.ts')
        app_translator = TsTranslator(ts_file)
        app.installTranslator(app_translator)
        keep.append(app_translator)

    return keep
