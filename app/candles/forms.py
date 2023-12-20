""" Forms for tabs 'Settings of securities', 'Candles', 'Returns'."""
import datetime
from django import forms
from django.core.exceptions import ValidationError
import django.db.models as dj_models
from django.utils.translation import gettext_lazy as _
from django.utils.translation import gettext as __
from account.forms import HeplerMixin
from . import models, const


class SecurityForm(HeplerMixin, forms.ModelForm):

    class Meta:
        model = models.Security
        fields = ['engine', 'market', 'security']


class FetchSettingForm(HeplerMixin, forms.ModelForm):

    class Meta:
        model = models.FetchSetting
        fields = ['duration', 'interval']


class UserSecuritySettingsForm(HeplerMixin, forms.ModelForm):

    class Meta:
        model = models.UserSecurityFetchSetting
        fields = ['max_update_rate']


def validateMinDuration(value: datetime.timedelta) -> None:
    if value < ReturnsTaskForm.DURATION_MIN_VAL:
        raise ValidationError(_('Min value of duration is 1 hour.'))


class ReturnsTaskForm(HeplerMixin, forms.Form):
    DURATION_MIN_VAL = datetime.timedelta(hours=1)  # minimal value of duration field

    class Rule(dj_models.TextChoices):
        OC = const.RULE_OC, _('Open-Close')
        HL = const.RULE_HL, _('High-Low')

    duration = forms.DurationField(
        required=True, initial=datetime.timedelta(days=1), label=_('Duration'),
        help_text=_('Format: DD HH:MM:SS.uuuuuu. All calculations will be based '
                    'only on (Current time - Duration) time period. Min value is 1 hour.'),
        validators=[validateMinDuration])
    feeIn = forms.FloatField(min_value=0.0, initial=0.0, required=True, label=_('Fee to buy'),
                             help_text=_('In percentages.'))
    feeOut = forms.FloatField(min_value=0.0, initial=0.0, required=True, label=_('Fee to sell'),
                              help_text=_('In percentages.'))
    loanFee = forms.FloatField(min_value=0.0, initial=0.0, required=True, label=_('Loan fee'),
                               help_text=_('In percentages.'))
    isPerYear = forms.BooleanField(
        initial=True, required=True, label=_('Per year'),
        help_text=_('Should deals be sorted by return per year (true) or by return per trade (false)?'))
    rule = forms.ChoiceField(
        choices=Rule.choices, initial=Rule.OC, required=True, label=_('Rule'), help_text=_(
            'What OHLC values should be used for return calculation?'))

    def cleanedDataAsStr(self) -> str:
        """ Represent form cleaned data as string."""
        cd = self.cleaned_data
        cd['duration'] = datetime.timedelta(seconds=cd['duration'])
        res = ', '.join([f"{fieldObj.label}: {cd[name]}" for name, fieldObj in self.fields.items()])
        return res
