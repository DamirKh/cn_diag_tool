"""Remembers the last directory used for Excel exports."""
import os

EXPORT_DIR_KEY = "ExportDir"


def default_dir(config_dir):
    return os.path.join(str(config_dir), "sites")


def current_dir(settings, default):
    stored = settings.value(EXPORT_DIR_KEY, "")
    if stored:
        stored = os.path.expanduser(str(stored))
        if os.path.isdir(stored):
            return stored
    return default


def remember(settings, filename):
    directory = os.path.dirname(os.path.abspath(filename))
    settings.setValue(EXPORT_DIR_KEY, directory)
    settings.sync()
    return directory


def reset(settings):
    settings.remove(EXPORT_DIR_KEY)
    settings.sync()
