"""
Detection of best long and short deals and calculations of its returns.
"""
import bisect
import datetime
import logging
import math
import statistics
import typing
import zoneinfo
from . import const

EPS = 1e-12  # min value of denominator
RATIO_NONE = -1e3  # negative number that means ratio can't be calculated
# if abs(number) >= this const then it will be displayedin scientific notation
SCIENT_MIN_LARGE_NUM = 1e6
# if abs(number) <= this const then it will be displayed in scientific notation
SCIENT_MAX_SMALL_NUM = 1e-6
YEAR_TD = datetime.timedelta(seconds=31556952)  # 365,2425 days

logger = logging.getLogger('custom_debug')


def roundToNSignif(num: float | int, numDigits: int = 4) -> float | int:
    """ Round 'num' to 'numDigits' significant digits.
    Args:
        num (float | int): number to round
        numDigits (int, optional): number of significant digits. Defaults to 4.
    Returns:
        float | int: rounded number
    """
    if abs(num) < EPS or not math.isfinite(num):
        return num
    numDigits -= math.ceil(math.log10(abs(num)))
    return round(num, numDigits)


def shortenLongNumbers(data: typing.Any) -> typing.Any:
    """ Transform all too large numbers in data to short str with numbers in scientific notation.
    Args:
        data (typing.Any): any data
    Returns:
        typing.Any: input data where all large numbers were replaced by short str
    """
    if isinstance(data, list | tuple):
        return tuple(shortenLongNumbers(elem) for elem in data)
    if isinstance(data, int | float):
        if abs(data - RATIO_NONE) < EPS:
            return '-'
        if abs(data) >= SCIENT_MIN_LARGE_NUM:
            return f'{data:.4e}'
        if abs(data) <= SCIENT_MAX_SMALL_NUM:
            return f'{data:.4e}'
        return roundToNSignif(data)
    return data


def calcYearPart(firstDt: datetime.datetime, lastDt: datetime.datetime) -> float:
    """ Calculate what part of the year the period since 'firstDt' till 'lastDt' lasts for.
        Minimal period length is 1 day.
    Args:
        firstDt (datetime.datetime): first datetime in the period
        lastDt (datetime.datetime): last datetime in the period
    Returns:
        float: a part of the year the period lasts for
    """
    return max(lastDt - firstDt, datetime.timedelta(days=1)) / YEAR_TD


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


def getFlattenDatetimes(data: list[list], startTime: datetime.datetime,
                        endTime: datetime.datetime | None = None)\
        -> tuple[list[datetime.datetime], int, int]:
    """ Get 2 datetime values from every row of 2D MOEX response list, flatten result.
    Args:
        data (list[list]): 2D MOEX response list, columns of inner list are in const.MOEX_COLS
        startTime (datetime.datetime): first datetime in result
        endTime (datetime.datetime | None, optional): last datetime in result. Defaults to None.
    Returns:
        tuple[list[datetime.datetime], int, int]:
        (price datetimes, index of startTime in input data, index of endTime in input data)
    """
    moexTz = zoneinfo.ZoneInfo(const.MOEX_TZ)
    startTime = startTime.astimezone(moexTz)
    res = [datetime.datetime.strptime(dt, const.MOEX_DATE_FORMAT).replace(tzinfo=moexTz)
           for row in data
           for dt in (row[const.MOEX_COL_DT_BEGIN], row[const.MOEX_COL_DT_END])]

    startInd = bisect.bisect_left(res, startTime, 0)
    if startInd % 2:
        startInd += 1  # because we can use both datimes values from data row or none of them
    endInd = len(res)
    if endTime:
        endInd = bisect.bisect_right(res, endTime)
        if endInd % 2:
            endInd += 1
    return res[startInd:endInd], startInd, endInd


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

    yearPart = calcYearPart(dateIn, dateOut)
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


