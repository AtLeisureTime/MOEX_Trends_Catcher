"""
Detection of best long and short deals and calculations of its returns.
"""
import bisect
import datetime
import logging
import typing
import zoneinfo
from . import const

logger = logging.getLogger('custom_debug')


def getTSMaxMinInds(ts: list[float | int]) -> tuple[list[int], list[int]]:
    """ Get indices of local mins and maxes in time series.
        Mins and maxs alternate, maxs[i] < mins[i], len(maxs) = len(mins).
    Args:
        ts (list[float | int]): time series
    Returns:
        tuple[list[int], list[int]]: (indices of maxs, indices of mins)
    """
    mins, maxs = [], []
    prevMinInd = prevMaxInd = 0
    for i in range(1, len(ts)):
        if len(mins) == len(maxs):
            if ts[i] >= ts[prevMaxInd]:
                prevMaxInd = i
                continue
            maxs.append(prevMaxInd)
            prevMinInd = i
        else:
            if ts[i] <= ts[prevMinInd]:
                if ts[i] < ts[prevMinInd]:
                    prevMinInd = i
                continue
            mins.append(prevMinInd)
            prevMaxInd = i
    if len(mins) != len(maxs):
        if maxs[-1] != prevMinInd:
            mins.append(prevMinInd)
        else:
            maxs = maxs[:-1]
    return maxs, mins


def getTSMinMaxInds(ts: list[float | int]) -> tuple[list[int], list[int]]:
    """ Get indices of local mins and maxes in time series.
        Mins and maxs alternate, maxs[i] > mins[i], len(maxs) = len(mins).
    Args:
        ts (list[float | int]): time series
    Returns:
        tuple[list[int], list[int]]: (indices of local mins, indices of local maxs)
    """
    mins, maxs = [], []
    prevMinInd = prevMaxInd = 0
    for i in range(1, len(ts)):
        if len(mins) == len(maxs):
            if ts[i] <= ts[prevMinInd]:
                prevMinInd = i
                continue
            mins.append(prevMinInd)
            prevMaxInd = i
        else:
            if ts[i] >= ts[prevMaxInd]:
                if ts[i] > ts[prevMaxInd]:
                    prevMaxInd = i
                continue
            maxs.append(prevMaxInd)
            prevMinInd = i
    if len(mins) != len(maxs):
        if mins[-1] != prevMaxInd:
            maxs.append(prevMaxInd)
        else:
            mins = mins[:-1]
    return mins, maxs


def getFlattenPrices(data: list[list], rule: str) -> list[float]:
    """ Get 2 price values from every row of 2D MOEX response list, flatten result.
    Args:
        data (list[list]): 2D MOEX response list, columns of inner list are in const.MOEX_COLS
        rule (str): the order of writing 2 values of the same time period to a time series
                    Values: const.RULE_*
    Raises:
        ValueError: incorrect value of rule param
    Returns:
        list[float]: prices, len(prices) = len(data) * 2 
    """
    if rule == const.RULE_HL:
        return [el for row in data
                for el in (row[const.MOEX_COL_H], row[const.MOEX_COL_L])]
    if rule == const.RULE_LH:
        return [el for row in data
                for el in (row[const.MOEX_COL_L], row[const.MOEX_COL_H])]
    if rule == const.RULE_OC:
        return [el for row in data
                for el in (row[const.MOEX_COL_O], row[const.MOEX_COL_C])]
    raise ValueError(f'Unknown value of rule param: {rule}')


def getFlattenDatetimes(data: list[list], startTime: datetime.datetime)\
        -> tuple[list[datetime.datetime], int]:
    """ Get 2 datetime values from every row of 2D MOEX response list, flatten result.
    Args:
        data (list[list]): 2D MOEX response list, columns of inner list are in const.MOEX_COLS
        startTime (datetime.datetime): first datetime in result
    Returns:
        tuple[list[datetime.datetime], int]: (price datetimes, index of startTime in input data)
    """
    moexTz = zoneinfo.ZoneInfo(const.MOEX_TZ)
    startTime = startTime.astimezone(moexTz)
    res = [datetime.datetime.strptime(dt, const.MOEX_DATE_FORMAT).replace(tzinfo=moexTz)
           for row in data
           for dt in (row[const.MOEX_COL_DT_BEGIN], row[const.MOEX_COL_DT_END])]

    startInd = bisect.bisect_left(res, startTime, 0)
    if startInd % 2:
        startInd += 1  # because we can use both datimes values from data row or none of them
    return res[startInd:], startInd


