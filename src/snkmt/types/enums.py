from enum import Enum


class Status(Enum):
    RUNNING = "RUNNING"
    SUCCESS = "SUCCESS"
    ERROR = "ERROR"
    UNKNOWN = "UNKNOWN"


class DateFilter(Enum):
    ANY = "any"
    TODAY = "today"
    YESTERDAY = "yesterday"
    LAST_7_DAYS = "week"
    LAST_30_DAYS = "month"
    LAST_90_DAYS = "quarter"
    THIS_YEAR = "year"


class FileType(Enum):
    INPUT = "INPUT"
    OUTPUT = "OUTPUT"
    LOG = "LOG"
    BENCHMARK = "BENCHMARK"
