#进行日志管理
import logging
import os
from pyth_tool import get_abs_path



#日志保存的根目录
LOG_ROOT = get_abs_path("logs")

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

    #避免重复添加Hander
    if logger.handlers:
        return logger