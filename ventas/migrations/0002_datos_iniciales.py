"""Carga los catálogos de estados de carrito y de pedido."""

from django.db import migrations

ESTADOS_CARRITO = [('ABIERTO', 'Abierto'), ('CERRADO', 'Cerrado')]
ESTADOS_PEDIDO = [
    ('PAGADO', 'Pagado'), ('ENVIADO', 'Enviado'),
    ('ENTREGADO', 'Entregado'), ('CANCELADO', 'Cancelado'),
]


def cargar(apps, schema_editor):
    EstadoCarrito = apps.get_model('ventas', 'EstadoCarrito')
    EstadoPedido = apps.get_model('ventas', 'EstadoPedido')
    for codigo, nombre in ESTADOS_CARRITO:
        EstadoCarrito.objects.get_or_create(codigo=codigo, defaults={'nombre': nombre})
    for codigo, nombre in ESTADOS_PEDIDO:
        EstadoPedido.objects.get_or_create(codigo=codigo, defaults={'nombre': nombre})


class Migration(migrations.Migration):
    dependencies = [('ventas', '0001_initial')]
    operations = [migrations.RunPython(cargar, migrations.RunPython.noop)]
