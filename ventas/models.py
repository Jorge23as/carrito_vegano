"""
Carrito y pedidos.

- EstadoCarrito / EstadoPedido: catálogos (tablas), no campos de texto.
- Carrito: uno abierto por (tienda, cliente). Así el carrito es distinto por
  tienda Y por usuario dentro de la misma tienda.
- ItemCarrito NO guarda el precio: el precio se lee del Producto (guardarlo
  acá repetiría un dato derivable y rompería la 3FN).
- ItemPedido SÍ guarda precio_unitario: es un dato histórico (el precio que
  se pagó ese día), no derivable del Producto porque el precio cambia.
"""

from django.db import models

from core.models import BajaLogicaModel
from catalogo.models import Producto
from tiendas.models import PerfilUsuario, Tienda


class EstadoCarrito(models.Model):
    ABIERTO = 'ABIERTO'
    CERRADO = 'CERRADO'

    codigo = models.CharField(max_length=20, unique=True)
    nombre = models.CharField(max_length=40)

    def __str__(self):
        return self.nombre


class EstadoPedido(models.Model):
    PAGADO = 'PAGADO'
    ENVIADO = 'ENVIADO'
    ENTREGADO = 'ENTREGADO'
    CANCELADO = 'CANCELADO'

    codigo = models.CharField(max_length=20, unique=True)
    nombre = models.CharField(max_length=40)

    def __str__(self):
        return self.nombre


class Carrito(BajaLogicaModel):
    tienda = models.ForeignKey(Tienda, on_delete=models.CASCADE, related_name='carritos')
    cliente = models.ForeignKey(PerfilUsuario, on_delete=models.CASCADE, related_name='carritos')
    estado = models.ForeignKey(EstadoCarrito, on_delete=models.PROTECT)
    fecha_creacion = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'Carrito {self.pk} de {self.cliente}'

    @property
    def items_activos(self):
        return self.items.filter(habilitado=True).select_related('producto')

    @property
    def total(self):
        return sum(item.subtotal for item in self.items_activos)


class ItemCarrito(BajaLogicaModel):
    carrito = models.ForeignKey(Carrito, on_delete=models.CASCADE, related_name='items')
    producto = models.ForeignKey(Producto, on_delete=models.RESTRICT, related_name='items_carrito')
    cantidad = models.PositiveIntegerField(default=1)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['carrito', 'producto'], name='un_item_por_producto_y_carrito'),
        ]

    @property
    def subtotal(self):
        return self.cantidad * self.producto.precio


class Pedido(BajaLogicaModel):
    tienda = models.ForeignKey(Tienda, on_delete=models.CASCADE, related_name='pedidos')
    cliente = models.ForeignKey(PerfilUsuario, on_delete=models.CASCADE, related_name='pedidos')
    estado = models.ForeignKey(EstadoPedido, on_delete=models.PROTECT)
    total = models.PositiveIntegerField()
    fecha = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-fecha']

    def __str__(self):
        return f'Pedido #{self.pk}'


class ItemPedido(BajaLogicaModel):
    pedido = models.ForeignKey(Pedido, on_delete=models.CASCADE, related_name='items')
    producto = models.ForeignKey(Producto, on_delete=models.RESTRICT, related_name='items_pedido')
    cantidad = models.PositiveIntegerField()
    precio_unitario = models.PositiveIntegerField()

    @property
    def subtotal(self):
        return self.cantidad * self.precio_unitario
