# Guía de estudio para la defensa

Léela con el código abierto. Si puedes explicar cada sección con tus palabras, estás listo.

## 1. La idea en una frase
Una sola aplicación Django atiende a muchas tiendas. Mirando el **subdominio** del request decide
de qué tienda es, y todas las consultas se filtran por esa tienda.

## 2. Recorrido de un request (lo más probable que te pidan)
Ejemplo: un cliente abre `demo.localhost:8000/carrito/`. Sale en `tienda_project/settings.py`, lista `MIDDLEWARE`:

1. **MetricasMiddleware** (`core/middleware.py`) parte un cronómetro.
2. **TenantMiddleware** lee el header `Host`, busca la tienda con slug `demo` y deja `request.tienda`.
   Si no existe → 404; si está dada de baja → 403.
3. Sesión, CSRF y auth de Django (el CSRF valida los POST de formularios).
4. **JWTAuthMiddleware** lee la cookie `access_token`, valida firma y expiración, y consulta la BD:
   ¿el usuario está habilitado? ¿pertenece a la tienda `demo`? Si todo calza deja `request.perfil`.
5. La URL (`ventas/urls.py`) llama a `ver_carrito`, decorada con `@requiere_rol(CLIENTE)`
   (`core/permisos.py`): sin sesión → redirige al login; rol equivocado → 403.
6. La vista pide el carrito con `carrito_abierto(perfil)` (`ventas/services.py`) y renderiza el template.
7. MetricasMiddleware guarda cuánto tardó.

## 3. Autenticación vs autorización
- **Autenticación** = quién eres → login + JWT. **Autorización** = qué puedes hacer → roles/permisos.
- No es "cada endpoint pide login": el login se hace una vez y en cada request se **verifica** el token.
  Algunos endpoints son públicos (catálogo) y otros exigen un rol.
- Token en **cookie HttpOnly**, no en `localStorage`: un XSS puede leer `localStorage` con JavaScript,
  pero no una cookie HttpOnly. Costo: al usar cookies hay que proteger de **CSRF**
  (`CsrfViewMiddleware` en formularios; `enforce_csrf` en `tienda_project/authentication.py` para la API)
  y se usa `SameSite=Lax`.
- Dos tokens: **access** (30 min) y **refresh** (7 días). Si el access vence, el middleware pide uno nuevo
  con el refresh. Al hacer logout el refresh va a la **lista negra** (`token_blacklist`).
- **Un token válido no basta**: se comprueba que el usuario pertenezca a la tienda del subdominio
  (test `test_la_cookie_de_una_tienda_no_sirve_en_otra`). Sin eso, un cliente de la tienda A podría
  operar en la B (control de acceso roto / IDOR).

## 4. Multi-tenant
- Estrategia: **una BD, columna `tienda`** en cada tabla de negocio. Alternativas: una BD por tienda
  (más aislamiento, más costo operativo) o un esquema por tienda.
- El filtro es explícito: `Producto.objects.de_tienda(request.tienda)`. Se eligió explícito y no
  "mágico" (thread-local) porque es más fácil de leer y de testear.
- `get_object_or_404(Producto.objects.de_tienda(request.tienda), pk=...)`: pedir el id de un producto
  de otra tienda da 404, no revela que existe.
- El username de `auth.User` lleva el slug (`demo__ana@correo.cl`) porque el mismo correo puede ser
  cliente de dos tiendas.

## 5. Borrado lógico
`BajaLogicaModel` (`core/models.py`) agrega `habilitado` y `fecha_baja`, y **sobreescribe `delete()`**
(objeto y queryset) para hacer un `UPDATE`. Un test captura el SQL y comprueba que no hay ningún `DELETE`.
Banear a un usuario pone su perfil y su `auth.User` en inactivo: su sesión deja de funcionar en el
siguiente request, aunque el token no haya vencido. Única excepción consciente: `reset_demo`, una
herramienta de operador que solo toca la tienda demo.

