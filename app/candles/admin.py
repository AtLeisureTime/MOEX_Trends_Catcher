from django.contrib import admin
from . import models


@admin.register(models.Security)
class SecurityAdmin(admin.ModelAdmin):
    list_display = ['engine', 'market', 'security']


@admin.register(models.FetchSetting)
class FetchSettingAdmin(admin.ModelAdmin):
    list_display = ['duration', 'interval']


@admin.register(models.FetchedData)
class FetchedDataAdmin(admin.ModelAdmin):
    list_display = ['id', 'security', 'fetch_setting', 'data_update_dt', 'data_first_dt',
                    'data_last_dt', 'data_is_full']
    raw_id_fields = ['security', 'fetch_setting']


@admin.register(models.UserSecurityFetchSetting)
class UserSecurityFetchSettingAdmin(admin.ModelAdmin):
    list_display = ['id', 'user', 'fetched_data', 'max_update_rate', 'has_error', 'sequence_number']
    raw_id_fields = ['user', 'fetched_data']


@admin.register(models.CandlesUpdate)
class CandlesUpdateAdmin(admin.ModelAdmin):
    list_display = ['id', 'url', 'time', 'status', 'error']
