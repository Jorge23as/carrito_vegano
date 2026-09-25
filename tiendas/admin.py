from django.contrib import admin

from tiendas.models import PerfilUsuario, Plan, Rol, Tienda

# El admin de Django es solo una herramienta de depuración: el borrado de estos
# modelos es baja lógica (ver core.models.BajaLogicaModel).
admin.site.register([Rol, Plan, Tienda, PerfilUsuario])
