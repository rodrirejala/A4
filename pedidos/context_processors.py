from django.conf import settings

from . import roles


def company(request):
    return {'company': settings.COMPANY}


def rol(request):
    """Expone el rol del usuario a todos los templates."""
    user = getattr(request, 'user', None)
    return {
        'es_admin': roles.es_admin(user),
        'es_solicitante': roles.es_solicitante(user),
    }