""" Send requests to MOEX, validate and transform responses."""
import asyncio
import datetime
import logging
import time
import typing
import zoneinfo
import aiohttp
from django.utils.translation import gettext_lazy as _
from django.utils.timezone import get_current_timezone
from . import const

logger = logging.getLogger('custom_debug')


class BaseDownloader:

    @classmethod
    def _validateResp(cls, respJson: dict, *args: typing.Any, **kwargs: typing.Any) -> str | None:
        """ Validates json response content and returns error message.
            Override this method.
        Args:
            respJson (dict): GET URL response json
            args (tuple): positional arguments
            kwargs (dict): keyword arguments
        Returns:
            str | None: error message
        """
        return

    @classmethod
    def _transformResp(cls, respJson: dict, *args: typing.Any, **kwargs: typing.Any) -> tuple:
        """ Extracts some fields from 'respJson' or returns 'respJson'.
            Override this method.
        Args:
            respJson (dict): GET URL response json
            args (tuple): positional arguments
            kwargs (dict): keyword arguments
        Returns:
            tuple: extracted info from respJson
        """
        return (respJson,)

    @classmethod
    async def _fetchOne(cls, session: aiohttp.ClientSession, url: str,
                        *args: typing.Any, **kwargs: typing.Any)\
            -> tuple[tuple | None, int | None, str | None]:
        """ Sends one GET 'url' request, validates fetched json, extracts some fields from it.
        Args:
            session (aiohttp.ClientSession): aiohttp interface for requests
            url (str): URL for GET request
            args (tuple): positional arguments
            kwargs (dict): keyword arguments
        Returns:
            tuple[tuple | None, int | None, str | None]:
                extracted info from json, request status code, error message
        """
        res, status, error = None, None, None
        try:
            async with session.get(url) as response:
                status = response.status
                res = await response.json()
        except aiohttp.client_exceptions.ClientError as ex:
            error = str(ex)
        if error is None:
            error = cls._validateResp(res, *args, **kwargs)
        if error is None:
            res = cls._transformResp(res, *args, **kwargs)
        else:
            res = None
        return res, status, error

    @classmethod
    async def fetchMany(cls, urls: list, timeoutSec: int, *args: typing.Any, **kwargs: typing.Any)\
            -> list[tuple[tuple | None, int | None, str | None]]:
        """ It calls fetchOne class method for every url in 'urls'.
            If timeoutSec is exceeded, every url will be marked as erroneous.
        Args:
            urls (list): URL for GET request in fetchOne function
            timeoutSec (int): maximum waiting time
        Returns:
            list[tuple[tuple | None, int | None, str | None]]: list of fetchOne call results
        """
        if not urls:
            return []
        timeout = aiohttp.ClientTimeout(total=timeoutSec)
        try:
            async with aiohttp.ClientSession(timeout=timeout) as session:
                tasks = [cls._fetchOne(session, url, *args, **kwargs) for url in urls]
                res = await asyncio.gather(*tasks)
        except asyncio.TimeoutError:
            error = (f'The timeout limit ({timeoutSec} seconds) has been exceeded '
                     f'during fetching {len(urls)} urls.')
            logger.debug(error)
            # mark all urls as erroneous
            res = [(None, None, error) for _ in range(len(urls))]
        return res


