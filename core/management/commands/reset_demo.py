from django.core.management.base import BaseCommand

from core.demo import CLAVE_DEMO, EMAIL_ADMIN_DEMO, EMAIL_ADMIN_GENERAL, EMAIL_CLIENTE_DEMO, asegurar_admin_general, reiniciar_demo


class Command(BaseCommand):
    help = 'Deja la tienda demo en su estado original (y crea el admin general si falta).'

    def handle(self, *args, **opciones):
        asegurar_admin_general()
        tienda = reiniciar_demo()
        self.stdout.write(self.style.SUCCESS(f'Tienda demo lista: http://{tienda.slug}.localhost:8000/'))
        self.stdout.write(f'  Admin general : {EMAIL_ADMIN_GENERAL}  (en http://localhost:8000/login/)')
        self.stdout.write(f'  Admin tienda  : {EMAIL_ADMIN_DEMO}')
        self.stdout.write(f'  Cliente       : {EMAIL_CLIENTE_DEMO}')
        self.stdout.write(f'  Contraseña de todos: {CLAVE_DEMO}')
