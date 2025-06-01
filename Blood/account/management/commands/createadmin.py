from django.core.management.base import BaseCommand
from account.models import User

class Command(BaseCommand):
    help = 'Create a default admin user if it does not exist'

    def handle(self, *args, **kwargs):
        username = 'admin'
        email = 'admin@example.com'
        password = 'admin'
        if not User.objects.filter(username=username).exists():
            admin_user = User.objects.create_user(
                username=username,
                email=email,
                password=password,
                role='ADMIN'
            )
            admin_user.is_staff = True
            admin_user.is_superuser = True
            admin_user.save()
            self.stdout.write(self.style.SUCCESS('Default admin user created successfully.'))
        else:
            self.stdout.write(self.style.WARNING('Default admin user already exists.'))