class MOEX_Downloader(BaseDownloader):

    @classmethod
    def _validateResp(cls, respJson: dict, *args: typing.Any, **kwargs: typing.Any) -> str | None:
        """ Validates json response content and returns error message.
        Args:
            respJson (dict): GET URL response json
            args (tuple): positional arguments
            kwargs (dict): keyword arguments
        Returns:
            str | None: error message
        """
        if 'candles' not in respJson:
            return _("No 'candles' field in response.")
        if 'error' in respJson['candles']:
            return respJson['candles']['error'] or _("There's 'error' field in response.")
        if 'columns' not in respJson['candles'] or 'data' not in respJson['candles']:
            return _("No ['candles']['columns'] or / and ['candles']['data'] dicts in response.")
        if not respJson['candles']['columns'] or \
            not isinstance(respJson['candles']['columns'], list) or \
                respJson['candles']['columns'] != const.MOEX_COLS:
            return _('Order of columns has changed in response.')
        if not respJson['candles']['data'] or not isinstance(respJson['candles']['data'], list):
            return _('No data.')
        if not isinstance(respJson['candles']['data'][0], list) or \
                not len(respJson['candles']['data'][0]) == len(const.MOEX_COLS):
            return _('Data format has changed.')

    @classmethod
    def _transformResp(cls, respJson: dict, *args: typing.Any, **kwargs: typing.Any)\
            -> tuple[list[list], datetime.datetime, datetime.datetime, bool]:
        """ Extracts 'candles'>'data' field from respJson, first and last datetime and checks
            if additional requests are needed to fetch other data rows.
        Args:
            respJson (dict): GET URL response json
            args (tuple): positional arguments
            kwargs (dict): keyword arguments
        Returns:
            tuple[list[list], datetime.datetime, datetime.datetime, bool]:
                respJson['candles']['data'] as fetched data,
                datetime of first row in fetched data, datetime of last row in fetched data,
                is data list full or additional requests are needed to fetch other data rows.
            Lengthes of all lists (except list of request errors or validation errors) are the same.
        """
        data = respJson['candles']['data']
        if kwargs.get('reversed', False):
            data = data[::-1]
        tz = zoneinfo.ZoneInfo(const.MOEX_TZ)
        beginDt, endDt = (
            datetime.datetime.strptime(dt, const.MOEX_DATE_FORMAT)
            .replace(tzinfo=tz).astimezone(get_current_timezone())
            for dt in (data[0][const.MOEX_COL_DT_BEGIN], data[-1][const.MOEX_COL_DT_END]))
        isFull = len(data) != const.MOEX_DATA_MAX_LEN
        return data, beginDt, endDt, isFull

    @classmethod
    def fetchData(cls, pageUrlsToGet: list[str], timeoutSec: int | float)\
        -> tuple[list[list[list]], list[int], list[str], list[str], list[datetime.datetime],
                 list[datetime.datetime], list[bool]] | None:
        """ Downloads data for every URL in 'pageUrlsToGet', validates it's json,
            extracts 'data' field, first and last datetime.
        Args:
            pageUrlsToGet (list[str]): urls for GET URL requests
            timeoutSec (int | float): maximum waiting time
        Returns:
            tuple[list[list[list]], list[int],
                  list[str], list[str],
                  list[datetime.datetime], list[datetime.datetime],
                  list[bool]] | None:
            list[list[const.MOEX_COLS] for every URL in 'pageUrlsToGet'], request statuses,
            request errors or validation errors, URLs of erroneous responses,
            datetimes of first row in fetched data, datetimes of last row in fetched data,
            list[is fetched data list full or additional requests are needed].
            Lengthes of all lists (except list of request errors or validation errors) are the same.
        """
        if not pageUrlsToGet:
            return

        start = time.time()
        results = asyncio.run(super().fetchMany(pageUrlsToGet, timeoutSec, reversed=True))
        end = time.time()
        logger.debug(f"Fetch time of {len(pageUrlsToGet)} urls is {end - start}.")
        results, statuses, errors = zip(*results) if results else ([], [], [])

        resultsCleaned = []
        for res in results:
            if res is None:
                resultsCleaned.append((None, None, None, None))
            else:
                resultsCleaned.append(res)

        if not resultsCleaned:
            dataArrs, beginDts, endDts, isFulls = ([], [], [], [])
        else:
            dataArrs, beginDts, endDts, isFulls = zip(*resultsCleaned)

        errRespInd = [i for i in range(len(pageUrlsToGet))
                      if not statuses[i] or statuses[i] >= 400 or errors[i]]
        errRespUrls = [pageUrlsToGet[i] for i in errRespInd]

        return dataArrs, statuses, errors, errRespUrls, beginDts, endDts, isFulls


