"""
ASGI config for water_delivery_crm project.

It exposes the ASGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/5.0/howto/deployment/asgi/
"""

import os
from django.core.asgi import get_asgi_application
from channels.routing import get_default_application
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'water_delivery_crm.settings')
from channels.routing import ProtocolTypeRouter, URLRouter
import water_delivery_crm.routing

application = ProtocolTypeRouter({
    "http": get_asgi_application(),
    "websocket": URLRouter(water_delivery_crm.routing.application.application['websocket'].application_mapping),
})