def largeNumsToScientificNotation(data: typing.Any) -> typing.Any:
    """ Transform all too large numbers in data to short str with numbers in scientific notation.
    Args:
        data (typing.Any): any data
    Returns:
        typing.Any: input data where all large numbers were replaced by short str
    """
    if isinstance(data, typing.Union[list, tuple]):
        return tuple(largeNumsToScientificNotation(elem) for elem in data)
    if isinstance(data, typing.Union[int, float]) and data > 1e10:
        return '{:.4e}'.format(data)
    return data


def calcReturn(
        priceIn: float, priceOut: float, avgPrice: float, short: bool,
        feeIn: float, feeOut: float, loanFee: float,
        dateIn: datetime.datetime, dateOut: datetime.datetime) -> tuple[float, float, float]:
    """ Calculate 3 returns: return per deal, return per year without reinvesting,
                             return per year with reinvesting of profit
    Args:
        priceIn (float): deal opening (buy for long deal / sell for short) price
        priceOut (float): deal closing (sell / buy) price
        avgPrice: (float): average price during the deal
        short (bool): is deal short
        feeIn (float): fee for deal opening, %
        feeOut (float): fee for deal closing, %
        loanFee (float): loan fee for short deal, %
        dateIn (datetime.datetime): datetime of deal opening
        dateOut (datetime.datetime): datetime of deal closing
    Returns:
        tuple[float, float, float]: 3 returns
    """
    if short:
        assert dateOut > dateIn
        loanFees = ((1. + loanFee / 100. / 365) ** (dateOut - dateIn).days - 1.) * avgPrice
        fees = (feeIn * priceOut + feeOut * priceIn) / 100.0 + loanFees
    else:
        fees = (feeIn * priceIn + feeOut * priceOut) / 100.0

    # per deal
    if short:
        r = (priceIn - priceOut - fees) / priceOut
    else:
        r = (priceOut - priceIn - fees) / priceIn

    yearPart = max(dateOut - dateIn, datetime.timedelta(days=1)) / datetime.timedelta(days=365)
    r1 = r / yearPart  # w/o reinvesting of profit
    r2 = (1. + r) ** (1. / yearPart) - 1.  # with reinvesting of profit
    return r, r1, r2


def findBestReturnFor1Deal(
    prices: list[float], dates: list[datetime.datetime], rule: str, short: bool,
    isPerYear: bool, feeIn: float, feeOut: float, loanFee: float)\
        -> tuple[float, float, float] | None:
    """ Find best tuple of 3 returns for 1 deal composed from 1 buy and 1 sell operations
        for long deal and 1 sell and 1 buy operations for short deal.
        The base return for detection of the most profitable deal is 'return per deal'
        or 'return per year without reinvesting of profit' (it depends on isPerYear param).
    Args:
        prices (list[float]): price time series
        dates (list[datetime.datetime]): price datetimes
        rule (str): the order of writing 2 values of the same time period to a time series
                    Values: const.RULE_*
        short (bool): is deal short
        isPerYear (bool): is 'return per year without reinvesting of profit' is base for detection
                          of the most profitable deal in time series
        feeIn (float): fee for deal opening, %.
        feeOut (float): fee for deal closing, %.
        loanFee (float): loan fee for short deal, %.
    Returns:
        tuple[float, float, float] | None: 3 returns from calcReturn function
    """
    baseRI = 1 if isPerYear else 0  # base return index
    res = None
    if short:
        maxInds, minInds = getTSMaxMinInds(prices)
        for i, _maxI in enumerate(maxInds):
            for _minI in minInds[i:]:
                datesInOut = (None, None)
                if dates:
                    d1I, d2I = _maxI, _minI
                    if rule in {const.RULE_HL, const.RULE_LH}:
                        # worst case
                        if d1I % 2:
                            d1I -= 1
                        if d2I % 2 == 0:
                            d2I += 1
                    datesInOut = (dates[d1I], dates[d2I])
                ts = prices[_maxI:_minI+1]
                tsAvgPrice = sum(ts) / len(ts)
                rArr = calcReturn(prices[_maxI], prices[_minI], tsAvgPrice, short,
                                  feeIn, feeOut, loanFee, *datesInOut)
                if res is None or rArr[baseRI] > res[baseRI]:
                    res = (*rArr, _maxI, _minI)
    else:
        minInds, maxInds = getTSMinMaxInds(prices)
        for i, _minI in enumerate(minInds):
            for _maxI in maxInds[i:]:
                datesInOut = (None, None)
                if dates:
                    d1I, d2I = _minI, _maxI
                    if rule in {const.RULE_HL, const.RULE_LH}:
                        # worst case
                        if d1I % 2:
                            d1I -= 1
                        if d2I % 2 == 0:
                            d2I += 1
                    datesInOut = (dates[d1I], dates[d2I])
                rArr = calcReturn(prices[_minI], prices[_maxI], None, short,
                                  feeIn, feeOut, loanFee, *datesInOut)
                if res is None or rArr[baseRI] > res[baseRI]:
                    res = (*rArr, _minI, _maxI)
    return res


