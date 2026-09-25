# Plataforma de tiendas online multi-tenant (SaaS)

Prueba 2 — Desarrollo Backend (INACAP). Django 6.1 + Django REST Framework + JWT + MySQL/MariaDB.

Cada tienda es un **tenant**: tiene su subdominio (`demo.localhost:8000`), sus productos,
clientes, carritos, pedidos, color y logo. Todo vive en una sola base de datos y se separa
por la columna `tienda`.

## Cómo levantarlo

```bash
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env            # y completar SECRET_KEY y credenciales de la BD
mysql -u root -e "CREATE DATABASE tienda_multitenant CHARACTER SET utf8mb4;
  CREATE USER 'tienda_app'@'localhost' IDENTIFIED BY 'tu-clave';
  GRANT ALL ON tienda_multitenant.* TO 'tienda_app'@'localhost';"
python manage.py migrate
python manage.py reset_demo     # crea admin general + tienda demo con datos
python manage.py runserver
```

Los navegadores resuelven `*.localhost` solos; no hace falta tocar `/etc/hosts`.

| Qué | Dónde | Usuario | Contraseña |
|---|---|---|---|
| Plataforma (admin general) | http://localhost:8000/login/ | admin@plataforma.cl | Demo12345! |
| Tienda demo — admin de tienda | http://demo.localhost:8000/login/ | admin@demo.cl | Demo12345! |
| Tienda demo — cliente | http://demo.localhost:8000/login/ | cliente@demo.cl | Demo12345! |
| Documentación de la API | http://localhost:8000/api/docs/ | | |

(Contraseñas solo de demostración.) Tests: `python manage.py test` (53 tests).

## Requisitos de la prueba → dónde están

| Requisito | Implementación |
|---|---|
| 3FN, nombres separados, catálogos | `*/models.py`: `Rol`, `Plan`, `EstadoCarrito`, `EstadoPedido`, `Categoria` son tablas; `PerfilUsuario` tiene `nombres`, `apellido_paterno`, `apellido_materno` |
| Todo con templates | `templates/` (base + páginas); las vistas renderizan en el servidor |
| Comentarios en el código | Cada módulo explica el porqué de sus decisiones |
| JWT obligatorio | `core/auth.py` (cookies HttpOnly) + `core/middleware.py` |
| Endpoints públicos y protegidos | Catálogo público; carrito, pedidos, clientes y paneles protegidos (`core/permisos.py`) |
| 404 controlado + redirección | `core/views.py`, `templates/errores/404.html` (redirige al inicio a los 8 s) |
| Borrado lógico siempre | `core/models.py`: `BajaLogicaModel` convierte todo `.delete()` en `habilitado=False` |
| Carrito por tienda y usuario | `ventas/services.py::carrito_abierto` busca por (tienda, cliente) |
| Jerarquía de usuarios | `tiendas/services.py`: general → admin de tienda (se crea con la tienda) → clientes (autoregistro) |
| Color y logo por tienda | `/panel/configuracion/`; el color entra al CSS como variable (`templates/base.html`) |
| Dashboard general y de tienda | `/plataforma/` y `/panel/` |
| Plan de suscripción con funciones recortadas | `Plan.max_productos`, validado al crear productos |
| Sandbox que vuelve al estado original | `python manage.py reset_demo` o botón "Reiniciar demo" |
| Métrica de rendimiento | `core/middleware.py::MetricasMiddleware` → tabla `Metrica` |
| Dominio propio por tienda | `Tienda.dominio_propio` (resuelto en `TenantMiddleware`) |
| Optimización de imágenes | `core/imagenes.py`: reduce a máx. 800 px y WebP (8 MB → ~50-150 KB) |

**No implementado** (el profe lo marcó como "suma", no obligatorio): pronóstico de ventas,
carga masiva CSV, demo de 1 mes con vencimiento, Nginx/Gunicorn con balanceo.

## SLA (nivel de servicio objetivo)

| Indicador | Objetivo |
|---|---|
| Disponibilidad mensual | 99,5 % |
| Tiempo de respuesta (promedio por tienda) | < 500 ms — se mide con el middleware y se ve en el panel general |
| Recuperación ante falla | < 4 horas |
| Respaldo de la base de datos | Diario |
| Soporte | Lunes a viernes, horario laboral |

El panel general muestra el tiempo de respuesta real por tienda para verificar el segundo indicador.
# carrito_vegano
