import os
from django.core.wsgi import get_wsgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "samda_accounts.settings")

application = get_wsgi_application()
