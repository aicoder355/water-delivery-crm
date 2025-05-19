from django.urls import re_path
from . import consumers

websocket_urlpatterns = [
    re_path(r'ws/driver/$', consumers.DriverNotificationConsumer.as_asgi()),
    re_path(r'ws/driver/notifications/$', consumers.DriverNotificationConsumer.as_asgi()),
]
