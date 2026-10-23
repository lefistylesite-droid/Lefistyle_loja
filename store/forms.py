from django import forms
from django.contrib.auth import get_user_model
from .models import CustomerProfile
from .validators import normalize_cpf


class RegisterForm(forms.Form):
    first_name = forms.CharField(label='Nome completo', min_length=3, max_length=150,
                                widget=forms.TextInput(attrs={'autocomplete':'name'}))
    cpf = forms.CharField(label='CPF', max_length=14,
                         widget=forms.TextInput(attrs={'inputmode':'numeric', 'placeholder':'000.000.000-00'}))
    email = forms.EmailField(label='E-mail', max_length=254,
                            widget=forms.EmailInput(attrs={'autocomplete':'email'}))

    def clean_cpf(self):
        cpf = normalize_cpf(self.cleaned_data['cpf'])
        if CustomerProfile.objects.filter(cpf=cpf).exists():
            raise forms.ValidationError('Este CPF já possui cadastro. Acesse sua conta ou contate a loja.')
        return cpf

    def clean_email(self):
        email = self.cleaned_data['email'].strip().lower()
        if (get_user_model().objects.filter(email__iexact=email).exists()
                or CustomerProfile.objects.filter(email=email).exists()):
            raise forms.ValidationError('Este e-mail já está cadastrado.')
        return email
