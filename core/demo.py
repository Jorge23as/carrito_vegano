"""
Sandbox / tienda de demostración.

`reiniciar_demo()` deja la tienda "demo" exactamente como estaba al principio:
con su admin, clientes, categorías, productos y algunas ventas. Sirve para
mostrar el sistema sin miedo a "ensuciarlo": después de jugar, se reinicia.

ES LA ÚNICA EXCEPCIÓN a la regla de "nunca borrar": es una herramienta de
operador (comando / botón del admin general), no algo que un usuario pueda
disparar, y solo afecta a la tienda demo. Para borrar de verdad se llama a
models.Model.delete() saltándose el override de baja lógica.
"""

from django.conf import settings
from django.contrib.auth.models import User
from django.db import models, transaction

from catalogo.models import Categoria, Producto
from tiendas import services
from tiendas.models import PerfilUsuario, Plan, Rol, Tienda
from ventas import services as ventas_services

CLAVE_DEMO = 'Demo12345!'
EMAIL_ADMIN_DEMO = 'admin@demo.cl'
EMAIL_CLIENTE_DEMO = 'cliente@demo.cl'
EMAIL_ADMIN_GENERAL = 'admin@plataforma.cl'

PRODUCTOS = {
    'Verduras': [
        ('Caja de verduras orgánicas', 'Selección de temporada, 5 kg.', 14990, 25),
        ('Tomates cherry', 'Bandeja de 500 g.', 2490, 40),
        ('Palta Hass', 'Malla de 1 kg.', 4990, 3),
    ],
    'Veganos': [
        ('Leche de almendras', 'Sin azúcar, 1 L.', 3490, 30),
        ('Tofu ahumado', 'Paquete de 300 g.', 3990, 18),
        ('Hamburguesa de lentejas', 'Pack de 4 unidades.', 5490, 2),
    ],
}


def _borrar_tienda_demo():
    tienda = Tienda.objects.filter(slug=settings.TIENDA_DEMO_SLUG).first()
    if tienda is None:
        return
    # Primero los usuarios (arrastran perfiles, carritos y pedidos), después la tienda.
    ids = list(PerfilUsuario.objects.filter(tienda=tienda).values_list('user_id', flat=True))
    User.objects.filter(pk__in=ids).delete()
    models.Model.delete(tienda)  # borrado físico real, salta la baja lógica


@transaction.atomic
def reiniciar_demo():
    _borrar_tienda_demo()

    tienda, admin = services.crear_tienda_con_admin(
        nombre='Raíz Market', slug=settings.TIENDA_DEMO_SLUG, plan=Plan.objects.get(nombre='Pro'),
        color_primario='#1B4332',
        admin={'nombres': 'María', 'apellido_paterno': 'Jara', 'apellido_materno': 'Soto',
               'email': EMAIL_ADMIN_DEMO, 'password': CLAVE_DEMO},
    )
    for nombre_categoria, productos in PRODUCTOS.items():
        categoria = Categoria.objects.create(tienda=tienda, nombre=nombre_categoria)
        for nombre, descripcion, precio, stock in productos:
            Producto.objects.create(tienda=tienda, categoria=categoria, nombre=nombre,
                                    descripcion=descripcion, precio=precio, stock=stock)

    cliente = services.registrar_cliente(
        tienda, nombres='Camila', apellido_paterno='Rojas', apellido_materno='Vega',
        email=EMAIL_CLIENTE_DEMO, password=CLAVE_DEMO,
    )
    # Una venta inicial para que los dashboards no estén vacíos.
    for producto in Producto.objects.filter(tienda=tienda, nombre__in=['Tofu ahumado', 'Leche de almendras']):
        ventas_services.agregar_producto(cliente, producto.pk, 2)
    ventas_services.pagar(cliente)
    return tienda


def asegurar_admin_general():
    """Crea el admin general si todavía no existe (idempotente)."""
    if not PerfilUsuario.objects.filter(rol__codigo=Rol.ADMIN_GENERAL).exists():
        services.crear_admin_general(
            email=EMAIL_ADMIN_GENERAL, password=CLAVE_DEMO,
            nombres='Admin', apellido_paterno='General',
        )
