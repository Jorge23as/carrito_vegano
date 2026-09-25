"""Validación y optimización de imágenes subidas (logos y productos)."""

from io import BytesIO

from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from PIL import Image

TAMANO_MAXIMO_MB = 8


def validar_tamano(archivo):
    if archivo.size > TAMANO_MAXIMO_MB * 1024 * 1024:
        raise ValidationError(f'La imagen no puede pesar más de {TAMANO_MAXIMO_MB} MB.')


def optimizar(archivo, max_px=800):
    """Reduce una imagen subida (ej. 8 MB) a algo liviano para web (~50-150 KB).

    - la achica a máx. `max_px` de ancho/alto manteniendo proporción
    - la guarda como WebP calidad 80 (mucho más liviana que PNG/JPG)
    Devuelve un ContentFile listo para asignar al ImageField.
    """
    imagen = Image.open(archivo)
    imagen.thumbnail((max_px, max_px))
    salida = BytesIO()
    imagen.save(salida, format='WEBP', quality=80)
    return ContentFile(salida.getvalue(), name='imagen.webp')
