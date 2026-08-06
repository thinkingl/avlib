import logging
import os
from datetime import datetime

def setup_logger(name='avlib', log_dir=None):
    """设置日志配置"""
    log_dir = log_dir or os.environ.get('AVLIB_LOG_DIR', 'logs')

    # 创建日志目录
    os.makedirs(log_dir, exist_ok=True)

    # 创建logger
    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)

    # 避免重复添加handler
    if logger.handlers:
        return logger

    # 控制台handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_format = logging.Formatter(
        '%(asctime)s [%(levelname)s] %(message)s',
        datefmt='%H:%M:%S'
    )
    console_handler.setFormatter(console_format)

    # 文件handler - 所有日志
    log_file = os.path.join(log_dir, f'avlib_{datetime.now().strftime("%Y%m%d")}.log')
    file_handler = logging.FileHandler(log_file, encoding='utf-8')
    file_handler.setLevel(logging.DEBUG)
    file_format = logging.Formatter(
        '%(asctime)s [%(levelname)s] [%(name)s:%(funcName)s:%(lineno)d] %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    file_handler.setFormatter(file_format)

    # 错误文件handler
    error_file = os.path.join(log_dir, f'error_{datetime.now().strftime("%Y%m%d")}.log')
    error_handler = logging.FileHandler(error_file, encoding='utf-8')
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(file_format)

    # 添加handlers
    logger.addHandler(console_handler)
    logger.addHandler(file_handler)
    logger.addHandler(error_handler)

    return logger

# 创建全局logger
logger = setup_logger()
