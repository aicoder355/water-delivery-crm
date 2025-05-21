from django import template
from crm.models import Notification

register = template.Library()

@register.simple_tag
def get_unread_notifications_count(user):
    if user.is_authenticated and hasattr(user, 'client'):
        return Notification.objects.filter(client=user.client, is_read=False).count()
    return 0
