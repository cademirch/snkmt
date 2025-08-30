from enum import Enum


class Status(Enum):
    RUNNING = "RUNNING"
    SUCCESS = "SUCCESS"
    ERROR = "ERROR"
    UNKNOWN = "UNKNOWN"


class FileType(Enum):
    INPUT = "INPUT"
    OUTPUT = "OUTPUT"
    LOG = "LOG"
    BENCHMARK = "BENCHMARK"
