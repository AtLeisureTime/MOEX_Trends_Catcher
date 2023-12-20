import django.urls as dj_urls
from . import views

app_name = "account"

urlpatterns = [
    dj_urls.path('', views.dashboard, name='dashboard'),
    dj_urls.path('login/', views.EmailLoginView.as_view(), name='login'),
    dj_urls.path('register/', views.register, name='register'),
    dj_urls.path('edit/', views.edit, name='edit'),
    dj_urls.path('password_change/', views.PasswordChangeView.as_view(
        success_url=dj_urls.reverse_lazy('account:password_change_done')), name='password_change'),
    dj_urls.path('password_reset/', views.PasswordResetView.as_view(
        success_url=dj_urls.reverse_lazy('account:password_reset_done')),
        name='password_reset'),
    dj_urls.path('reset/<uidb64>/<token>/', views.PasswordResetConfirmView.as_view(
        success_url=dj_urls.reverse_lazy('account:password_reset_complete')),
        name='password_reset_confirm'),  # mb TODO
    dj_urls.path('', dj_urls.include('django.contrib.auth.urls')),
]
