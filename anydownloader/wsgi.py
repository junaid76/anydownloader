"""
WSGI config for anydownloader project.

It exposes the WSGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/6.0/howto/deployment/wsgi/
"""

import os

from django.core.wsgi import get_wsgi_application

# Default to development, override with DJANGO_SETTINGS_MODULE env var
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'anydownloader.settings.development')

application = get_wsgi_application()
