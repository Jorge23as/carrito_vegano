"""Le explica a Swagger (drf-spectacular) cómo se autentica nuestra API:
con una cookie (el JWT), no con el header Authorization."""

from django.conf import settings
from drf_spectacular.extensions import OpenApiAuthenticationExtension


class CookieJWTScheme(OpenApiAuthenticationExtension):
    target_class = 'tienda_project.authentication.CookieJWTAuthentication'
    name = 'cookieJWT'

    def get_security_definition(self, auto_schema):
        return {'type': 'apiKey', 'in': 'cookie', 'name': settings.AUTH_COOKIE_ACCESS_NAME,
                'description': 'JWT en cookie HttpOnly. Se obtiene con POST /api/auth/login/ '
                               '(o iniciando sesión en /login/).'}
