"""Piezas comunes de la API: tienda actual y manejo de errores de negocio."""

from rest_framework.exceptions import NotFound
from rest_framework.response import Response
from rest_framework.views import exception_handler

from core.errores import ErrorNegocio
from tiendas.models import Rol


def tienda_actual(request):
    """La tienda del subdominio; si el request llegó a la plataforma (sin
    tienda), estos endpoints no aplican."""
    tienda = getattr(request._request, 'tienda', None)
    if tienda is None:
        raise NotFound('Este endpoint solo existe dentro de una tienda.')
    return tienda


def es_admin_tienda(request):
    perfil = getattr(request._request, 'perfil', None)
    return bool(perfil and perfil.rol.codigo == Rol.ADMIN_TIENDA)


class TenantMixin:
    """Para los ViewSets: entrega la tienda a los serializers."""

    def get_serializer_context(self):
        contexto = super().get_serializer_context()
        contexto['tienda'] = tienda_actual(self.request)
        return contexto


def manejador_de_errores(exc, contexto):
    """Un ErrorNegocio (stock insuficiente, etc.) se responde 400 con JSON
    prolijo; el resto lo maneja DRF como siempre."""
    if isinstance(exc, ErrorNegocio):
        return Response({'error': str(exc)}, status=400)
    return exception_handler(exc, contexto)
