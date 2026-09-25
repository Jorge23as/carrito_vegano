from django.core.management.base import BaseCommand, CommandError

from core.errores import ErrorNegocio
from tiendas import services


class Command(BaseCommand):
    help = 'Crea un administrador general de la plataforma (no existe registro público para esto).'

    def add_arguments(self, parser):
        parser.add_argument('--email', required=True)
        parser.add_argument('--password', required=True)
        parser.add_argument('--nombres', required=True)
        parser.add_argument('--apellido-paterno', required=True)
        parser.add_argument('--apellido-materno', default='')

    def handle(self, *args, **o):
        try:
            services.crear_admin_general(
                email=o['email'], password=o['password'], nombres=o['nombres'],
                apellido_paterno=o['apellido_paterno'], apellido_materno=o['apellido_materno'])
        except ErrorNegocio as error:
            raise CommandError(str(error))
        self.stdout.write(self.style.SUCCESS('Admin general creado.'))