## 6. Modelo de datos (3FN)
- Catálogos en tablas: `Rol`, `Plan`, `EstadoCarrito`, `EstadoPedido`, `Categoria`.
- `ItemCarrito` **no guarda el precio** (se lee del Producto; guardarlo repetiría un dato derivable).
  `ItemPedido` **sí guarda `precio_unitario`**: es el precio pagado ese día, un dato histórico que no
  se puede derivar porque el precio cambia. Esta diferencia es una pregunta clásica.
- `Tienda` y `PerfilUsuario.tienda` llevan `tienda` explícito aunque se pudiera inferir por otras FK,
  para filtrar con una sola condición.
- `on_delete`: `CASCADE` para lo que pertenece a una tienda, `PROTECT` para catálogos, `RESTRICT` para
  producto/categoría (impide borrarlos si están en uso, pero permite el borrado conjunto de `reset_demo`).

## 7. Seguridad: lista de lo que hay
| Medida | Dónde |
|---|---|
| JWT en cookie HttpOnly + SameSite | `core/auth.py` |
| CSRF en formularios y en la API | `settings.py`, `tienda_project/authentication.py` |
| Bloqueo por fuerza bruta (5 intentos / 5 min) | `core/auth.py` |
| Mensaje de error genérico en el login | `tiendas/services.py::autenticar_credenciales` |
| Open redirect bloqueado en `?next=` | `core/utils.py::destino_seguro` |
| Autoescape de templates (XSS) | Django; test `test_xss_en_nombre_de_producto_se_escapa` |
| Color validado `#RRGGBB` (evita inyectar CSS) | `tiendas/models.py::validar_color_hex` |
| Imágenes validadas con Pillow (no acepta SVG) y tamaño máximo | `core/imagenes.py` |
| Precios y totales calculados en el servidor | `ventas/services.py` |
| Stock protegido con `select_for_update` (dos compras simultáneas) | `ventas/services.py::pagar` |
| Logout por POST | `tiendas/views.py::logout_view` |
| Secretos en `.env` | `settings.py` |
| Cuentas de admin no se crean por endpoint público | `crear_admin_general` (comando) |

## 8. Preguntas que te pueden hacer
1. *¿Por qué JWT en cookie y no en localStorage?* → sección 3.
2. *¿Cómo evitas que la tienda A vea datos de la B?* → sección 4 y el test de cookie cruzada.
3. *¿Por qué `ItemPedido` guarda el precio y `ItemCarrito` no?* → sección 6.
4. *¿Qué pasa si dos clientes compran el último producto a la vez?* → `select_for_update` dentro de `transaction.atomic`.
5. *¿Qué es un middleware?* → código que corre en cada request antes/después de la vista; acá son 3.
6. *¿Qué es un servicio y por qué separarlo de la vista?* → `services.py`: la regla de negocio se escribe una vez y la usan las páginas y la API.
7. *¿Por qué PyMySQL y ese parche en `__init__.py`?* → el equipo no tenía los headers de compilación de `mysqlclient`; Django exige versión ≥ 2.2.1 y PyMySQL reporta la suya, así que se declara una compatible.
8. *¿Qué harías para escalar?* → Nginx como proxy inverso + Gunicorn con varios workers, caché (Redis) en vez de la memoria local para el contador de intentos, una BD por tienda grande.
9. *¿Qué es un SLA?* → contrato con niveles medibles; ver README.
10. *¿Qué NO hiciste?* → pronóstico de ventas, CSV, demo con vencimiento, balanceador. Es mejor decirlo tú.

## 9. Para practicar (haz esto tú, sin ayuda)
- Crea una tienda nueva desde el panel general y entra como su admin.
- Agrega un campo `descripcion_corta` a `Categoria`: modelo → `makemigrations` → formulario → template.
- Rompe una regla a propósito (quita `.de_tienda(...)` de una vista) y mira qué test falla.
- Corre `python manage.py test` y lee un test completo de cada clase.
