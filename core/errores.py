class ErrorNegocio(Exception):
    """Error esperado de una regla de negocio (stock insuficiente, correo
    repetido, credenciales inválidas...). Las vistas lo capturan y muestran
    el mensaje al usuario; no es un bug ni debe terminar en un 500."""
