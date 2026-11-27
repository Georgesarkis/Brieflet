"""How a bench command ended. The CLI turns it into the process exit code."""
from enum import IntEnum


class Outcome(IntEnum):
    OK = 0
    REFUSED = 2          # money gate, missing price, missing learning pass: nothing ran
    BUDGET_STOP = 3      # the next run could pass max_usd
    ERROR_STOP = 4       # 3 errors in a row (usually a usage limit): continue later with --resume
