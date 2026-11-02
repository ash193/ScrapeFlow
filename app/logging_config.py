import logging
import os
import sys

def configure_logging():
    """
    Configure consistent application logging.
    Logs are written to stdout so Docker can collect them
    """
    
    # read the log level from the env
    # default to INFO for normal application operation
    log_level = os.getenv("LOG_LEVEL", "INFO").upper()
    
    # configure the root logger
    logging.basicConfig(
        level=getattr(logging, log_level, logging.INFO),
        format=(
            "%(asctime)s | %(levelname)s | "
            "%(name)s | %(message)s"
        ),
        stream=sys.stdout,
        force=True
    )