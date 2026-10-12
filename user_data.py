# Constants for clarity
import os
import pathlib

basedir = os.path.dirname(__file__)
asset_dir = os.path.join(basedir, 'asset')

Organisation = 'CPC'
AppName = 'CN_Diagnostic_Tool'

def get_user_data_path():
    """Returns the user's data directory in an OS-independent way."""

    home_dir = pathlib.Path.home()
    app_data_dir = home_dir / "AppData" if os.name == "nt" else home_dir / ".config"
    user_data_dir = app_data_dir / f"CN_diag_tool"

    return user_data_dir