def toRowRepr(prices: list[float], dates: list[datetime.datetime],
              res: tuple[float, float, float], rule: str, security: str, ratios: list[float])\
        -> tuple[float, float, float, str, str, float, str, float, str,
                 float, float, float, float, float, float, float, float, float, float, float]:
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
        tuple[float, float, float, str, str, float, str, float, str,
              float, float, float, float, float, float, float, float, float, float, float]:
            3 returns from calcReturn function, ticker symbol of security,
            buy/sell time, buy/sell price, sell/buy time, sell/buy price, data time period,
            11 ratios values.
    """
    dealReturn, woReinvest, withReinvest = (ret * 100. for ret in res[:3])  # profit, %
    inI, outI = res[3], res[4]

    dateIn, dateOut = toStr(dates[inI]), toStr(dates[outI])
    if rule in {const.RULE_HL, const.RULE_LH}:
        dateIn = f'{toStr(dates[inI - 1])} - {toStr(dates[inI])}' if inI % 2 else \
            f'{toStr(dates[inI])} - {toStr(dates[inI + 1])}'
        dateOut = f'{toStr(dates[outI - 1])} - {toStr(dates[outI])}' if outI % 2 else \
            f'{toStr(dates[outI])} - {toStr(dates[outI + 1])}'
    elif rule != const.RULE_OC:
        raise ValueError(f'Unknown value of rule param: {rule}')
    dataTimePeriod = f'{toStr(dates[0])} - {toStr(dates[-1])}'

    return (woReinvest, withReinvest, dealReturn, security, dateIn, prices[inI],
            dateOut, prices[outI], dataTimePeriod, *ratios)


def calcSharpeRatio(assetReturns: list[float], riskFreeReturn: float = 0.0) -> float:
    if len(assetReturns) < 2:
        return RATIO_NONE
    denom = statistics.stdev(assetReturns)
    denom = max(denom, EPS)
    diffs = [assetReturn - riskFreeReturn for assetReturn in assetReturns]
    return statistics.fmean(diffs) / denom


def calcSortinoRatio(assetReturns: list[float], riskFreeReturn: float = 0.0) -> float:
    diffs = [assetReturn - riskFreeReturn for assetReturn in assetReturns]
    downsideReturns = list(filter(lambda r: r < riskFreeReturn, assetReturns))
    if len(downsideReturns) < 2:
        return RATIO_NONE
    denom = statistics.stdev(downsideReturns)
    denom = max(denom, EPS)
    return statistics.fmean(diffs) / denom


def calcMaxDrawdown(assetReturns: list[float]) -> float:
    if not assetReturns:
        return RATIO_NONE
    return min(assetReturns)


def calcCalmarRatio(assetReturns: list[float], maxDrawdown: float, riskFreeReturn: float = 0.0) \
        -> float:
    if abs(maxDrawdown - RATIO_NONE) < EPS:
        return RATIO_NONE
    diffs = [assetReturn - riskFreeReturn for assetReturn in assetReturns]
    if not diffs:
        return RATIO_NONE
    denom = max(abs(maxDrawdown), EPS)
    return statistics.fmean(diffs) / denom


def calcStddev(assetReturns: list[float]) -> float:
    if len(assetReturns) < 2:
        return RATIO_NONE
    return statistics.stdev(assetReturns)


def calcBeta(assetReturns: list[float], marketReturns: list[float]) -> float:
    if len(assetReturns) != len(marketReturns) or len(marketReturns) < 2:
        return RATIO_NONE
    denom = statistics.variance(marketReturns)
    denom = max(denom, EPS)
    return statistics.covariance(assetReturns, marketReturns) / denom


def calcAlpha(assetReturn: float | None, assetBeta: float, marketReturns: list[float],
              riskFreeReturn: float = 0.0) -> float:
    if not marketReturns or not assetReturn or abs(assetBeta - RATIO_NONE) < EPS:
        return RATIO_NONE
    marketReturn = max(marketReturns)
    return (assetReturn - riskFreeReturn) - assetBeta * (marketReturn - riskFreeReturn)


def calcTreynorRatio(assetReturn: float | None, assetBeta: float, riskFreeReturn: float = 0.0) \
        -> float:
    if not assetReturn or abs(assetBeta - RATIO_NONE) < EPS:
        return RATIO_NONE
    if assetBeta < 0.:
        denom = min(assetBeta, -EPS)
    else:
        denom = max(assetBeta, EPS)
    return (assetReturn - riskFreeReturn) / denom


def calcRsquared(assetReturns: list[float], marketReturns: list[float]) -> float:
    if len(assetReturns) != len(marketReturns) or not assetReturns:
        return RATIO_NONE
    ssRes = sum(((ra - rm) ** 2 for ra, rm in zip(assetReturns, marketReturns)))
    raMean = statistics.mean(assetReturns)
    ssTot = sum(((ra - raMean) ** 2 for ra in assetReturns))
    ssTot = max(ssTot, EPS)
    return 1. - ssRes / ssTot


def calcRsquared2(assetReturns: list[float], marketReturns: list[float]) -> float:
    """ https://www.titan.com/articles/what-is-r-squared
        https://groww.in/p/r-squared """
    if len(assetReturns) != len(marketReturns) or len(marketReturns) < 2:
        return RATIO_NONE
    denom = statistics.stdev(marketReturns) * statistics.stdev(assetReturns)
    denom = max(denom, EPS)
    cor = statistics.covariance(assetReturns, marketReturns) / denom
    return cor ** 2


