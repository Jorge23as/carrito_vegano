"""Carga los catálogos base: roles y planes de suscripción.
Es una migración de datos: corre sola con `migrate`, también en la BD de tests."""

from django.db import migrations

ROLES = [
    ('ADMIN_GENERAL', 'Administrador general'),
    ('ADMIN_TIENDA', 'Administrador de tienda'),
    ('CLIENTE', 'Cliente'),
]

PLANES = [
    # (nombre, precio mensual CLP, máximo de productos activos)
    ('Básico', 50000, 20),
    ('Pro', 100000, 100),
    ('Premium', 120000, 1000),
]


def cargar(apps, schema_editor):
    Rol = apps.get_model('tiendas', 'Rol')
    Plan = apps.get_model('tiendas', 'Plan')
    for codigo, nombre in ROLES:
        Rol.objects.get_or_create(codigo=codigo, defaults={'nombre': nombre})
    for nombre, precio, maximo in PLANES:
        Plan.objects.get_or_create(
            nombre=nombre, defaults={'precio_mensual': precio, 'max_productos': maximo}
        )


class Migration(migrations.Migration):
    dependencies = [('tiendas', '0001_initial')]
    operations = [migrations.RunPython(cargar, migrations.RunPython.noop)]
