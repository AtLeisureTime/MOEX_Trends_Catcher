from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from . import models


@admin.register(models.CustomUser)
class CustomUserAdmin(UserAdmin):
    pass


@admin.register(models.Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ['id', 'user', 'date_of_birth', 'photo']
    raw_id_fields = ['user']
