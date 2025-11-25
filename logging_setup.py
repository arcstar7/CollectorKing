# logging_setup.py
import logging
import logging.handlers
import os
from pathlib import Path
from datetime import datetime

APP_NAME = "CollectorKing"

def _default_log_dir() -> Path:
    # Priority: explicit env var -> LOCALAPPDATA -> APPDATA -> ./logs
    for env in ("COLLECTORKING_LOG_DIR", "LOCALAPPDATA", "APPDATA"):
        p = os.environ.get(env)
        if p:
            base = Path(p)
            return (base / APP_NAME / "logs").resolve()
    return (Path.cwd() / "logs").resolve()

def ensure_log_dir(dir_path: Path) -> Path:
    dir_path.mkdir(parents=True, exist_ok=True)
    return dir_path

def get_log_paths() -> tuple[Path, Path]:
    log_dir = ensure_log_dir(_default_log_dir())
    today = datetime.now().strftime("%Y-%m-%d")
    file_log = log_dir / f"app-{today}.log"        # human-readable
    json_log = log_dir / f"app-{today}.jsonl"      # machine-readable (optional)
    return file_log, json_log

class _KVFormatter(logging.Formatter):
    """Key-value (human readable) formatter with useful context."""
    def format(self, record: logging.LogRecord) -> str:
        base = super().format(record)
        ctx = []
        # If using LoggerAdapter extra={'import_file':..., 'run_id':...}, they appear on the record
        for key in ("run_id", "import_file", "item_count", "user"):
            if hasattr(record, key):
                ctx.append(f"{key}={getattr(record, key)}")
        return f"{base} {' '.join(ctx)}".strip()

def setup_logging(debug: bool = False) -> logging.Logger:
    logger = logging.getLogger(APP_NAME)
    if logger.handlers:
        return logger  # already configured

    level = logging.DEBUG if debug or os.getenv("COLLECTORKING_DEBUG") == "1" else logging.INFO
    logger.setLevel(level)

    file_log, json_log = get_log_paths()

    # Console handler
    ch = logging.StreamHandler()
    ch.setLevel(level)
    ch.setFormatter(_KVFormatter(
        fmt="%(asctime)s %(levelname)s %(name)s %(module)s:%(lineno)d - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    ))

    # Rotating file handler (readable)
    fh = logging.handlers.RotatingFileHandler(
        file_log, maxBytes=10_000_000, backupCount=5, encoding="utf-8"
    )
    fh.setLevel(level)
    fh.setFormatter(_KVFormatter(
        fmt="%(asctime)s %(levelname)s %(name)s %(module)s:%(lineno)d - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    ))

    # Optional JSONL file for structured parsing
    jh = logging.handlers.RotatingFileHandler(
        json_log, maxBytes=10_000_000, backupCount=5, encoding="utf-8"
    )
    jh.setLevel(level)
    jh.setFormatter(logging.Formatter(
        # simple JSONL without extra deps
        fmt='{"ts":"%(asctime)s","lvl":"%(levelname)s","logger":"%(name)s",'
            '"module":"%(module)s","line":%(lineno)d,'
            '"msg":"%(message)s","run_id":"%(run_id)s","import_file":"%(import_file)s",'
            '"item_count":"%(item_count)s","user":"%(user)s"}',
        datefmt="%Y-%m-%dT%H:%M:%S"
    ))

    logger.addHandler(ch)
    logger.addHandler(fh)
    logger.addHandler(jh)

    # Be quiet noisy libs unless you want full debug
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("botocore").setLevel(logging.WARNING)
    logging.getLogger("azure").setLevel(logging.WARNING)
    return logger
