from crispy_forms.helper import FormHelper
from django import forms
from django.core.validators import validate_email
from django.utils.translation import gettext_lazy as _
import django.contrib.auth.forms as dj_auth_forms
from . import models

INVALID_LOGIN = _("Please enter a correct email and password")
INACTIVE_ACCOUNT = _("This account is inactive.")


class HeplerMixin:
    """ Provide an opportunity to insert input html tag of type="submit" to the crispy form."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper(self)
        self.helper.form_tag = False


class CustomAuthenticationForm(HeplerMixin, dj_auth_forms.AuthenticationForm):
    pass


class UserRegistrationForm(HeplerMixin, dj_auth_forms.UserCreationForm):
    email = forms.CharField(widget=forms.EmailInput(),
                            label=_("Email"), validators=[validate_email])

    class Meta:
        model = models.CustomUser
        fields = ('username', 'email')
        field_classes = {'username': dj_auth_forms.UsernameField}


class PasswordChangeForm(HeplerMixin, dj_auth_forms.PasswordChangeForm):
    pass


class PasswordResetForm(HeplerMixin, dj_auth_forms.PasswordResetForm):
    pass


class SetPasswordForm(HeplerMixin, dj_auth_forms.SetPasswordForm):
    pass


class UserEditForm(HeplerMixin, forms.ModelForm):
    class Meta:
        model = models.CustomUser
        fields = ['first_name', 'last_name', 'email']


class ProfileEditForm(HeplerMixin, forms.ModelForm):
    class Meta:
        model = models.Profile
        fields = ['date_of_birth', 'photo']
        widgets = {'date_of_birth': forms.TextInput(attrs={'type': 'date'})}
