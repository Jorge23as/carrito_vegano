"""Portada y manejo de errores.

Requisito de la prueba: escribir cualquier URL basura no debe romper nada.
Django llama a estos handlers cuando no encuentra la URL (404), no hay permiso
(403), falla algo interno (500) o falla el token CSRF.
"""

from django.http import JsonResponse
from django.shortcuts import render
from django.template.loader import render_to_string
from django.http import HttpResponse

from catalogo.views import catalogo
from tiendas.views import home_plataforma


def inicio(request):
    """La misma URL "/" muestra cosas distintas según el host:
    dentro de una tienda -> su catálogo; en la plataforma -> lista de tiendas."""
    if request.tienda is not None:
        return catalogo(request)
    return home_plataforma(request)


def _es_api(request):
    return request.path.startswith('/api/')


def error_404(request, exception=None):
    if _es_api(request):
        return JsonResponse({'error': 'Recurso no encontrado.'}, status=404)
    # La plantilla incluye una redirección automática al inicio a los 6 segundos.
    return render(request, 'errores/404.html', status=404)


def error_403(request, exception=None):
    if _es_api(request):
        return JsonResponse({'error': 'No tienes permiso para esto.'}, status=403)
    return render(request, 'errores/403.html', status=403)


def error_400(request, exception=None):
    if _es_api(request):
        return JsonResponse({'error': 'Solicitud inválida.'}, status=400)
    return render(request, 'errores/404.html', {'mensaje': 'La solicitud no es válida.'}, status=400)


def error_csrf(request, reason=''):
    return render(request, 'errores/403.html', {
        'mensaje': 'Tu formulario expiró o no es válido. Recarga la página e inténtalo de nuevo.',
    }, status=403)


def error_500(request):
    # Se renderiza SIN contexto ni request a propósito: si el error vino de la
    # BD o de un middleware, usar tienda/usuario podría fallar otra vez.
    return HttpResponse(render_to_string('errores/500.html'), status=500)
