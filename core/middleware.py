"""
Los tres middlewares del proyecto. Un middleware es código que se ejecuta en
CADA request, antes y después de la vista. El orden importa (ver settings.py):

  Metricas  ->  Tenant  ->  (sesión, CSRF, auth de Django)  ->  JWT  ->  vista
"""

import time

from django.conf import settings
from django.shortcuts import render

from core.auth import perfil_desde_cookies, poner_cookie
from core.models import Metrica
from tiendas.models import Tienda


class MetricasMiddleware:
    """Guarda cuánto tardó cada request. Es el middleware más externo, así que
    mide todo lo demás (incluidos los otros middlewares)."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        inicio = time.perf_counter()
        response = self.get_response(request)
        if not request.path.startswith(('/static/', '/media/', '/favicon')):
            try:
                Metrica.objects.create(
                    tienda=getattr(request, 'tienda', None),
                    metodo=request.method,
                    ruta=request.path[:255],
                    status=response.status_code,
                    duracion_ms=int((time.perf_counter() - inicio) * 1000),
                )
            except Exception:
                pass  # medir jamás debe romper la respuesta al usuario
        return response


class TenantMiddleware:
    """Decide de qué tienda es el request mirando el header Host.

      raiz.localhost:8000   -> tienda con slug "raiz"
      zapatilleate.cl       -> tienda con dominio_propio "zapatilleate.cl"
      localhost:8000        -> la plataforma (request.tienda = None)

    Deja el resultado en request.tienda. Si la tienda no existe responde 404
    y si está dada de baja responde 403, sin llegar a ninguna vista.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.tienda = None
        host = request.get_host().split(':')[0].lower()

        if host not in settings.HOSTS_PLATAFORMA:
            sufijo = '.' + settings.DOMINIO_BASE
            if host.endswith(sufijo):
                tienda = Tienda.objects.select_related('plan').filter(slug=host[:-len(sufijo)]).first()
            else:
                tienda = Tienda.objects.select_related('plan').filter(dominio_propio=host).first()

            if tienda is None:
                return render(request, 'errores/404.html', {
                    'mensaje': 'Esta tienda no existe.',
                }, status=404)
            if not tienda.habilitado:
                return render(request, 'errores/403.html', {
                    'mensaje': 'Esta tienda está suspendida.',
                }, status=403)
            request.tienda = tienda

        return self.get_response(request)


class JWTAuthMiddleware:
    """Si el request trae una cookie JWT válida, deja request.user y
    request.perfil. Si el access estaba vencido pero el refresh sirve, renueva
    el access automáticamente y lo devuelve en la respuesta."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.perfil = None
        access_nuevo = None
        if settings.AUTH_COOKIE_ACCESS_NAME in request.COOKIES or \
                settings.AUTH_COOKIE_REFRESH_NAME in request.COOKIES:
            perfil, access_nuevo = perfil_desde_cookies(request)
            if perfil:
                request.perfil = perfil
                request.user = perfil.user

        response = self.get_response(request)

        if access_nuevo:
            poner_cookie(response, settings.AUTH_COOKIE_ACCESS_NAME, access_nuevo,
                          int(settings.SIMPLE_JWT['ACCESS_TOKEN_LIFETIME'].total_seconds()))
        return response
