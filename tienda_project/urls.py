"""
Mapa de URLs del proyecto.

La misma URL puede significar cosas distintas según el host (ver
core.views.inicio): raiz.localhost:8000/ es el catálogo de la tienda "raiz";
localhost:8000/ es la portada de la plataforma.
"""

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

from core import views as core_views
from tienda_project import schema  # noqa: F401  (registra la autenticación por cookie en Swagger)

urlpatterns = [
    path('', core_views.inicio, name='inicio'),
    path('admin/', admin.site.urls),  # admin de Django: solo para depurar
    # Documentación interactiva de la API (Swagger).
    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
    path('api/docs/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
    path('api/', include('tienda_project.api_urls')),
    # Páginas (templates) de cada app.
    path('', include('tiendas.urls')),
    path('', include('catalogo.urls')),
    path('', include('ventas.urls')),
]

# En desarrollo Django sirve las imágenes subidas (logos y productos).
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

# Páginas de error controladas: cualquier URL basura cae acá y no rompe nada.
handler400 = 'core.views.error_400'
handler403 = 'core.views.error_403'
handler404 = 'core.views.error_404'
handler500 = 'core.views.error_500'
