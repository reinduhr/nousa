import logging
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path

def setup_logging(log_dir='/code/data/log', level=logging.DEBUG):
    # Set global log level
    logging.basicConfig(encoding='utf-8', level=level)
    
    # Silence specific libraries
    logging.getLogger('sqlalchemy.engine').setLevel(logging.WARN)
    logging.getLogger('apscheduler').setLevel(logging.DEBUG)

    try:
        log_path = Path(log_dir)
        log_path.mkdir(parents=True, mode=0o770, exist_ok=True)
        file_handler = TimedRotatingFileHandler(
            str(log_path / 'nousa.log'),
            when='midnight',
            interval=7,
            backupCount=12,
            encoding='utf-8'
        )

        formatter = logging.Formatter(
            '%(asctime)s.%(msecs)03d - %(name)s - %(levelname)s - %(message)s',
            datefmt='%d-%b-%Y %H:%M:%S'
        )
        file_handler.setFormatter(formatter)
        logging.root.addHandler(file_handler)

    except Exception as err:
        logging.error(f"can't open log: {err}")

def delete_files_not_in_use():
    # delete unused files
    old_log_file = Path('/code/data/nousa.log')
    old_calendar_file = Path('/code/data/nousa.ics')
    old_audit_file = Path('/code/data/log/audit.log')
    if old_log_file.is_file():
        old_log_file.unlink()
    if old_calendar_file.is_file():
        old_calendar_file.unlink()
    if old_audit_file.is_file():
        old_audit_file.unlink()