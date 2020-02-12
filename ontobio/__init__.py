from __future__ import absolute_import

__version__ = '1.15.3'

from .ontol_factory import OntologyFactory
from .ontol import Ontology, Synonym, TextDefinition
from .assoc_factory import AssociationSetFactory
from .io.ontol_renderers import GraphRenderer

import logging
import logging.handlers
from logging.config import dictConfig

DEFAULT_LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
}

def configure_logging():
    """
    Initialize logging defaults for Project.

    :param logfile_path: logfile used to the logfile
    :type logfile_path: string

    This function does:

    - Assign INFO and DEBUG level to logger file handler and console handler

    """
    dictConfig(DEFAULT_LOGGING)

    default_formatter = logging.Formatter(
        "%(asctime)s [%(levelname)s] [PID:%(process)d TID:%(thread)d] [%(filename)s:%(lineno)s in `%(funcName)s`]  %(message)s",
        "%Y-%m-%d %H:%M:%S")

    # file_handler = logging.handlers.RotatingFileHandler(logfile_path, maxBytes=10485760,backupCount=300, encoding='utf-8')
    # file_handler.setLevel(logging.INFO)

    console_handler = logging.getLogger().handlers[0]
    console_handler.setLevel(logging.DEBUG)
    console_handler.setFormatter(default_formatter)

    # file_handler.setFormatter(default_formatter)

    logging.root.setLevel(logging.WARNING)
    # logging.root.addHandler(file_handler)
    logging.root.addHandler(console_handler)
    
configure_logging()
