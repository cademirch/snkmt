from pathlib import Path
from platformdirs import user_data_dir

SNKMT_DIR = Path(user_data_dir(appname="snkmt", appauthor=False, ensure_exists=True))
