""" Celery tasks for tabs 'Settings of securities', 'Candles', 'Returns'."""
import datetime
import logging
import celery
import django.utils as dj_utils
from . import models, calculations as calc

logger = logging.getLogger('custom_debug')


@celery.shared_task
def findBestReturnsForAllSecurities(cleanedData: dict, maxNumBest: int)\
        -> tuple[list[tuple], list[tuple]]:
    """ Tries to extract time series from DB for every security, makes calculations of returns,
        generates rows for 2 tables in template.
    Args:
        cleanedData (dict): form cleaned data with parameters of task
        maxNumBest (int): max number of best returns to show in every deal table.
    Returns:
        tuple[list[tuple], list[tuple]]: rows for 2 template tables: long deals, short deals
    """
    minTime = dj_utils.timezone.now() - datetime.timedelta(seconds=cleanedData['duration'])
    qsBase = models.FetchedData.objects.select_related('fetch_setting', 'security')

    qs1 = qsBase.filter(data_last_dt__gt=minTime, data_first_dt__lte=minTime)\
        .order_by('security__security', '-data_last_dt')\
        .distinct('security__security').values_list('security__security', 'data')

    # if we don't have long enough security time series for requested minTime
    qs2 = qsBase.filter(data_last_dt__gt=minTime)\
        .order_by('security__security', '-data_last_dt')\
        .distinct('security__security').values_list('security__security', 'data')

    qs = qs1.union(qs2)

    res = []
    for security, data in qs:
        longReturns, shortReturns = calc.findBestLongShort1DealReturns(
            data, cleanedData['rule'], minTime, security, cleanedData['isPerYear'],
            cleanedData['feeIn'], cleanedData['feeOut'], cleanedData['loanFee'])
        res.append([longReturns, shortReturns])
    if not res:
        return [], []

    longReturns, shortReturns = zip(*res)
    baseReturnInd = 0 if cleanedData['isPerYear'] else 2
    longReturns, shortReturns = (
        sorted(filter(lambda el: el, arr),
               key=lambda row: row[baseReturnInd], reverse=True)[:maxNumBest]
        for arr in (longReturns, shortReturns))
    longReturns, shortReturns = (calc.largeNumsToScientificNotation(arr)
                                 for arr in (longReturns, shortReturns))

    return longReturns, shortReturns
