""" Celery tasks for tabs 'Settings of securities', 'Candles', 'Returns'."""
import datetime
import logging
import celery
import django.utils as dj_utils
from . import models, calculations as calc, const, download

logger = logging.getLogger('custom_debug')


@celery.shared_task
def findBestReturnsForAllSecurities(cleanedData: dict)\
        -> tuple[list[tuple], list[tuple], list[int], list[int], int]:
    """ Tries to extract time series from DB for every security, makes calculations of returns,
        generates rows for 2 tables in template.
    Args:
        cleanedData (dict): form cleaned data with parameters of task
    Returns:
        tuple[list[tuple], list[tuple], list[int], list[int], int]:
        rows for 2 template tables: long deals, short deals;
        models.FetchedData ids for long and short deals;
        index of column to order each template table.
    """
    minTime = dj_utils.timezone.now() - datetime.timedelta(seconds=cleanedData['duration'])
    qsBase = models.FetchedData.objects.select_related('fetch_setting', 'security')

    qs1 = qsBase.filter(data_last_dt__gt=minTime, data_first_dt__lte=minTime)\
        .order_by('security__security', '-data_last_dt')\
        .distinct('security__security').values_list(
            'id', 'security__security', 'data', 'fetch_setting__interval')

    # if we don't have long enough security time series for requested minTime
    qs2 = qsBase.filter(data_last_dt__gt=minTime)\
        .order_by('security__security', '-data_last_dt')\
        .distinct('security__security').values_list(
            'id', 'security__security', 'data', 'fetch_setting__interval')

    qs = qs1.union(qs2)

    res = []
    securityObjIdDict = {}
    for i, (objId, security, data, interval) in enumerate(qs):
        if i == 0:
            marketData, _, _, _, _, _, _ = \
                download.MOEX_Downloader.fetchData(
                    [const.IMOEX_INDEX_URL.format(str(interval))], 60)
        securityObjIdDict[security] = objId
        longReturns, shortReturns = calc.findBestLongShort1DealReturns(
            data, cleanedData['rule'], minTime, security, cleanedData['isPerYear'], marketData[0],
            cleanedData['feeIn'], cleanedData['feeOut'], cleanedData['loanFee'],
            cleanedData['riskFreeReturn'])
        res.append([longReturns, shortReturns])
    if not res:
        return [], [], [], [], 0

    longReturns, shortReturns = zip(*res)
    orderingInd = int(cleanedData['orderingField'])
    longReturns, shortReturns = (
        sorted(filter(lambda el: el, arr),
               key=lambda row: float(row[orderingInd]), reverse=True)[:cleanedData['numRows']]
        for arr in (longReturns, shortReturns))
    longReturns, shortReturns = (calc.shortenLongNumbers(arr)
                                 for arr in (longReturns, shortReturns))
    longIds = [securityObjIdDict[row[3]] for row in longReturns]
    shortIds = [securityObjIdDict[row[3]] for row in shortReturns]

    return longReturns, shortReturns, longIds, shortIds, orderingInd
