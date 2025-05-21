def export_orders_by_day_csv(request):
    orders = Order.objects.all()
    orders_by_day = (
        orders
        .annotate(day=TruncDay('order_date'))
        .values('day')
        .annotate(count=Count('id'))
        .order_by('day')
    )
    
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="orders_by_day.csv"'
    
    writer = csv.writer(response)
    writer.writerow(['День', 'Количество заказов'])
    
    for entry in orders_by_day:
        writer.writerow([entry['day'].strftime('%Y-%m-%d'), entry['count']])
    
    return response