def toStr(date: datetime.datetime) -> str:
    """ Transform MOEX datetime to str with MOEX time zone
    Args:
        date (datetime.datetime): datetime from MOEX response
    Returns:
        str: str with MOEX time zone
    """
    return datetime.datetime.strftime(date, const.MOEX_DATE_FORMAT_TZ)


def returnRepr(prices: list[float], dates: list[datetime.datetime],
               res: tuple[float, float, float], rule: str, security: str)\
        -> tuple[float, float, float, str, str, float, str, float, str]:
    """ Prepare 1 row for tables in return calculation results template.
    Args:
        prices (list[float]): price time series
        dates (list[datetime.datetime]): price datetimes
        res (tuple[float, float, float]): 3 returns from calcReturn function
        rule (str): the order of writing 2 values of the same time period to a time series
                    Values: const.RULE_*
        security (str): ticker symbol of security
    Raises:
        ValueError: incorrect value of rule param
    Returns:
        tuple[float, float, float, str,
              str, float, str, float, str]:
            3 returns from calcReturn function, ticker symbol of security,
            buy/sell time, buy/sell price, sell/buy time, sell/buy price, data time period
    """
    dealReturn, woReinvest, withReinvest = (round(r * 100., 4) for r in res[:3])  # profit, %
    inI, outI = res[3], res[4]

    dateIn, dateOut = toStr(dates[inI]), toStr(dates[outI])
    if rule in {const.RULE_HL, const.RULE_LH}:
        dateIn = f'{toStr(dates[inI - 1])} - {toStr(dates[inI])}' if inI % 2 else \
            f'{toStr(dates[inI])} - {toStr(dates[inI + 1])}'
        dateOut = f'{toStr(dates[outI - 1])} - {toStr(dates[outI])}' if outI % 2 else \
            f'{toStr(dates[outI])} - {toStr(dates[outI + 1])}'
    elif rule != const.RULE_OC:
        ValueError(f'Unknown value of rule param: {rule}')
    dataTimePeriod = f'{toStr(dates[0])} - {toStr(dates[-1])}'
    return (woReinvest, withReinvest, dealReturn, security, dateIn, prices[inI],
            dateOut, prices[outI], dataTimePeriod)


def findBestLongShort1DealReturns(
        data: list[list], rule: str, startTime: datetime.datetime, security: str, isPerYear: bool,
        feeIn: float = 0.0, feeOut: float = 0.0, loanFee: float = 0.0) -> list[tuple, tuple]:
    """ Find 1 best long deal and 1 best short deal for security based on input data
        from MOEX (data are transformed using rule and startTime params), 
        calculate for them tuple of 3 returns (see what calcReturn() returns) using fees
        and isPerYear params, return rows for tables in template.
    Args:
        data (list[list]): 2D MOEX response list, columns of inner list are in const.MOEX_COLS
        rule (str): the order of writing 2 values of the same time period to a time series
                    Values: const.RULE_*
        startTime (datetime.datetime): discard all data with datetimes < startTime
        security (str): ticker symbol of security
        isPerYear (bool): is 'return per year without reinvesting of profit' is base for detection
                          of the most profitable deal in time series
        feeIn (float, optional): fee for deal opening, %. Defaults to 0.0.
        feeOut (float, optional): fee for deal closing, %. Defaults to 0.0.
        loanFee (float, optional): loan fee for short deal, %. Defaults to 0.0.
    Returns:
        list[tuple, tuple]: every element is (long deal row from returnRepr(),
                                              short deal row from returnRepr())
    """
    if not data or not data[0]:
        return [(), ()]
    res = []
    dates, startInd = getFlattenDatetimes(data, startTime)
    if startInd == len(data) * 2:
        return [(), ()]
    for short in (False, True):
        if rule == const.RULE_LH and not short:
            rule = const.RULE_HL
        elif rule == const.RULE_HL and short:
            rule = const.RULE_LH
        prices = getFlattenPrices(data[startInd // 2:], rule)
        logger.debug(f'{security=} {len(dates)=}, {len(prices)=}')
        returnInOut = findBestReturnFor1Deal(prices, dates, rule, short, isPerYear,
                                             feeIn, feeOut, loanFee)
        reprDict = returnRepr(prices, dates, returnInOut, rule, security) if returnInOut else None
        res.append(reprDict)
    return res
