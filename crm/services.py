from .models import Notification, Order, Client

class NotificationService:
    @staticmethod
    def create_notification(client, notification_type, title, message):
        return Notification.objects.create(
            client=client,
            notification_type=notification_type,
            title=title,
            message=message
        )
    
    @staticmethod
    def notify_order_status(order):
        """Создает уведомление при изменении статуса заказа"""
        status_messages = {
            'NEW': 'Ваш заказ принят в обработку',
            'CONFIRMED': 'Заказ подтвержден и готовится к отправке',
            'IN_DELIVERY': 'Ваш заказ в пути',
            'DELIVERED': 'Заказ успешно доставлен',
            'CANCELLED': 'Заказ отменен',
        }
        
        message = status_messages.get(order.status, 'Статус заказа изменен')
        title = f'Заказ №{order.id} - {message}'
        
        return NotificationService.create_notification(
            client=order.client,
            notification_type='ORDER_STATUS',
            title=title,
            message=f'{message}. Текущий статус: {order.get_status_display()}'
        )
    
    @staticmethod
    def notify_loyalty_points(transaction):
        """Создает уведомление о начислении/списании баллов"""
        action = 'начислено' if transaction.points > 0 else 'списано'
        points = abs(transaction.points)
        
        title = f'{points} баллов {action}'
        message = f'На ваш счет {action} {points} баллов лояльности. ' \
                 f'Текущий баланс: {transaction.client.loyalty_points} баллов'
        
        return NotificationService.create_notification(
            client=transaction.client,
            notification_type='LOYALTY_POINTS',
            title=title,
            message=message
        )
