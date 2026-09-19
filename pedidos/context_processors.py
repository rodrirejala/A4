from django.conf import settings


def company(request):
    return {'company': settings.COMPANY}