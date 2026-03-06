
# This is a swiss cheese function for the log file to ensure notifications don't fail due to log file permission issues. 
def _safe_log_file(log_file):
    import os
    log_dir = os.path.dirname(log_file)
    # Check if the file exists and is writable, or if the directory is writable for a new file
    if os.path.exists(log_file):
        writable = os.access(log_file, os.W_OK)
    else:
        if not log_dir:
            log_dir = '.'
        writable = os.access(log_dir, os.W_OK)
    # If not writeable add the user id to the log file name to attempt to create a unique log file for the user
    if not writable:
        uid = os.getuid() if hasattr(os, 'getuid') else os.getlogin()
        base, ext = os.path.splitext(log_file)
        log_file = f"{base}-{uid}{ext}"
    return (log_file, writable)


def initLogger(log_disable_file = False, log_level = "INFO", log_file = "/var/log/icinga2/notification_script.log", rotate = '1 day', retention = '2 days'):
    from loguru import logger
    format = "<blue>{time:YYYY-MM-DD HH:mm:ss.SSS}</blue> <yellow>({process.id})</yellow> <level>{level}</level>: {message}"
    if log_level == "DEBUG" and not log_disable_file:
        format = "<blue>{time:YYYY-MM-DD HH:mm:ss.SSS}</blue> <yellow>({process.id})</yellow> <cyan>{function}</cyan>:<cyan>{line}</cyan> <level>{level}</level>: {message}"
    else:
        logger.remove()
    if log_disable_file:
        return True
    log_file, writable = _safe_log_file(log_file)
    try:
        logger.add(log_file,
                colorize=True,
                format=format,
                level=log_level,
                rotation=rotate,
                retention=retention,
                compression="gz"
                )
    except Exception as e:
        import sys
        logger.add(sys.stdout,
                colorize=True,
                format=format,
                level=log_level,
                )
        writable = False
        logger.error(f"Failed to initialize log file ({log_file}), error: {e}")
    return writable

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
