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
    path('bulk-return-containers/', views.bulk_return_containers, name='bulk_return_containers'),
    path('delete-container/<int:container_id>/', views.delete_container, name='delete_container'),
    path('export-clients-csv/', views.export_clients_csv, name='export_clients_csv'),
    path('export-orders-csv/', views.export_orders_csv, name='export_orders_csv'),
    path('export-orders-by-day-csv/', views.export_orders_by_day_csv, name='export_orders_by_day_csv'),
    path('export-revenue-by-month-csv/', views.export_revenue_by_month_csv, name='export_revenue_by_month_csv'),
    path('export-containers-csv/', views.export_containers_csv, name='export_containers_csv'),
    path('export-orders-xlsx/', views.export_orders_xlsx, name='export_orders_xlsx'),
    path('export-containers-xlsx/', views.export_containers_xlsx, name='export_containers_xlsx'),
    path('create-product/', views.create_product, name='create_product'),
    path('driver-dashboard/', views.driver_dashboard, name='driver_dashboard'),
    path('reports/', views.reports, name='reports'),
    path('api/', include(router.urls)),
    path('api/orders/<int:order_id>/update/', views.api_update_order, name='api_update_order'),
]