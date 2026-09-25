"""
Autenticación JWT vía cookie HttpOnly para los endpoints de la API (DRF).

Por defecto, djangorestframework-simplejwt busca el token en el header
"Authorization: Bearer <token>". Acá NO se usa el header: el token viaja en
una cookie HttpOnly, porque un XSS podría leer localStorage con JavaScript
pero no una cookie HttpOnly.

La validación del token (firma, expiración, usuario habilitado, pertenece a
esta tienda) ya la hizo core.middleware.JWTAuthMiddleware, que dejó
request.perfil. Esta clase solo lo entrega a DRF, para tener una única fuente
de verdad tanto en las páginas como en la API.

COSTO de usar cookies: el navegador las manda solo, incluso desde otro sitio
malicioso (ataque CSRF). Por eso, en métodos que modifican datos (POST, PUT,
PATCH, DELETE), se exige además el header X-CSRFToken (igual que hace
SessionAuthentication de DRF).
"""

from rest_framework import exceptions
from rest_framework.authentication import BaseAuthentication, CSRFCheck


class CookieJWTAuthentication(BaseAuthentication):
    def authenticate(self, request):
        perfil = getattr(request._request, 'perfil', None)
        if perfil is None:
            return None  # sin sesión: DRF decide con los permisos de la vista
        self.enforce_csrf(request)
        return perfil.user, None

    def authenticate_header(self, request):
        # Hace que "no autenticado" responda 401 (y no 403).
        return 'Cookie'

    def enforce_csrf(self, request):
        comprobacion = CSRFCheck(lambda r: None)
        comprobacion.process_request(request)
        motivo = comprobacion.process_view(request, None, (), {})
        if motivo:
            raise exceptions.PermissionDenied(f'CSRF falló: {motivo}')
