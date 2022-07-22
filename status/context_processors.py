from django.conf import settings


def canonical(request):
    """
    Gets the canonical URL for the current request.
    """
    return {'canonical': request.build_absolute_uri(request.path)}


def base_url(request):
    """
    Provides the BASE_URL from settings.
    """
    return {'BASE_URL': settings.BASE_URL}
