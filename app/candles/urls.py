""" Urls for tabs 'Settings of securities', 'Candles', 'Returns'."""
import django.urls as dj_urls
from . import views


app_name = 'candles'

urlpatterns = [
    dj_urls.path('', views.getCandlesPreview, name='list'),
    dj_urls.path('candlesData/', views.getCandles, name='candlesData'),
    dj_urls.path('returnsTask/', views.returnsTask, name='returnsTask'),
    dj_urls.path('trackingSettings/', views.SecuritySettingListView.as_view(), name='settingList'),
    dj_urls.path('trackingSettings/add/',
                 views.createSecuritySetting, name='settingCreate'),
    dj_urls.path('trackingSettings/chooseAction/', views.chooseAction, name='chooseAction'),
    dj_urls.path('trackingSettings/bulkDeleteConfirm/',
                 views.bulkDeleteConfirm, name='settingBulkDeleteConfirm'),
    dj_urls.path('trackingSettings/<pk>/edit/', views.updateSecuritySetting, name='settingUpdate'),
]
