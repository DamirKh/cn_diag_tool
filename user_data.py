# Constants for clarity
import os
import pathlib
import sys

# In a PyInstaller bundle data files live under sys._MEIPASS (the one-dir "_internal");
# in a normal run they are next to this module.
basedir = sys._MEIPASS if getattr(sys, 'frozen', False) else os.path.dirname(os.path.abspath(__file__))
asset_dir = os.path.join(basedir, 'asset')

Organisation = 'CPC'
AppName = 'CN_Diagnostic_Tool'

def get_user_data_path():
    """Returns the user's data directory in an OS-independent way."""

    home_dir = pathlib.Path.home()
    app_data_dir = home_dir / "AppData" if os.name == "nt" else home_dir / ".config"
    user_data_dir = app_data_dir / f"CN_diag_tool"

    return user_data_dir
