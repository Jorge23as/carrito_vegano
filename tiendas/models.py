"""
Modelos de identidad y multi-tenant.

Diseño (3FN):
- Rol y Plan son CATÁLOGOS: tablas propias en vez de campos de texto/choices.
- Tienda es el "tenant": cada tienda es un cliente de la plataforma SaaS.
- PerfilUsuario extiende a auth.User (que ya maneja contraseña y login) con
  los datos personales (nombres separados) y a qué tienda pertenece.
"""

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator
from django.db import models

from core.imagenes import validar_tamano
from core.models import BajaLogicaModel, BajaLogicaQuerySet

# El color se inyecta en el CSS de la página, por eso se valida estrictamente
# (#RRGGBB). Sin esto, un admin de tienda podría meter CSS/JS malicioso.
validar_color_hex = RegexValidator(
    r'^#[0-9A-Fa-f]{6}$', 'Usa un color hexadecimal, por ejemplo #1B4332.'
)

# Un subdominio válido: minúsculas, números y guiones (sin _ ni espacios).
validar_subdominio = RegexValidator(
    r'^[a-z0-9]([a-z0-9-]{0,28}[a-z0-9])?$',
    'Solo minúsculas, números y guiones (sin espacios ni guion bajo).',
)

SUBDOMINIOS_RESERVADOS = {'www', 'admin', 'api', 'static', 'media', 'plataforma'}


def validar_subdominio_libre(valor):
    if valor in SUBDOMINIOS_RESERVADOS:
        raise ValidationError('Ese subdominio está reservado.')


class Rol(models.Model):
    """Catálogo de roles. Se cargan en la migración inicial."""

    ADMIN_GENERAL = 'ADMIN_GENERAL'
    ADMIN_TIENDA = 'ADMIN_TIENDA'
    CLIENTE = 'CLIENTE'

    codigo = models.CharField(max_length=30, unique=True)
    nombre = models.CharField(max_length=60)

    def __str__(self):
        return self.nombre


class Plan(models.Model):
    """Catálogo de planes de suscripción: cada plan recorta funciones.
    Acá el recorte es la cantidad máxima de productos activos."""

    nombre = models.CharField(max_length=60, unique=True)
    precio_mensual = models.PositiveIntegerField(help_text='En pesos chilenos.')
    max_productos = models.PositiveIntegerField()

    def __str__(self):
        return self.nombre


class Tienda(BajaLogicaModel):
    """Un tenant. Se identifica por subdominio (slug.localhost) o por un
    dominio propio (ej. zapatilleate.cl)."""

    nombre = models.CharField(max_length=100)
    slug = models.CharField(
        'subdominio', max_length=30, unique=True,
        validators=[validar_subdominio, validar_subdominio_libre],
    )
    dominio_propio = models.CharField(max_length=253, unique=True, null=True, blank=True)
    color_primario = models.CharField(
        max_length=7, default='#1B4332', validators=[validar_color_hex]
    )
    logo = models.ImageField(upload_to='logos/', blank=True, validators=[validar_tamano])
    plan = models.ForeignKey(Plan, on_delete=models.PROTECT, related_name='tiendas')
    fecha_creacion = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.nombre


class PerfilQuerySet(BajaLogicaQuerySet):
    def delete(self):
        # Dar de baja perfiles también bloquea el login (auth.User.is_active).
        User.objects.filter(perfil__in=self).update(is_active=False)
        return super().delete()


class PerfilUsuario(BajaLogicaModel):
    """Datos de la persona + su rol + su tienda.

    - admin general:  tienda = NULL (no pertenece a ninguna tienda)
    - admin de tienda / cliente: tienda obligatoria
    """

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='perfil')
    rol = models.ForeignKey(Rol, on_delete=models.PROTECT, related_name='perfiles')
    tienda = models.ForeignKey(
        Tienda, null=True, blank=True, on_delete=models.CASCADE, related_name='perfiles'
    )
    # Nombres separados (3FN / atomicidad): nada de un solo campo "nombre".
    nombres = models.CharField(max_length=100)
    apellido_paterno = models.CharField(max_length=60)
    apellido_materno = models.CharField(max_length=60, blank=True)
    fecha_nacimiento = models.DateField(null=True, blank=True)
    telefono = models.CharField(max_length=20, blank=True)

    objects = PerfilQuerySet.as_manager()

    def __str__(self):
        return self.nombre_completo

    @property
    def nombre_completo(self):
        partes = [self.nombres, self.apellido_paterno, self.apellido_materno]
        return ' '.join(p for p in partes if p)

    @property
    def iniciales(self):
        return (self.nombres[:1] + self.apellido_paterno[:1]).upper()

    @property
    def email(self):
        return self.user.email

    def clean(self):
        # Regla de la jerarquía: solo el admin general no tiene tienda.
        if self.rol_id and self.rol.codigo == Rol.ADMIN_GENERAL and self.tienda_id:
            raise ValidationError('El admin general no pertenece a ninguna tienda.')
        if self.rol_id and self.rol.codigo != Rol.ADMIN_GENERAL and not self.tienda_id:
            raise ValidationError('Admins de tienda y clientes necesitan una tienda.')

    def dar_de_baja(self):
        super().dar_de_baja()
        User.objects.filter(pk=self.user_id).update(is_active=False)

    def reactivar(self):
        super().reactivar()
        User.objects.filter(pk=self.user_id).update(is_active=True)
