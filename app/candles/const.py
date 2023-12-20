""" All constants used in multiple files of candles app."""

MOEX_URL = 'http://iss.moex.com/'
MOEX_TZ = 'Europe/Moscow'
MOEX_DATE_FORMAT = '%Y-%m-%d %H:%M:%S'
MOEX_DATE_FORMAT_TZ = '%Y-%m-%d %H:%M:%S %Z'
MOEX_COLS = ["open", "close", "high", "low", "value", "volume", "begin", "end"]
MOEX_COL_O, MOEX_COL_C, MOEX_COL_H, MOEX_COL_L, _, _, MOEX_COL_DT_BEGIN, MOEX_COL_DT_END = \
    range(len(MOEX_COLS))
MOEX_DATA_MAX_LEN = 500

# the order of writing 2 values of the same time period to a time series
RULE_HL = 'HL'  # high, low
RULE_LH = 'LH'  # low, high
RULE_OC = 'OC'  # open, close
