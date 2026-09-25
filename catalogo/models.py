"""
Catálogo de productos de cada tienda.

Categoria es un catálogo (tabla propia) y pertenece a UNA tienda: cada tienda
maneja sus propias categorías. Todo lleva `tienda` para poder filtrar con
.de_tienda(request.tienda) y garantizar el aislamiento entre tenants.
"""

from django.db import models

from core.imagenes import validar_tamano
from core.models import BajaLogicaModel
from tiendas.models import Tienda

# Bajo este stock el producto aparece en el dashboard como "quiebre de stock".
UMBRAL_STOCK_BAJO = 5


class Categoria(BajaLogicaModel):
    tienda = models.ForeignKey(Tienda, on_delete=models.CASCADE, related_name='categorias')
    nombre = models.CharField(max_length=80)

    class Meta:
        ordering = ['nombre']
        constraints = [
            models.UniqueConstraint(fields=['tienda', 'nombre'], name='categoria_unica_por_tienda'),
        ]

    def __str__(self):
        return self.nombre


class Producto(BajaLogicaModel):
    tienda = models.ForeignKey(Tienda, on_delete=models.CASCADE, related_name='productos')
    categoria = models.ForeignKey(Categoria, on_delete=models.RESTRICT, related_name='productos')
    nombre = models.CharField(max_length=120)
    descripcion = models.TextField(blank=True)
    precio = models.PositiveIntegerField(help_text='En pesos chilenos.')
    stock = models.PositiveIntegerField(default=0)
    imagen = models.ImageField(upload_to='productos/', blank=True, validators=[validar_tamano])

    class Meta:
        ordering = ['nombre']

    def __str__(self):
        return self.nombre

    @property
    def stock_bajo(self):
        return self.stock <= UMBRAL_STOCK_BAJO
