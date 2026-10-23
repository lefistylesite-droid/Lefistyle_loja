"""Bootstrap optional one-time administrator with explicit environment credentials.
No default password, never changes an existing account or prints credentials.
"""
import os
from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError

class Command(BaseCommand):
    help = 'Opcional: cria superusuário se LEFI_ADMIN_EMAIL e LEFI_ADMIN_PASSWORD estiverem configurados.'
    def handle(self,*args,**kwargs):
        email = os.environ.get('LEFI_ADMIN_EMAIL','').strip().lower()
        password = os.environ.get('LEFI_ADMIN_PASSWORD','')
        if not email and not password:
            self.stdout.write('Admin inicial: não configurado; use createsuperuser ou variáveis seguras.')
            return
        if not email or not password:
            raise CommandError('Configure LEFI_ADMIN_EMAIL e LEFI_ADMIN_PASSWORD juntos.')
        if '@' not in email or len(email)>150:
            raise CommandError('E-mail administrativo inválido.')
        user_model=get_user_model()
        if user_model.objects.filter(username=email).exists():
            self.stdout.write('Admin inicial: conta existente preservada (senha nunca sobrescrita).')
            return
        if user_model.objects.filter(is_superuser=True).exists():
            self.stdout.write('Admin inicial: já existe superusuário. Nenhuma alteração.')
            return
        if len(password) < 12:
            raise CommandError('Senha deve ter ao menos 12 caracteres.')
        try:
            validate_password(password)
        except ValidationError as exc:
            raise CommandError('; '.join(exc.messages))
        user_model.objects.create_superuser(username=email,email=email,password=password)
        self.stdout.write(self.style.SUCCESS('Administrador inicial criado. Remova as variáveis de bootstrap depois.'))
