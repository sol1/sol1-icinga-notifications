from loguru import logger

def initLogger(log_disable_file = False, log_level = "INFO", log_file = "/var/log/icinga2/notification_script.log", rotate = '1 day', retention = '2 days'):
    format = "<blue>{time:YYYY-MM-DD HH:mm:ss.SSS}</blue> <level>{level}</level>: {message}",
    if log_level == "DEBUG" and not log_disable_file:
        format = "<blue>{time:YYYY-MM-DD HH:mm:ss.SSS}</blue> <cyan>{function}</cyan>:<cyan>{line}</cyan> <level>{level}</level>: {message}",
    else:
        logger.remove()
    if not log_disable_file:
        logger.add(log_file,
                   colorize=True,
                   format=format,
                   level=log_level,
                   rotation=rotate,
                   retention=retention,
                   compression="gz"
                   )