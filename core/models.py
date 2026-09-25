"""
Modelos compartidos por todas las apps.

Acá vive la regla más importante de la prueba: NUNCA se borra nada de verdad.
Todo modelo de negocio hereda de BajaLogicaModel, y "borrar" significa poner
habilitado=False (baja lógica). Así se conserva el historial (ej. un producto
dado de baja sigue apareciendo en pedidos antiguos).
"""

from django.db import models
from django.utils import timezone


class BajaLogicaQuerySet(models.QuerySet):
    """QuerySet que convierte cualquier .delete() en una baja lógica."""

    def delete(self):
        # update() hace un solo UPDATE en SQL; no se ejecuta ningún DELETE.
        n = self.update(habilitado=False, fecha_baja=timezone.now())
        return n, {self.model._meta.label: n}

    delete.alters_data = True

    def activos(self):
        """Solo los registros que no fueron dados de baja."""
        return self.filter(habilitado=True)

    def de_tienda(self, tienda):
        """Filtro multi-tenant: solo los registros de UNA tienda.

        Se usa siempre que se lee un modelo que tiene columna `tienda`, para
        que una tienda jamás vea datos de otra (aislamiento entre tenants).
        """
        return self.filter(tienda=tienda)


class BajaLogicaModel(models.Model):
    """Base abstracta: agrega habilitado + fecha_baja y bloquea el borrado físico."""

    habilitado = models.BooleanField(default=True, db_index=True)
    fecha_baja = models.DateTimeField(null=True, blank=True)

    objects = BajaLogicaQuerySet.as_manager()

    class Meta:
        abstract = True

    def dar_de_baja(self):
        self.habilitado = False
        self.fecha_baja = timezone.now()
        self.save(update_fields=['habilitado', 'fecha_baja'])

    def reactivar(self):
        self.habilitado = True
        self.fecha_baja = None
        self.save(update_fields=['habilitado', 'fecha_baja'])

    def delete(self, using=None, keep_parents=False):
        # Se sobreescribe delete(): aunque alguien llame obj.delete() (por
        # ejemplo el admin de Django), solo se da de baja.
        self.dar_de_baja()
        return 1, {self._meta.label: 1}


class Metrica(models.Model):
    """Una fila por request atendido: sirve para medir tiempos de respuesta
    por tienda (dashboard general) sin depender de herramientas externas."""

    tienda = models.ForeignKey(
        'tiendas.Tienda', null=True, blank=True,
        on_delete=models.CASCADE, related_name='metricas',
    )
    metodo = models.CharField(max_length=10)
    ruta = models.CharField(max_length=255)
    status = models.PositiveSmallIntegerField()
    duracion_ms = models.PositiveIntegerField()
    fecha = models.DateTimeField(auto_now_add=True, db_index=True)

    def __str__(self):
        return f'{self.metodo} {self.ruta} {self.status} {self.duracion_ms}ms'
