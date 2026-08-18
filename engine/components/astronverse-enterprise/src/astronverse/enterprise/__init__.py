"""Enterprise module initialization"""

from enum import Enum

from astronverse.enterprise.enterprise import Enterprise


class ReportLevelType(Enum):
    """Report level types"""

    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
