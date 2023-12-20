""" Models for tabs 'Settings of securities', 'Candles', 'Returns'."""
import datetime
import zoneinfo
from django.db import models
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from account import models as account_models
from . import const

User = account_models.CustomUser


class Security(models.Model):
    """ 'engine', 'market' & 'security' URL params of https://iss.moex.com/iss/reference/155
        endpoint"""
    MAX_LEN = 40

    engine = models.CharField(
        _('Engine name'), default='stock', max_length=MAX_LEN,
        help_text=_(f"E.g., stock, currency, commodity. Full list: {const.MOEX_URL}iss/engines/"))
    market = models.CharField(
        _('Market name'), max_length=MAX_LEN,
        help_text=_(f"E.g., index, shares, bonds."
                    f"Full list: {const.MOEX_URL}iss/engines/[your_engine]/markets/"))
    security = models.CharField(
        _('Security SECID'), max_length=MAX_LEN, db_index=True,
        help_text=_(f"E.g., YNDX, GLDRUB_TOM. Full list: "
                    f"{const.MOEX_URL}iss/engines/[your_engine]/markets/[your_market]/securities/"))

    class Meta:
        verbose_name_plural = 'Securities'

    def __str__(self) -> str:
        return _('Engine: {engine}, market: {market}, security: {security}').format(
            engine=self.engine, market=self.market, security=self.security)


class FetchSetting(models.Model):
    """ Used to calculate 'from' and set 'interval' param of https://iss.moex.com/iss/reference/155
        endpoint"""
    class Intervals(models.IntegerChoices):
        I_0 = 0, _('No value')
        I_1MIN = 1, _('1 minute')
        I_10MIN = 10, _('10 minutes')
        I_1HOUR = 60, _('1 hour')
        I_1DAY = 24, _('1 day')
        I_1WEEK = 7, _('1 week')
        I_1MONTH = 31, _('1 month')
        I_3MONTHES = 4, _('3 monthes')

    duration = models.DurationField(
        _('Duration'), default=datetime.timedelta(weeks=1), blank=True, null=True,
        help_text=_("It's necessary for calculation of 'candles.json?from=' parameter. "
                    "Format: DD HH:MM:SS.uuuuuu"))
    interval = models.PositiveSmallIntegerField(
        _('Interval'), choices=Intervals.choices, default=Intervals.I_1HOUR,
        help_text=_("'candles.json?interval=' parameter. Bear in mind that data will be fetched "
                    "only for the last 500 time intervals in the current version of this app."))

    def __str__(self) -> str:
        # return f'Duration={self.duration}; interval={self.interval}'
        return _('Duration: {duration}; interval: {interval}').format(
            duration=self.duration, interval=self.__class__.Intervals(self.interval).label)


class FetchedData(models.Model):
    """ Used to save data from MOEX response."""
    # These 2 params define URL to fetch data
    security = models.ForeignKey(Security, on_delete=models.CASCADE)
    fetch_setting = models.ForeignKey(FetchSetting, on_delete=models.CASCADE)

    # 2D array with mix of float, int and str data.
    # Maybe change to HStoreField {'{date1}': array1d, ..}
    # or ArrayField(ArrayField(models.FloatField(), size=6) and store str fields in another place.
    data = models.JSONField(blank=True, null=True)

    # metadata of data field
    data_update_dt = models.DateTimeField(blank=True, null=True)
    data_first_dt = models.DateTimeField(blank=True, null=True, db_index=True)
    data_last_dt = models.DateTimeField(blank=True, null=True, db_index=True)
    data_is_full = models.BooleanField(blank=True, null=True)

    def __str__(self) -> str:
        return f'security=[{str(self.security)}]; fetch_setting=[{str(self.fetch_setting)}]'

    def getURL(self) -> str:
        """ Generate URL to fetch data from MOEX."""
        from_, interval = '', ''
        if self.fetch_setting.duration:
            tz = zoneinfo.ZoneInfo(const.MOEX_TZ)
            currentTime = timezone.now().astimezone(tz)
            from_ = (currentTime - self.fetch_setting.duration).strftime('%Y-%m-%d_%H:%M:%S')
            from_ = f'&from={from_}'
        if self.fetch_setting.interval != 0:
            interval = f'&interval={self.fetch_setting.interval}'
        # iss.meta=off - remove some fields from json response
        # iss.reverse - respJson['candles']['data'] in the reverse order
        params = f'?iss.meta=off&iss.reverse=true{from_}{interval}'

        return (f'{const.MOEX_URL}iss/engines/{self.security.engine}/markets/{self.security.market}'
                f'/securities/{self.security.security}/candles.json{params}')

    @classmethod
    def getPrefetchObjWoDataFields(cls) -> models.Prefetch:
        """ Exclude 'data' and metadata fields from qs."""
        qs = cls.objects.only('security', 'fetch_setting')\
            .select_related('security', 'fetch_setting')
        return models.Prefetch('fetched_data', queryset=qs)


class UserSecurityFetchSetting(models.Model):
    """ Used to save user desired parameters of security data fetching."""
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    fetched_data = models.ForeignKey(FetchedData, on_delete=models.CASCADE)
    max_update_rate = models.DurationField(
        _('Maximum candle refresh rate'), default=datetime.timedelta(hours=1),
        help_text=_('Format: DD HH:MM:SS.uuuuuu'))

    # 'has_error' is null after setting creation even if other users get error for this setting.
    # Value is True / False after first fetching of data during candle displaying.
    has_error = models.BooleanField(null=True)
    sequence_number = models.PositiveSmallIntegerField(db_index=True)

    class Meta:
        constraints = [
            models.constraints.UniqueConstraint(fields=('user_id', 'sequence_number'),
                                                name='unique_userId_sequenceNumber',
                                                deferrable=models.Deferrable.DEFERRED),
            models.constraints.UniqueConstraint(
                fields=('user_id', 'fetched_data_id'), name='unique_userId_fetchedDataId')]

    def get_absolute_url(self) -> str:
        return reverse('candles:settingUpdate', args=[self.id])


class CandlesUpdate(models.Model):
    """ Info about all requests with errors or status >= 400."""
    url = models.URLField(max_length=200)
    time = models.DateTimeField(auto_now_add=True, editable=False)
    status = models.PositiveSmallIntegerField(null=True)
    error = models.CharField(null=True)
