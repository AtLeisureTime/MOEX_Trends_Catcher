from django.contrib import admin
from django.urls import path, include
from django.conf.urls.i18n import i18n_patterns
from . import views

urlpatterns = i18n_patterns(
    path('', views.index, name='home'),
    path('admin/', admin.site.urls),
    path('account/', include('account.urls', namespace='account')),
    path('candles/', include('candles.urls', namespace='candles')),
)

urlpatterns += [
    path("i18n/", include("django.conf.urls.i18n"))
]
