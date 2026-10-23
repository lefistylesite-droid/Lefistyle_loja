import re
from django.core.exceptions import ValidationError


def normalize_cpf(value):
    if not re.fullmatch(r"[0-9.\- ]+", value or ""):
        raise ValidationError('Informe um CPF válido.')
    cpf = re.sub(r"[^0-9]", "", value)
    if len(cpf) != 11 or len(set(cpf)) == 1:
        raise ValidationError('Informe um CPF válido.')
    for size in (9, 10):
        digit = (sum(int(cpf[i]) * (size + 1 - i) for i in range(size)) * 10) % 11
        if int(cpf[size]) != (0 if digit == 10 else digit):
            raise ValidationError('CPF inválido. Confira os números digitados.')
    return cpf
