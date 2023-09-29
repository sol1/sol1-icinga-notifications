
def initLogger(log_disable_file = False, log_level = "INFO", log_file = "/var/log/icinga2/notification_script.log", rotate = '1 day', retention = '2 days'):
    from loguru import logger
    format = "<blue>{time:YYYY-MM-DD HH:mm:ss.SSS}</blue> <yellow>({process.id})</yellow> <level>{level}</level>: {message}"
    if log_level == "DEBUG" and not log_disable_file:
        format = "<blue>{time:YYYY-MM-DD HH:mm:ss.SSS}</blue> <yellow>({process.id})</yellow> <cyan>{function}</cyan>:<cyan>{line}</cyan> <level>{level}</level>: {message}"
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

def initRequestsCache(cache_file, expire_after = 30):
    """_summary_

    Args:
        cache_file (str): full path to cache file
        expire_after (int, optional): seconds till the cache expires. Defaults to 30.

    Returns:
        tuple: (bool, str) the boolan value is success/failure, the string is the message
    """    
    import requests_cache
    import os
    if os.path.isfile(cache_file):
        if not os.access(cache_file, os.W_OK):
            return (False, f"Permissions error, unable to write to requests cache file ({cache_file})")

    backend = requests_cache.SQLiteCache(cache_file, check_same_thread=False)
    requests_cache.install_cache(cache_file, backend=backend, expire_after=expire_after)
    requests_cache.patcher.remove_expired_responses()
    return (True, f'Successfully initalized requests cache file ({cache_file})')
