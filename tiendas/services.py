"""
Lógica de negocio de tiendas y usuarios.

Está separada de las vistas a propósito: tanto las páginas (templates) como la
API (DRF) llaman a estas mismas funciones, así las reglas se escriben una sola vez.
"""

from django.contrib.auth import authenticate
from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.db import transaction

from core.errores import ErrorNegocio
from tiendas.models import PerfilUsuario, Rol, Tienda


def nombre_usuario(tienda, email):
    """auth.User exige username único en TODA la base, pero el mismo correo
    puede ser cliente de dos tiendas distintas. Por eso el username lleva el
    slug de la tienda: 'raiz__ana@correo.cl'. El admin general no tiene tienda."""
    email = email.strip().lower()
    return f'{tienda.slug}__{email}' if tienda else email


@transaction.atomic
def crear_usuario_perfil(*, tienda, rol_codigo, email, password, nombres,
                         apellido_paterno, apellido_materno='',
                         fecha_nacimiento=None, telefono=''):
    """Crea auth.User + PerfilUsuario juntos (o ninguno, por el atomic)."""
    username = nombre_usuario(tienda, email)
    if User.objects.filter(username=username).exists():
        raise ErrorNegocio('Ya existe una cuenta con ese correo.')
    try:
        validate_password(password)
    except ValidationError as error:
        raise ErrorNegocio(' '.join(error.messages))

    user = User.objects.create_user(username=username, email=email.strip().lower(), password=password)
    return PerfilUsuario.objects.create(
        user=user, rol=Rol.objects.get(codigo=rol_codigo), tienda=tienda,
        nombres=nombres, apellido_paterno=apellido_paterno,
        apellido_materno=apellido_materno, fecha_nacimiento=fecha_nacimiento,
        telefono=telefono,
    )


def registrar_cliente(tienda, **datos):
    """Autoregistro: el cliente se crea a sí mismo con permisos mínimos."""
    return crear_usuario_perfil(tienda=tienda, rol_codigo=Rol.CLIENTE, **datos)


@transaction.atomic
def crear_tienda_con_admin(*, nombre, slug, plan, admin, color_primario='#1B4332',
                           dominio_propio=None, logo=None):
    """Regla de la jerarquía: al crear una tienda se crea AUTOMÁTICAMENTE su
    admin de tienda. Solo el admin general llega hasta acá (ver vistas)."""
    tienda = Tienda(nombre=nombre, slug=slug, plan=plan, color_primario=color_primario,
                    dominio_propio=dominio_propio or None)
    if logo:
        tienda.logo = logo
    tienda.full_clean()
    tienda.save()
    perfil = crear_usuario_perfil(tienda=tienda, rol_codigo=Rol.ADMIN_TIENDA, **admin)
    return tienda, perfil


@transaction.atomic
def reasignar_admin_tienda(tienda, **admin):
    """Si el admin de una tienda desaparece, el admin general designa a otro.
    Los admins anteriores se dan de baja (baja lógica, no se borran)."""
    for anterior in tienda.perfiles.filter(rol__codigo=Rol.ADMIN_TIENDA, habilitado=True):
        anterior.dar_de_baja()
    return crear_usuario_perfil(tienda=tienda, rol_codigo=Rol.ADMIN_TIENDA, **admin)


def autenticar_credenciales(tienda, email, password):
    """Valida correo+contraseña Y que la persona pertenezca a este host.
    Devuelve (user, perfil) o lanza ErrorNegocio con un mensaje genérico
    (no se dice si falló el correo o la clave, para no ayudar a un atacante)."""
    user = authenticate(username=nombre_usuario(tienda, email), password=password)
    perfil = getattr(user, 'perfil', None) if user else None

    if perfil and perfil.habilitado:
        en_plataforma = tienda is None and perfil.rol.codigo == Rol.ADMIN_GENERAL
        en_su_tienda = (
            tienda is not None and perfil.tienda_id == tienda.id
            and perfil.rol.codigo in (Rol.ADMIN_TIENDA, Rol.CLIENTE)
        )
        if en_plataforma or en_su_tienda:
            return user, perfil
    raise ErrorNegocio('Correo o contraseña incorrectos.')


def crear_admin_general(*, email, password, nombres, apellido_paterno, apellido_materno=''):
    return crear_usuario_perfil(
        tienda=None, rol_codigo=Rol.ADMIN_GENERAL, email=email, password=password,
        nombres=nombres, apellido_paterno=apellido_paterno, apellido_materno=apellido_materno,
    )
