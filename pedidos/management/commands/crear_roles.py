from django.contrib.auth.models import User
from django.core.management.base import BaseCommand

from pedidos import roles


class Command(BaseCommand):
    help = 'Crea los grupos de roles (Solicitante / Administrador) con sus permisos.'

    def handle(self, *args, **options):
        grupos = roles.asegurar_grupos()

        for rol, grupo in grupos.items():
            self.stdout.write(
                self.style.SUCCESS(f'Grupo "{rol}": {grupo.permissions.count()} permisos')
            )

        sin_grupo = User.objects.exclude(groups__in=list(grupos.values())).distinct()
        if superusuarios := list(User.objects.filter(is_superuser=True)):
            self.stdout.write(
                self.style.SUCCESS(
                    f'Superusuarios (acceso total): {", ".join(u.username for u in superusuarios)}'
                )
            )

        huerfanos = [u for u in sin_grupo if not u.is_superuser]
        if huerfanos:
            self.stdout.write(
                self.style.WARNING(
                    'Usuarios sin rol (no podrán acceder): '
                    + ', '.join(u.username for u in huerfanos)
                )
            )
            self.stdout.write(
                self.style.WARNING(
                    f'Asigná el rol desde /usuarios/ o con: '
                    f'python manage.py asignar_rol <usuario> {roles.GRUPO_ADMINISTRADOR}'
                )
            )