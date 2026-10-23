from django.contrib.auth.backends import ModelBackend
from django.contrib.auth import get_user_model

class EmailOrUsernameBackend(ModelBackend):
    def authenticate(self, request, username=None, password=None, **kwargs):
        if not username or password is None:
            return None
        User = get_user_model()
        users = list(User.objects.filter(email__iexact=username.strip())[:2]) if '@' in username else []
        if len(users) > 1:
            User().set_password(password)
            return None
        if not users:
            return super().authenticate(request, username=username, password=password, **kwargs)
        user = users[0]
        if user.check_password(password) and self.user_can_authenticate(user):
            return user
        return None
