"""
Autenticación con JWT guardado en cookies HttpOnly.

Flujo completo:
1. El usuario hace login (formulario o /api/auth/login/).
2. El servidor valida correo + contraseña y crea dos tokens:
     - access  (30 min): se manda en cada request, prueba "quién eres".
     - refresh (7 días): sirve solo para pedir un access nuevo.
3. Ambos se guardan en cookies HttpOnly: el navegador las manda solo y
   JavaScript NO puede leerlas (protege ante XSS).
4. En cada request, JWTAuthMiddleware lee la cookie, valida la firma y la
   fecha del token, y revisa en la BD que el usuario siga habilitado y que
   pertenezca a la tienda del subdominio. Recién ahí deja request.user.

Un token válido NO basta: además se comprueba la tienda. Si no, un cliente de
la tienda A podría usar su cookie contra la tienda B.
"""

from django.conf import settings
from django.core.cache import cache
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import AccessToken, RefreshToken

from tiendas.models import PerfilUsuario, Rol

MAX_INTENTOS = 5
BLOQUEO_SEGUNDOS = 300


# --- Emisión y borrado de cookies -------------------------------------------

def emitir_tokens(perfil):
    """Crea (access, refresh) para el usuario, con la tienda y el rol dentro
    del token como datos extra (claims)."""
    refresh = RefreshToken.for_user(perfil.user)
    refresh['tienda_id'] = perfil.tienda_id
    refresh['rol'] = perfil.rol.codigo
    # access_token copia los claims del refresh.
    return str(refresh.access_token), str(refresh)


def poner_cookie(response, nombre, valor, segundos):
    response.set_cookie(
        nombre, valor, max_age=segundos,
        httponly=settings.AUTH_COOKIE_HTTPONLY,  # JS no puede leerla
        secure=settings.AUTH_COOKIE_SECURE,      # solo HTTPS fuera de DEBUG
        samesite=settings.AUTH_COOKIE_SAMESITE,  # no se manda en requests de otros sitios
        path='/',
    )


def poner_cookies(response, access, refresh):
    jwt = settings.SIMPLE_JWT
    poner_cookie(response, settings.AUTH_COOKIE_ACCESS_NAME, access,
                  int(jwt['ACCESS_TOKEN_LIFETIME'].total_seconds()))
    poner_cookie(response, settings.AUTH_COOKIE_REFRESH_NAME, refresh,
                  int(jwt['REFRESH_TOKEN_LIFETIME'].total_seconds()))


def borrar_cookies(response):
    response.delete_cookie(settings.AUTH_COOKIE_ACCESS_NAME, path='/')
    response.delete_cookie(settings.AUTH_COOKIE_REFRESH_NAME, path='/')


def invalidar_refresh(request):
    """Logout real: mete el refresh token en la lista negra para que no se
    pueda reutilizar aunque alguien lo hubiera copiado."""
    refresh = request.COOKIES.get(settings.AUTH_COOKIE_REFRESH_NAME)
    if refresh:
        try:
            RefreshToken(refresh).blacklist()
        except TokenError:
            pass


# --- Lectura de cookies -----------------------------------------------------

def _perfil_valido(request, user_id, tienda_id_del_token):
    """Revisa contra la BD que el usuario puede actuar en ESTE host."""
    perfil = (
        PerfilUsuario.objects
        .select_related('user', 'rol', 'tienda', 'tienda__plan')
        .filter(user_id=user_id).first()
    )
    if perfil is None or not perfil.habilitado or not perfil.user.is_active:
        return None  # cuenta dada de baja: el token deja de servir al instante

    tienda = getattr(request, 'tienda', None)
    if perfil.rol.codigo == Rol.ADMIN_GENERAL:
        # El admin general solo opera en la plataforma, no dentro de una tienda.
        return perfil if tienda is None else None
    # Admin de tienda y cliente: solo en SU tienda (y el token debe decir lo mismo).
    if tienda is None or perfil.tienda_id != tienda.id or tienda_id_del_token != tienda.id:
        return None
    return perfil


def perfil_desde_cookies(request):
    """Devuelve (perfil, access_nuevo). perfil es None si no hay sesión válida.
    access_nuevo trae un token si hubo que renovar el access con el refresh."""
    access = request.COOKIES.get(settings.AUTH_COOKIE_ACCESS_NAME)
    if access:
        try:
            token = AccessToken(access)  # valida firma y expiración
            return _perfil_valido(request, token['user_id'], token.get('tienda_id')), None
        except TokenError:
            pass  # access vencido o falso: se intenta con el refresh

    refresh = request.COOKIES.get(settings.AUTH_COOKIE_REFRESH_NAME)
    if refresh:
        try:
            token = RefreshToken(refresh)  # también revisa la lista negra
            perfil = _perfil_valido(request, token['user_id'], token.get('tienda_id'))
            if perfil:
                return perfil, str(token.access_token)
        except TokenError:
            pass
    return None, None


# --- Bloqueo por intentos fallidos (fuerza bruta) ----------------------------

def _clave(host, email):
    return f'login-fallos:{host}:{email.strip().lower()}'


def login_bloqueado(host, email):
    return cache.get(_clave(host, email), 0) >= MAX_INTENTOS


def registrar_fallo(host, email):
    clave = _clave(host, email)
    cache.set(clave, cache.get(clave, 0) + 1, BLOQUEO_SEGUNDOS)


def limpiar_fallos(host, email):
    cache.delete(_clave(host, email))
