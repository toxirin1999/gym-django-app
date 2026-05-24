from .models import Cliente


def get_cliente_actual(user):
    return Cliente.objects.get(user=user)
