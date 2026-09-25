from django.conf import settings
from django.utils.http import url_has_allowed_host_and_scheme


def url_tienda(request, tienda):
    """URL pública de una tienda: http://raiz.localhost:8000/ (o su dominio propio)."""
    puerto = request.get_port()
    sufijo = '' if puerto in ('80', '443') else f':{puerto}'
    host = tienda.dominio_propio or f'{tienda.slug}.{settings.DOMINIO_BASE}'
    return f'{request.scheme}://{host}{sufijo}/'


def destino_seguro(request, siguiente, por_defecto='/'):
    """Evita el "open redirect": el parámetro ?next= solo se acepta si apunta
    a este mismo sitio (si no, un atacante podría mandar al usuario a otra web
    justo después de que inicie sesión)."""
    if siguiente and url_has_allowed_host_and_scheme(siguiente, allowed_hosts={request.get_host()}):
        return siguiente
    return por_defecto
