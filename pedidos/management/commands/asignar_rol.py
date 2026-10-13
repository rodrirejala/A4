from django.contrib.auth.models import User
from django.core.management.base import BaseCommand, CommandError

from pedidos import roles


class Command(BaseCommand):
    help = 'Asigna (o quita) un rol a un usuario existente.'

    def add_arguments(self, parser):
        parser.add_argument('username')
        parser.add_argument('rol', choices=roles.ROLES)

    def handle(self, *args, **options):
        roles.asegurar_grupos()
        username = options['username']
        rol = options['rol']

        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            raise CommandError(f'No existe el usuario "{username}".')

        grupo = user.groups.filter(name=rol).first()
        if grupo:
            self.stdout.write(
                self.style.WARNING(f'"{username}" ya tenía el rol {rol}.')
            )
        else:
            user.groups.add(rol)
            self.stdout.write(self.style.SUCCESS(f'Rol {rol} asignado a "{username}".'))

        self.stdout.write(f'Roles actuales: {", ".join(roles.roles_de(user)) or "ninguno"}')