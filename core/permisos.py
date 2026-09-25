"""
Autorización: quién puede entrar a qué.

Hay dos niveles y NO son lo mismo:
  - autenticación: ¿quién eres?   -> lo resuelve JWTAuthMiddleware
  - autorización:  ¿puedes hacer esto? -> lo resuelve este archivo

Se ofrece lo mismo para las dos "caras" del proyecto:
  - requiere_rol(...)  : decorador para las vistas con templates
  - rol_api(...)       : clase de permiso para los endpoints de DRF
"""

from functools import wraps
from urllib.parse import quote

from django.shortcuts import redirect, render
from rest_framework.permissions import SAFE_METHODS, BasePermission

from tiendas.models import Rol


def requiere_rol(*roles):
    """Vista con template que exige sesión y uno de los roles dados.
    - sin sesión  -> redirige al login (equivale a un 401 amable)
    - rol distinto -> página 403"""

    def decorador(vista):
        @wraps(vista)
        def envoltura(request, *args, **kwargs):
            perfil = getattr(request, 'perfil', None)
            if perfil is None:
                return redirect(f'/login/?next={quote(request.get_full_path())}')
            if perfil.rol.codigo not in roles:
                return render(request, 'errores/403.html', status=403)
            return vista(request, *args, **kwargs)
        return envoltura

    return decorador


def rol_api(*roles):
    """Crea una clase de permiso DRF que exige uno de los roles."""

    class TieneRol(BasePermission):
        def has_permission(self, request, view):
            perfil = getattr(request._request, 'perfil', None)
            return bool(perfil and perfil.rol.codigo in roles)

    return TieneRol


class LecturaPublicaEscrituraAdminTienda(BasePermission):
    """Ver es público (catálogo); crear/editar/dar de baja solo el admin de la tienda."""

    def has_permission(self, request, view):
        if request.method in SAFE_METHODS:
            return True
        perfil = getattr(request._request, 'perfil', None)
        return bool(perfil and perfil.rol.codigo == Rol.ADMIN_TIENDA)
