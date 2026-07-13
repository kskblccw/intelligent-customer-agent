#进行日志管理
import logging
from logging.handlers import RotatingFileHandler
import os
from utils.pyth_tool import get_abs_path


#日志保存的根目录
LOG_ROOT = get_abs_path("logs")
LOG_MAX_BYTES = 10 * 1024 * 1024  # 单文件最大 10MB
LOG_BACKUP_COUNT = 9              # 保留最近 10 个轮转文件（含当前）

#确保日志的目录存在
os.makedirs(LOG_ROOT, exist_ok=True)

#日志的格式配置 error info debug
DEFAULT_LOG_FORMAT = logging.Formatter(
    '%(asctime)s %(name)-12s %(levelname)-8s - %(filename)s:%(lineno)d -  %(message)s',
)

def get_logger(
        name:str = 'agent',
        console_level:int = logging.INFO,
        file_level:int = logging.DEBUG,
        log_file = None,
) -> logging.Logger:
    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)

    if logger.handlers:
        return logger

    #控制台Handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(console_level)
    console_handler.setFormatter(DEFAULT_LOG_FORMAT)
    logger.addHandler(console_handler)

    #文件Handler — 固定文件名，按大小自动轮转，超出 backupCount 自动删除最旧的
    if not log_file:
        log_file = os.path.join(LOG_ROOT, 'agent.log')

    file_handler = RotatingFileHandler(
        log_file, encoding='utf-8',
        maxBytes=LOG_MAX_BYTES,
        backupCount=LOG_BACKUP_COUNT,
    )
    file_handler.setLevel(file_level)
    file_handler.setFormatter(DEFAULT_LOG_FORMAT)
    logger.addHandler(file_handler)

    return logger


#快捷获取日志处理器
logger = get_logger()

if __name__ == '__main__':
    logger.info('信息日志')
    logger.debug('调试日志')
    logger.error('错误日志')
    logger.warning('警告日志')

