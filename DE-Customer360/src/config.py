import json
import logging
from pathlib import Path


def load_config(base_dir, path="config.json"):
    config_path = Path(base_dir) / path
    with open(config_path, "r", encoding="utf-8") as f:
        return json.load(f)


def setup_logging(base_dir, log_path):
    path = Path(base_dir) / log_path
    path.parent.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("customer360")
    logger.setLevel(logging.INFO)
    logger.handlers.clear()
    fmt = logging.Formatter("%(asctime)s %(levelname)s %(message)s")
    fh = logging.FileHandler(path, encoding="utf-8")
    fh.setFormatter(fmt)
    sh = logging.StreamHandler()
    sh.setFormatter(fmt)
    logger.addHandler(fh)
    logger.addHandler(sh)
    return logger
