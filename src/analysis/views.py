from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.db.models import Count, Sum, Q
from products.models import PillItem, Product
from accounts.models import YEAR_CHOICES
from .serializers import SalesAnalyticsSerializer, BestSellerProductSerializer


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def sales_analytics(request):
    """
    Get sales analytics from paid PillItems
    
    Query Parameters:
    - ordering: 'ascend' or 'descend' (default: 'descend')
    - limit: number to limit results per list (default: no limit)
    - date_from: filter from this date (format: YYYY-MM-DD)
    - date_to: filter to this date (format: YYYY-MM-DD)
    """
    # Get query parameters
    ordering = request.query_params.get('ordering', 'descend')
    limit = request.query_params.get('limit', None)
    date_from = request.query_params.get('date_from', None)
    date_to = request.query_params.get('date_to', None)
    
    # Validate ordering
    if ordering not in ['ascend', 'descend']:
        ordering = 'descend'
    
    # Parse limit
    if limit is not None:
        try:
            limit = int(limit)
            if limit < 0:
                limit = None
        except ValueError:
            limit = None
    else:
        limit = None
    
    # Determine ordering direction
    order_prefix = '' if ordering == 'ascend' else '-'
    
    # Query only paid pill items
    paid_items = PillItem.objects.filter(status='p').select_related(
        'product__category',
        'product__sub_category',
        'product__subject',
        'product__teacher'
    )
    
    # Apply date filters if provided
    if date_from:
        paid_items = paid_items.filter(date_sold__gte=date_from)
    if date_to:
        paid_items = paid_items.filter(date_sold__lte=date_to)
    
    # Query all pill items for total orders
    all_items = PillItem.objects.all()
    
    # Apply date filters to all_items as well
    if date_from:
        all_items = all_items.filter(date_added__gte=date_from)
    if date_to:
        all_items = all_items.filter(date_added__lte=date_to)
    
    # Summary statistics
    summary = {
        'total_paid_books': paid_items.count(),
        'total_orders': all_items.values('pill').distinct().count(),
        'paid_orders': paid_items.values('pill').distinct().count(),
        'waiting_orders': all_items.filter(
            Q(status='w') | Q(status='i')
        ).values('pill').distinct().count(),
        'total_revenue': float(paid_items.aggregate(
            total=Sum('price_at_sale')
        )['total'] or 0.0)
    }
    
    # Categories analytics
    categories_data = paid_items.filter(
        product__category__isnull=False
    ).values(
        'product__category__id',
        'product__category__name'
    ).annotate(
        count=Count('id')
    ).order_by(f'{order_prefix}count')
    
    if limit is not None:
        categories_data = categories_data[:limit]
    
    categories = [
        {
            'id': item['product__category__id'],
            'name': item['product__category__name'],
            'count': item['count']
        }
        for item in categories_data
    ]
    
    # Subcategories analytics
    subcategories_data = paid_items.filter(
        product__sub_category__isnull=False
    ).values(
        'product__sub_category__id',
        'product__sub_category__name'
    ).annotate(
        count=Count('id')
    ).order_by(f'{order_prefix}count')
    
    if limit is not None:
        subcategories_data = subcategories_data[:limit]
    
    subcategories = [
        {
            'id': item['product__sub_category__id'],
            'name': item['product__sub_category__name'],
            'count': item['count']
        }
        for item in subcategories_data
    ]
    
    # Subjects analytics
    subjects_data = paid_items.filter(
        product__subject__isnull=False
    ).values(
        'product__subject__id',
        'product__subject__name'
    ).annotate(
        count=Count('id')
    ).order_by(f'{order_prefix}count')
    
    if limit is not None:
        subjects_data = subjects_data[:limit]
    
    subjects = [
        {
            'id': item['product__subject__id'],
            'name': item['product__subject__name'],
            'count': item['count']
        }
        for item in subjects_data
    ]
    
    # Teachers analytics
    teachers_data = paid_items.filter(
        product__teacher__isnull=False
    ).values(
        'product__teacher__id',
        'product__teacher__name'
    ).annotate(
        count=Count('id')
    ).order_by(f'{order_prefix}count')
    
    if limit is not None:
        teachers_data = teachers_data[:limit]
    
    teachers = [
        {
            'id': item['product__teacher__id'],
            'name': item['product__teacher__name'],
            'count': item['count']
        }
        for item in teachers_data
    ]
    
    # Years analytics - include all years from YEAR_CHOICES
    # Years list is not affected by ordering or limit parameters
    years = []
    for year_code, year_name in YEAR_CHOICES:
        count = paid_items.filter(product__year=year_code).count()
        years.append({
            'year': year_code,
            'count': count
        })
    
    # Prepare response data
    data = {
        'summary': summary,
        'categories': categories,
        'subcategories': subcategories,
        'subjects': subjects,
        'teachers': teachers,
        'years': years
    }
    
    serializer = SalesAnalyticsSerializer(data)
    return Response(serializer.data)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def best_seller_products(request):
    """
    Get best seller products based on paid PillItems
    
    Query Parameters:
    - limit: number to limit results (default: 10)
    - date_from: filter from this date (format: YYYY-MM-DD)
    - date_to: filter to this date (format: YYYY-MM-DD)
    """
    # Get query parameters
    limit = request.query_params.get('limit', 10)
    date_from = request.query_params.get('date_from', None)
    date_to = request.query_params.get('date_to', None)
    
    # Parse limit
    try:
        limit = int(limit)
        if limit < 0:
            limit = 10
    except ValueError:
        limit = 10
    
    # Get best selling products with date filtering
    best_sellers = PillItem.objects.filter(status='p')
    
    # Apply date filters if provided
    if date_from:
        best_sellers = best_sellers.filter(date_sold__gte=date_from)
    if date_to:
        best_sellers = best_sellers.filter(date_sold__lte=date_to)
    
    # Continue with aggregation
    best_sellers = best_sellers.values(
        'product__id',
        'product__name',
        'product__price',
        'product__category__name',
        'product__sub_category__name',
        'product__subject__name',
        'product__teacher__name',
        'product__year'
    ).annotate(
        sales_count=Count('id'),
        total_revenue=Sum('price_at_sale')
    ).order_by('-sales_count')
    
    if limit is not None:
        best_sellers = best_sellers[:limit]
    
    # Format the response
    products = [
        {
            'id': item['product__id'],
            'name': item['product__name'],
            'price': item['product__price'],
            'category': item['product__category__name'],
            'subcategory': item['product__sub_category__name'],
            'subject': item['product__subject__name'],
            'teacher': item['product__teacher__name'],
            'year': item['product__year'],
            'sales_count': item['sales_count'],
            'total_revenue': float(item['total_revenue'] or 0.0)
        }
        for item in best_sellers
    ]
    
    serializer = BestSellerProductSerializer(products, many=True)
    return Response(serializer.data)
