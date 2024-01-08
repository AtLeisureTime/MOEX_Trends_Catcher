""" All constants used in multiple files of candles app."""

MOEX_URL = 'http://iss.moex.com/'
MOEX_TZ = 'Europe/Moscow'
MOEX_DATE_FORMAT = '%Y-%m-%d %H:%M:%S'
MOEX_DATE_FORMAT_TZ = '%Y-%m-%d %H:%M:%S %Z'
MOEX_COLS = ["open", "close", "high", "low", "value", "volume", "begin", "end"]
MOEX_COL_O, MOEX_COL_C, MOEX_COL_H, MOEX_COL_L, _, _, MOEX_COL_DT_BEGIN, MOEX_COL_DT_END = \
    range(len(MOEX_COLS))
MOEX_DATA_MAX_LEN = 500
MOEX_SECURITY_LIST_URL = 'http://iss.moex.com/iss/engines/stock/markets/shares/boards/TQBR/securities'\
    '.json?iss.meta=off&iss.only=securities,marketdata&securities.columns=SECID,SHORTNAME'\
    '&marketdata.columns=ISSUECAPITALIZATION,ISSUECAPITALIZATION_UPDATETIME'
MOEX_SECURITY_COLS = ['SECID', 'SHORTNAME']
MOEX_MARKETDATA_COLS = ['ISSUECAPITALIZATION', 'ISSUECAPITALIZATION_UPDATETIME']
IMOEX_INDEX_URL = 'http://iss.moex.com/iss/engines/stock/markets/index/securities/IMOEX/candles'\
    '.json??iss.meta=off&iss.reverse=true&interval={0}'

# the order of writing 2 values of the same time period to a time series
RULE_HL = 'HL'  # high, low
RULE_LH = 'LH'  # low, high
RULE_OC = 'OC'  # open, close
