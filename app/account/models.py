from django.db import models
import django.contrib.auth.models as dj_auth_models
from django.utils.translation import gettext_lazy as _


class CustomUser(dj_auth_models.AbstractUser):
    """ User model where every user has unique username and unique email."""
    email = models.EmailField(
        _("Email address"), max_length=255, unique=True, blank=True, null=True,
        error_messages={"unique": _("A user with that email already exists.")})

    class Meta(dj_auth_models.AbstractUser.Meta):
        swappable = "AUTH_USER_MODEL"


class Profile(models.Model):
    """ Additional user fields."""
    PHOTO_UPLOAD_TO = 'users/%Y/%m/%d/'

    user = models.OneToOneField(CustomUser, on_delete=models.CASCADE, unique=True)
    date_of_birth = models.DateField(blank=True, null=True)  # TODO: remove
    photo = models.ImageField(upload_to=PHOTO_UPLOAD_TO, blank=True, null=True)  # TODO: remove
    # TODO: add other fields

    def __str__(self):
        return f'{self.user.username}'