def calcInformationRatio(assetReturns: list[float], marketReturns: list[float]) -> float:
    if len(assetReturns) != len(marketReturns):
        return RATIO_NONE
    activeReturns = [ra - rm for ra, rm in zip(assetReturns, marketReturns)]
    if len(activeReturns) < 2:
        return RATIO_NONE
    denom = statistics.stdev(activeReturns)
    denom = max(denom, EPS)
    return statistics.mean(activeReturns) / denom


def findBestLongShort1DealReturns(
        data: list[list], rule: str, startTime: datetime.datetime, security: str, isPerYear: bool,
        marketData: list[list], feeIn: float = 0.0, feeOut: float = 0.0, loanFee: float = 0.0,
        riskFreeReturn: float = 0.0
) -> list[tuple, tuple]:
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
        marketData (list[list]): 2D response list for IMOEX security,
                                 columns of inner list are in const.MOEX_COLS                  
        feeIn (float, optional): fee for deal opening, %. Defaults to 0.0.
        feeOut (float, optional): fee for deal closing, %. Defaults to 0.0.
        loanFee (float, optional): loan fee for short deal, %. Defaults to 0.0.
        riskFreeReturn (float, optional): risk free return, %. Defaults to 0.0.
    Returns:
        list[tuple, tuple]: every element is (long deal row from toRowRepr(),
                                              short deal row from toRowRepr())
    """
    if not data or not data[0]:
        return [(), ()]
    res = []
    dates, startInd, _ = getFlattenDatetimes(data, startTime)
    if not dates:
        return [(), ()]

    _, marketStartInd, marketEndInd = getFlattenDatetimes(marketData, dates[0], dates[-1])
    riskFreeReturn = riskFreeReturn * calcYearPart(dates[0], dates[-1])
    for short in (False, True):
        if rule == const.RULE_LH and not short:
            rule = const.RULE_HL
        elif rule == const.RULE_HL and short:
            rule = const.RULE_LH
        prices = getFlattenPrices(data[startInd // 2:], rule)
        marketPrices = getFlattenPrices(
            marketData[marketStartInd // 2: marketEndInd // 2], rule)
        if len(dates) == len(prices) == len(marketPrices):
            logger.debug(f'{security=}, {len(dates)=}, {len(prices)=}, {len(marketPrices)=}')
        else:
            logger.error(f'{security=}, {len(dates)=}, {len(prices)=}, {len(marketPrices)=}')
        returnInOut = findBestReturnFor1Deal(prices, dates, rule, short, isPerYear,
                                             feeIn, feeOut, loanFee)
        if len(prices) > 5:
            assetReturns = [(prices[j] / prices[i] - 1.) * 100.
                            for i in range(0, len(prices) - 1)
                            for j in range(i + 1, len(prices))]
            marketReturns = [(marketPrices[j] / marketPrices[i] - 1.) * 100.
                             for i in range(0, len(marketPrices) - 1)
                             for j in range(i + 1, len(marketPrices))]
            assetReturnPerDeal = returnInOut[0] * 100. if returnInOut else None

            sharpeRatio = calcSharpeRatio(assetReturns, riskFreeReturn)
            sortinoRatio = calcSortinoRatio(assetReturns, riskFreeReturn)
            maxDD = calcMaxDrawdown(assetReturns)
            calmarRatio = calcCalmarRatio(assetReturns, maxDD, riskFreeReturn)
            stdDev = calcStddev(assetReturns)
            beta = calcBeta(assetReturns, marketReturns)
            alpha = calcAlpha(assetReturnPerDeal, beta, marketReturns, riskFreeReturn)
            treynorRatio = calcTreynorRatio(assetReturnPerDeal, beta, riskFreeReturn)
            rSq1 = calcRsquared(assetReturns, marketReturns)
            rSq2 = calcRsquared2(assetReturns, marketReturns)
            informRatio = calcInformationRatio(assetReturns, marketReturns)
        else:
            sharpeRatio, sortinoRatio, maxDD, calmarRatio, stdDev, alpha, beta, treynorRatio, \
                rSq1, rSq2, informRatio = RATIO_NONE, RATIO_NONE, RATIO_NONE, RATIO_NONE, \
                RATIO_NONE, RATIO_NONE, RATIO_NONE, RATIO_NONE, RATIO_NONE, RATIO_NONE, RATIO_NONE
        reprDict = toRowRepr(
            prices, dates, returnInOut, rule, security,
            [sharpeRatio, sortinoRatio, maxDD, calmarRatio, stdDev, alpha, beta, treynorRatio,
             rSq1, rSq2, informRatio])\
            if returnInOut else None
        res.append(reprDict)
    return res
