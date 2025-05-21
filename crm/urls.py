from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register(r'clients', views.ClientViewSet)
router.register(r'orders', views.OrderViewSet)
router.register(r'containers', views.ContainerViewSet)
router.register(r'drivers', views.DriverViewSet)
router.register(r'regions', views.RegionViewSet)

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('orders/', views.orders, name='orders'),
    path('create-order/', views.create_order, name='create_order'),
    path('edit-order/', views.edit_order, name='edit_order'),
    path('delete-order/<int:order_id>/', views.delete_order, name='delete_order'),
    path('drivers/', views.drivers, name='drivers'),
    path('create-driver/', views.create_driver, name='create_driver'),
    path('edit-driver/', views.edit_driver, name='edit_driver'),
    path('delete-driver/<int:driver_id>/', views.delete_driver, name='delete_driver'),
    path('regions/', views.regions, name='regions'),
    path('create-region/', views.create_region, name='create_region'),
    path('edit-region/', views.edit_region, name='edit_region'),
    path('delete-region/<int:region_id>/', views.delete_region, name='delete_region'),
    path('clients/', views.clients, name='clients'),
    path('create-client/', views.create_client, name='create_client'),
    path('edit-client/', views.edit_client, name='edit_client'),
    path('delete-client/<int:client_id>/', views.delete_client, name='delete_client'),
    path('containers/', views.containers, name='containers'),
    path('create-container/', views.create_container, name='create_container'),
    path('edit-container/', views.edit_container, name='edit_container'),
    path('return-container/<int:container_id>/', views.return_container, name='return_container'),
    path('bulk-return-containers/', views.bulk_return_containers, name='bulk_return_containers'),    path('delete-container/<int:container_id>/', views.delete_container, name='delete_container'),
    path('export-orders-by-day-csv/', views.export_orders_by_day_csv, name='export_orders_by_day_csv'),
    path('export-revenue-by-month-csv/', views.export_revenue_by_month_csv, name='export_revenue_by_month_csv'),
    path('create-product/', views.create_product, name='create_product'),
    path('driver-dashboard/', views.driver_dashboard, name='driver_dashboard'),
    path('routes/', views.routes, name='routes'),
    path('reports/', views.reports, name='reports'),
    path('export-orders-xlsx/', views.export_orders_xlsx, name='export_orders_xlsx'),
    path('export-containers-xlsx/', views.export_containers_xlsx, name='export_containers_xlsx'),
    path('create-route/', views.create_route, name='create_route'),
    path('route/<int:route_id>/', views.route_detail, name='route_detail'),
    path('api/', include(router.urls)),
    path('api/orders/<int:order_id>/update/', views.api_update_order, name='api_update_order'),
    path('notifications/', views.notifications_list, name='notifications_list'),
    path('notifications/<int:notification_id>/mark-read/', views.mark_notification_read, name='mark_notification_read'),
    path('loyalty/', views.loyalty_dashboard, name='loyalty_dashboard'),
    path('loyalty/program/new/', views.loyalty_program_edit, name='loyalty_program_new'),
    path('loyalty/program/<int:program_id>/', views.loyalty_program_edit, name='loyalty_program_edit'),
    path('loyalty/category/new/', views.loyalty_category_edit, name='loyalty_category_new'),
    path('loyalty/category/<int:category_id>/', views.loyalty_category_edit, name='loyalty_category_edit'),
    path('loyalty/transactions/', views.loyalty_transactions, name='loyalty_transactions'),
    path('attach-client-to-region/', views.attach_client_to_region, name='attach_client_to_region'),
]