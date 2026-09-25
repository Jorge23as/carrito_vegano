from django.contrib import admin

from catalogo.models import Categoria, Producto

admin.site.register([Categoria, Producto])
