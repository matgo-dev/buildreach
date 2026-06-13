"""脚本日志初始化 — 终端 + 文件双写。

日志文件存 backend/logs/<script_name>_<timestamp>.log,按运行时间命名。
"""
from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path

_LOGS_DIR = Path(__file__).resolve().parent.parent / "logs"


def setup_logging(script_name: str) -> Path:
    """初始化 logging:终端(简洁) + 文件(带日期)。返回日志文件路径。"""
    _LOGS_DIR.mkdir(exist_ok=True)

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = _LOGS_DIR / f"{script_name}_{ts}.log"

    # 终端:简洁,不带日期(当天能看到)
    console = logging.StreamHandler()
    console.setLevel(logging.INFO)
    console.setFormatter(logging.Formatter(
        "%(asctime)s [%(levelname)s] %(message)s", datefmt="%H:%M:%S",
    ))

    # 文件:带完整日期
    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s — %(message)s", datefmt="%Y-%m-%d %H:%M:%S",
    ))

    logging.basicConfig(level=logging.INFO, handlers=[console, file_handler])

    logging.getLogger(script_name).info("日志文件: %s", log_file)
    return log_file