class MOEX_Ticker_Downloader(BaseDownloader):

    @classmethod
    def _validateResp(cls, respJson: dict, *args: typing.Any, **kwargs: typing.Any) -> str | None:
        """ Validates json response content and returns error message.
        Args:
            respJson (dict): GET URL response json
            args (tuple): positional arguments
            kwargs (dict): keyword arguments
        Returns:
            str | None: error message
        """
        SCR, MRKD = 'securities', 'marketdata'
        if SCR not in respJson or MRKD not in respJson:
            return _("No 'securities' or / and 'marketdata' field in response.")
        if 'error' in respJson[SCR] or 'error' in respJson[MRKD]:
            return respJson[SCR].get('error', None) or \
                respJson[MRKD].get('error', None) or _("There's 'error' field in response.")
        if 'columns' not in respJson[SCR] or 'columns' not in respJson[MRKD]\
                or 'data' not in respJson[SCR] or 'data' not in respJson[MRKD]:
            return _("No 'columns' or / and 'data' fields inside 'securities' or / and "
                     "'marketdata' fields in response.")
        if not respJson[SCR]['columns'] or not respJson[MRKD]['columns']\
            or not isinstance(respJson[SCR]['columns'], list) \
                or not isinstance(respJson[MRKD]['columns'], list)\
            or respJson[SCR]['columns'] != const.MOEX_SECURITY_COLS\
                or respJson[MRKD]['columns'] != const.MOEX_MARKETDATA_COLS:
            return _('Order of columns has changed in response.')
        if not respJson[SCR]['data'] or not respJson[MRKD]['data']\
                or not isinstance(respJson[SCR]['data'], list)\
        or not isinstance(respJson[MRKD]['data'], list):
            return _("No 'data' field in response.")
        if not isinstance(respJson[SCR]['data'][0], list)\
            or not isinstance(respJson[MRKD]['data'][0], list)\
                or not isinstance(respJson[SCR]['data'][0][0], str)\
            or not isinstance(respJson[MRKD]['data'][0][0], int | float):
            return _('Data format has changed.')

    @classmethod
    def _transformResp(cls, respJson: dict, *args: typing.Any, **kwargs: typing.Any)\
            -> tuple[list[str], list[int | float]]:
        """ Extracts 'securities'>'data'>'SECID' and 'marketdata'>'data'>'ISSUECAPITALIZATION'
            fields from respJson.
        Args:
            respJson (dict): GET URL response json
            args (tuple): positional arguments
            kwargs (dict): keyword arguments
        Returns:
            tuple[list[str], list[int | float]]: tickers of securities, security capitalizations
            Lengthes of lists are the same.
        """
        securityTickers = [row[0] for row in respJson['securities']['data']]
        capitalizatns = [row[0] for row in respJson['marketdata']['data']]
        return securityTickers, capitalizatns

    @classmethod
    def fetchSecurities(cls, pageUrlsToGet: list[str], timeoutSec: int | float)\
            -> tuple[list[str], list[int | float], list[str]]:
        """ Downloads data for every URL in 'pageUrlsToGet', validates its json,
            extracts security tickers and their capitalizations.
        Args:
            pageUrlsToGet (list[str]): urls for GET URL requests
            timeoutSec (int | float): maximum waiting time
        Returns:
            tuple[list[str], list[int | float], list[str]]:
            tickers of securities, security capitalizations, erroneous responses URL list
            Lengthes of lists are the same.
        """
        if not pageUrlsToGet:
            return

        start = time.time()
        results = asyncio.run(super().fetchMany(pageUrlsToGet, timeoutSec))
        end = time.time()
        logger.debug(f"Fetch time of {len(pageUrlsToGet)} urls is {end - start}.")
        results, statuses, errors = zip(*results) if results else ([], [], [])

        resultsCleaned = []
        for res in results:
            if res is None:
                resultsCleaned.append((None, None))
            else:
                resultsCleaned.append(res)

        if not resultsCleaned:
            securityTickers, capitalizatns = ([], [])
        else:
            securityTickers, capitalizatns = zip(*resultsCleaned)

        errRespInd = [i for i in range(len(pageUrlsToGet))
                      if not statuses[i] or statuses[i] >= 400 or errors[i]]
        errRespUrls = [pageUrlsToGet[i] for i in errRespInd]

        return securityTickers[0], capitalizatns[0], errRespUrls
