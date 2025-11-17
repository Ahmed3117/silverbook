from datetime import timedelta
import random
import logging
from django.shortcuts import get_object_or_404
from django.db.models import Count, Sum, F

logger = logging.getLogger(__name__)
from django.utils import timezone
from django.db.models import Sum, F, Count, Q, Case, When, IntegerField
from rest_framework import generics, status
from rest_framework.exceptions import ValidationError
from rest_framework import filters as rest_filters
from rest_framework.filters import OrderingFilter
from accounts.pagination import CustomPageNumberPagination
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, IsAdminUser, AllowAny
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.views import APIView
from .serializers import *
from .filters import CategoryFilter, CouponDiscountFilter, PillFilter, ProductFilter
from .models import (
    Category, CouponDiscount,
    ProductImage, Rating, SubCategory, Product, Pill
)
from .permissions import IsOwner, IsOwnerOrReadOnly

class CategoryListView(generics.ListAPIView):
    queryset = Category.objects.all()
    serializer_class = CategorySerializer
    filter_backends = [DjangoFilterBackend]
    filterset_class = CategoryFilter
    
class SubCategoryListView(generics.ListAPIView):
    queryset = SubCategory.objects.all()
    serializer_class = SubCategorySerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['category','category__type']

class SubjectListView(generics.ListAPIView):
    queryset = Subject.objects.all()
    serializer_class = SubjectSerializer
    filter_backends = [DjangoFilterBackend, rest_filters.SearchFilter]
    search_fields = ['name', ]
 
class TeacherListView(generics.ListAPIView):
    queryset = Teacher.objects.all()
    serializer_class = TeacherSerializer
    filter_backends = [DjangoFilterBackend, rest_filters.SearchFilter]
    filterset_fields = ['subject']
    search_fields = ['name', 'subject__name']

class TeacherDetailView(generics.RetrieveAPIView):
    queryset = Teacher.objects.all()
    serializer_class = TeacherSerializer
    permission_classes = [AllowAny]
    lookup_field = 'id'

    def get(self, request, *args, **kwargs):
        teacher = self.get_object()
        serializer = self.get_serializer(teacher, context={'request': request})
        return Response(serializer.data)

class ProductListView(generics.ListAPIView):
    queryset = Product.objects.all()
    serializer_class = ProductSerializer
    filter_backends = [DjangoFilterBackend, rest_filters.SearchFilter]
    filterset_class = ProductFilter
    search_fields = ['name', 'category__name', 'subject__name' , 'teacher__name', 'description']


class ProductDetailView(generics.RetrieveAPIView):
    queryset = Product.objects.all()
    serializer_class = ProductSerializer
    lookup_field = 'id'

class Last10ProductsListView(generics.ListAPIView):
    queryset = Product.objects.all()
    serializer_class = ProductSerializer
    filter_backends = [DjangoFilterBackend, rest_filters.SearchFilter]
    filterset_class = ProductFilter

class ActiveSpecialProductsView(generics.ListAPIView):
    serializer_class = SpecialProductSerializer
    permission_classes = [AllowAny]

    def get_queryset(self):
        return SpecialProduct.objects.filter(is_active=True).order_by('-order')
    
class ActiveBestProductsView(generics.ListAPIView):
    serializer_class = BestProductSerializer
    permission_classes = [AllowAny]

    def get_queryset(self):
        return BestProduct.objects.filter(is_active=True).order_by('-order')



class CombinedProductsView(APIView):
    permission_classes = [AllowAny]
    
    def get(self, request, *args, **kwargs):
        # Get limit parameter with default of 10
        limit = int(request.query_params.get('limit', 10))
        
        # Prepare response data
        data = {
            'last_products': self.get_last_products(limit),
            'important_products': self.get_important_products(limit),
            'first_year_products': self.get_year_products('first-secondary', limit),
            'second_year_products': self.get_year_products('second-secondary', limit),
            'third_year_products': self.get_year_products('third-secondary', limit),
        }
        
        return Response(data, status=status.HTTP_200_OK)
    
    def get_last_products(self, limit):
        queryset = Product.objects.all().order_by('-id')[:limit]
        serializer = ProductSerializer(queryset, many=True, context={'request': self.request})
        return serializer.data
    
    def get_important_products(self, limit):
        # Since is_important field was removed, return an empty list
        return []
    
    def get_year_products(self, year, limit):
        queryset = Product.objects.filter(
            year=year
        ).order_by('-date_added')[:limit]
        serializer = ProductSerializer(queryset, many=True, context={'request': self.request})
        return serializer.data

class SpecialBestProductsView(APIView):
    permission_classes = [AllowAny]
    
    def get(self, request, *args, **kwargs):
        # Get limit parameter with default of 10
        limit = int(request.query_params.get('limit', 10))
        
        # Prepare response data
        data = {
            'special_products': self.get_special_products(limit),
            'best_products': self.get_best_products(limit),
        }
        
        return Response(data, status=status.HTTP_200_OK)
    
    def get_special_products(self, limit):
        # Get the special products with their related product data
        special_products = SpecialProduct.objects.filter(
            is_active=True
        ).order_by('-order')[:limit].select_related('product')
        
        # Serialize with additional fields
        result = []
        for sp in special_products:
            product_data = ProductSerializer(sp.product, context={'request': self.request}).data
            result.append({
                'order': sp.order,
                'special_image': self.get_special_image_url(sp),
                **product_data
            })
        return result
    
    def get_special_image_url(self, special_product):
        if special_product.special_image and hasattr(special_product.special_image, 'url'):
            if hasattr(self, 'request'):
                return self.request.build_absolute_uri(special_product.special_image.url)
            return special_product.special_image.url
        return None
    
    def get_best_products(self, limit):
        # Get the best products with their related product data
        best_products = BestProduct.objects.filter(
            is_active=True
        ).order_by('-order')[:limit].select_related('product')
        
        # Serialize with additional fields
        result = []
        for bp in best_products:
            product_data = ProductSerializer(bp.product, context={'request': self.request}).data
            result.append({
                'order': bp.order,
                **product_data
            })
        return result


class TeacherProductsView(APIView):
    permission_classes = [AllowAny]
    
    def get(self, request, teacher_id, *args, **kwargs):
        try:
            teacher = Teacher.objects.get(pk=teacher_id)
        except Teacher.DoesNotExist:
            return Response(
                {"error": "Teacher not found"},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Get parameters with defaults
        limit = int(request.query_params.get('limit', 10))
        is_important = request.query_params.get('important', 'false').lower() == 'true'
        
        # Prepare response data
        data = {
            'teacher': TeacherSerializer(teacher, context={'request': request}).data,
            'books': self.get_books(teacher, limit, is_important),
            'products': self.get_products(teacher, limit, is_important),
        }
        
        return Response(data, status=status.HTTP_200_OK)
    
    def get_books(self, teacher, limit, is_important):
        queryset = Product.objects.filter(
            teacher=teacher,
            type='book'
        )
        
        if is_important:
            queryset = queryset.filter(is_important=True)
            
        queryset = queryset.order_by('-date_added')[:limit]
        serializer = ProductSerializer(queryset, many=True, context={'request': self.request})
        return serializer.data
    
    def get_products(self, teacher, limit, is_important):
        queryset = Product.objects.filter(
            teacher=teacher,
            type='product'
        )
        
        if is_important:
            queryset = queryset.filter(is_important=True)
            
        queryset = queryset.order_by('-date_added')[:limit]
        serializer = ProductSerializer(queryset, many=True, context={'request': self.request})
        return serializer.data


class PillItemPermissionMixin:
    def has_object_permission(self, request, view, obj):
        return obj.user == request.user

class PillCreateView(generics.CreateAPIView):
    queryset = Pill.objects.all()
    serializer_class = PillCreateSerializer
    permission_classes = [IsAuthenticated]

    def perform_create(self, serializer):
        serializer.save(user=self.request.user, status='i')

class PillCouponApplyView(generics.GenericAPIView):
    serializer_class = PillCouponApplySerializer
    lookup_field = 'id'
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Pill.objects.filter(user=self.request.user)

    def post(self, request, *args, **kwargs):
        return self._apply_coupon(request, *args, **kwargs)

    def patch(self, request, *args, **kwargs):
        return self._apply_coupon(request, *args, **kwargs)

    def _apply_coupon(self, request, *args, **kwargs):
        pill = self.get_object()
        serializer = self.get_serializer(pill, data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=status.HTTP_200_OK)




class PillDetailView(generics.RetrieveAPIView, PillItemPermissionMixin):
    queryset = Pill.objects.all()
    serializer_class = PillDetailSerializer
    lookup_field = 'id'
    permission_classes = [IsAuthenticated]

    def get_object(self):
        pill_id = self.kwargs.get('id')
        return get_object_or_404(Pill, id=pill_id, user=self.request.user)

class UserPillsView(generics.ListAPIView):
    serializer_class = PillDetailSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Pill.objects.filter(user=self.request.user).order_by('-date_added')

class CustomerRatingListCreateView(generics.ListCreateAPIView):
    queryset = Rating.objects.all()
    serializer_class = RatingSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Rating.objects.filter(user=self.request.user)

class CustomerRatingDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = Rating.objects.all()
    serializer_class = RatingSerializer
    permission_classes = [IsAuthenticated, IsOwner]


class ProductsWithActiveDiscountAPIView(APIView):
    def get(self, request):
        now = timezone.now()
        product_discounts = Discount.objects.filter(
            is_active=True,
            discount_start__lte=now,
            discount_end__gte=now,
            product__isnull=False
        ).values_list('product_id', flat=True)
        category_discounts = Discount.objects.filter(
            is_active=True,
            discount_start__lte=now,
            discount_end__gte=now,
            category__isnull=False
        ).values_list('category_id', flat=True)
        products = Product.objects.filter(
            Q(id__in=product_discounts) | Q(category_id__in=category_discounts)
        ).distinct()
        serializer = ProductSerializer(products, many=True, context={'request': request})
        return Response(serializer.data, status=status.HTTP_200_OK)

class LovedProductListCreateView(generics.ListCreateAPIView):
    serializer_class = LovedProductSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return LovedProduct.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        serializer.save()

class LovedProductRetrieveDestroyView(generics.RetrieveDestroyAPIView):
    queryset = LovedProduct.objects.all()
    serializer_class = LovedProductSerializer
    permission_classes = [IsAuthenticated, IsOwnerOrReadOnly]

class NewArrivalsView(generics.ListAPIView):
    serializer_class = ProductSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['category', 'sub_category']

    def get_queryset(self):
        queryset = Product.objects.all().order_by('-date_added')
        days = self.request.query_params.get('days', None)
        if days:
            date_threshold = timezone.now() - timedelta(days=int(days))
            queryset = queryset.filter(date_added__gte=date_threshold)
        return queryset

class BestSellersView(generics.ListAPIView):
    serializer_class = ProductSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['category', 'sub_category']

    def get_queryset(self):
        # Get products with paid/delivered items
        queryset = Product.objects.annotate(
            total_sold=Sum(
                Case(
                    When(
                        pill_items__status__in=['p', 'd'],
                        then='pill_items__quantity'
                    ),
                    default=0,
                    output_field=IntegerField()
                )
            )
        ).filter(
            total_sold__gt=0
        ).order_by('-total_sold')
        
        # Apply date filter if provided
        days = self.request.query_params.get('days', None)
        if days:
            date_threshold = timezone.now() - timedelta(days=int(days))
            queryset = queryset.annotate(
                recent_sold=Sum(
                    Case(
                        When(
                            pill_items__status__in=['p', 'd'],
                            pill_items__date_sold__gte=date_threshold,
                            then='pill_items__quantity'
                        ),
                        default=0,
                        output_field=IntegerField()
                    )
                )
            ).filter(
                recent_sold__gt=0
            ).order_by('-recent_sold')
        
        return queryset

class FrequentlyBoughtTogetherView(generics.ListAPIView):
    serializer_class = ProductSerializer

    def get_queryset(self):
        product_id = self.request.query_params.get('product_id')
        if not product_id:
            return Product.objects.none()
        
        # Get pills that contain the requested product
        pill_ids = PillItem.objects.filter(
            product_id=product_id,
            status__in=['p', 'd']
        ).values_list('pill_id', flat=True)
        
        # Find other products in those pills
        frequent_products = Product.objects.filter(
            pill_items__pill_id__in=pill_ids,
            pill_items__status__in=['p', 'd']
        ).exclude(
            id=product_id
        ).annotate(
            co_purchase_count=Count('pill_items__id')
        ).order_by('-co_purchase_count')[:5]
        
        return frequent_products


class ProductRecommendationsView(generics.ListAPIView):
    serializer_class = ProductSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        current_product_id = self.request.query_params.get('product_id')
        recommendations = []
        
        if current_product_id:
            current_product = get_object_or_404(Product, id=current_product_id)
            similar_products = Product.objects.filter(
                Q(category=current_product.category) |
                Q(sub_category=current_product.sub_category) |
                Q(subject=current_product.subject) |
                Q(teacher=current_product.teacher)
            ).exclude(id=current_product_id).distinct()
            recommendations.extend(list(similar_products))
        
        # Loved products
        loved_products = Product.objects.filter(
            lovedproduct__user=user
        ).exclude(id__in=[p.id for p in recommendations]).distinct()
        recommendations.extend(list(loved_products))
        
        # Purchased products (using PillItem now)
        purchased_products = Product.objects.filter(
            pill_items__user=user,
            pill_items__status__in=['p', 'd']
        ).exclude(id__in=[p.id for p in recommendations]).distinct()
        recommendations.extend(list(purchased_products))
        
        # Deduplicate
        seen = set()
        unique_recommendations = []
        for product in recommendations:
            if product.id not in seen:
                seen.add(product.id)
                unique_recommendations.append(product)
            if len(unique_recommendations) >= 12:
                break
                
        return unique_recommendations


from rest_framework import filters

class CustomPillFilterBackend(filters.BaseFilterBackend):
    def filter_queryset(self, request, queryset, view):
        pill_id = request.query_params.get('pill')
        if pill_id is not None:
            # First validate that the pill exists
            if Pill.objects.filter(id=pill_id).exists():
                return queryset.filter(pill__id=pill_id)
            else:
                # Return empty queryset if pill doesn't exist
                return queryset.none()
        return queryset


class PillItemListCreateView(generics.ListCreateAPIView):
    queryset = PillItem.objects.select_related(
        'user', 'product', 'color', 'pill'
    ).prefetch_related('product__images')
    serializer_class = AdminPillItemSerializer
    filter_backends = [CustomPillFilterBackend, OrderingFilter]
    ordering_fields = ['date_added', 'quantity']
    ordering = ['-date_added']
    

class PillItemRetrieveUpdateDestroyView(generics.RetrieveUpdateDestroyAPIView):
    queryset = PillItem.objects.select_related(
        'user', 'product', 'color', 'pill'
    )
    serializer_class = AdminPillItemSerializer
    lookup_field = 'pk'

    def perform_destroy(self, instance):
        if instance.pill and instance.pill.status in ['p', 'd']:
            raise serializers.ValidationError("Cannot delete items from paid/delivered pills")
        instance.delete()


class RemovePillItemView(APIView):
    """
    API endpoint to remove an item from a pill
    """
    permission_classes = [IsAuthenticated]
    
    def delete(self, request, pill_id, item_id):
        """
        Remove a specific item from a pill
        """
        try:
            # Get the pill and ensure it belongs to the authenticated user
            pill = get_object_or_404(Pill, id=pill_id, user=request.user)
            
            # Get the pill item to remove
            try:
                pill_item = pill.items.get(id=item_id)
            except pill.items.model.DoesNotExist:
                return Response({
                    'success': False,
                    'error': 'العنصر غير موجود في هذه الفاتورة',
                    'error_code': 'ITEM_NOT_FOUND'
                }, status=status.HTTP_404_NOT_FOUND)
            
            # Store item info for response
            removed_item_info = {
                'id': pill_item.id,
                'product_name': pill_item.product.name,
                'quantity': pill_item.quantity,
                'price': float(pill_item.price)
            }
            
            # Remove the item
            pill_item.delete()
            
            # Check if pill has any items left
            remaining_items_count = pill.items.count()
            
            if remaining_items_count == 0:
                # If no items left, delete the pill
                pill.delete()
                return Response({
                    'success': True,
                    'message': 'تم حذف العنصر والفاتورة بالكامل لعدم وجود عناصر أخرى',
                    'pill_deleted': True,
                    'removed_item': removed_item_info
                }, status=status.HTTP_200_OK)
            
            # Recalculate pill totals
            pill.save()  # This will trigger recalculation in the save method
            
            return Response({
                'success': True,
                'message': 'تم حذف العنصر بنجاح',
                'pill_deleted': False,
                'removed_item': removed_item_info,
                'remaining_items_count': remaining_items_count,
                'updated_pill': {
                    'id': pill.id,
                    'pill_number': pill.pill_number,
                    'total_amount': float(pill.final_price()),
                    'items_count': remaining_items_count
                }
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.error(f"Exception removing item {item_id} from pill {pill_id}: {str(e)}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            return Response({
                'success': False,
                'error': f'خطأ في الخادم: {str(e)}',
                'error_code': 'SERVER_ERROR'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class AdminLovedProductListCreateView(generics.ListCreateAPIView):
    queryset = LovedProduct.objects.select_related(
        'user', 'product'
    ).prefetch_related('product__images')
    serializer_class = AdminLovedProductSerializer
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields = {
        'user': ['exact'],
        'product': ['exact'],
        'created_at': ['gte', 'lte', 'exact']
    }
    ordering_fields = ['created_at']
    ordering = ['-created_at']

class AdminLovedProductRetrieveDestroyView(generics.RetrieveDestroyAPIView):
    queryset = LovedProduct.objects.select_related('user', 'product')
    serializer_class = AdminLovedProductSerializer
    lookup_field = 'pk'




















# Admin Endpoints

class CategoryListCreateView(generics.ListCreateAPIView):
    queryset = Category.objects.all()
    serializer_class = CategorySerializer
    filter_backends = [DjangoFilterBackend]
    filterset_class = CategoryFilter
    # permission_classes = [IsAdminOrHasEndpointPermission]

class CategoryRetrieveUpdateDestroyView(generics.RetrieveUpdateDestroyAPIView):
    queryset = Category.objects.all()
    serializer_class = CategorySerializer
    # permission_classes = [IsAdminOrHasEndpointPermission]

class SubCategoryListCreateView(generics.ListCreateAPIView):
    queryset = SubCategory.objects.all()
    serializer_class = SubCategorySerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['category','category__type']
    
    def get_permissions(self):
        from permissions.permissions import IsAdminOrHasEndpointPermission
        return [IsAdminOrHasEndpointPermission()]

class SubCategoryRetrieveUpdateDestroyView(generics.RetrieveUpdateDestroyAPIView):
    queryset = SubCategory.objects.all()
    serializer_class = SubCategorySerializer
    # permission_classes = [IsAdminOrHasEndpointPermission]

class SubjectListCreateView(generics.ListCreateAPIView):
    queryset = Subject.objects.all()
    serializer_class = SubjectSerializer
    filter_backends = [DjangoFilterBackend, rest_filters.SearchFilter]
    search_fields = ['name']
    # permission_classes = [IsAdminOrHasEndpointPermission]

class SubjectRetrieveUpdateDestroyView(generics.RetrieveUpdateDestroyAPIView):
    queryset = Subject.objects.all()
    serializer_class = SubjectSerializer
    # permission_classes = [IsAdminOrHasEndpointPermission]
    

class TeacherListCreateView(generics.ListCreateAPIView):
    queryset = Teacher.objects.all()
    serializer_class = TeacherSerializer
    filter_backends = [DjangoFilterBackend, rest_filters.SearchFilter]
    filterset_fields = ['subject']
    search_fields = ['name', 'subject__name']
    # permission_classes = [IsAdminOrHasEndpointPermission]

class TeacherRetrieveUpdateDestroyView(generics.RetrieveUpdateDestroyAPIView):
    queryset = Teacher.objects.all()
    serializer_class = TeacherSerializer
    # permission_classes = [IsAdminOrHasEndpointPermission]
    

class ProductListCreateView(generics.ListCreateAPIView):
    queryset = Product.objects.all()
    serializer_class = ProductSerializer
    filter_backends = [DjangoFilterBackend, rest_filters.SearchFilter]
    filterset_class = ProductFilter
    search_fields = ['name', 'category__name', 'description']
    pagination_class = CustomPageNumberPagination
    # permission_classes = [IsAdminOrHasEndpointPermission]

class ProductListBreifedView(generics.ListCreateAPIView):
    queryset = Product.objects.all()
    serializer_class = ProductBreifedSerializer
    filter_backends = [DjangoFilterBackend, rest_filters.SearchFilter]
    filterset_class = ProductFilter
    search_fields = ['name', 'category__name', 'description']
    # permission_classes = [IsAdminOrHasEndpointPermission]

class ProductRetrieveUpdateDestroyView(generics.RetrieveUpdateDestroyAPIView):
    queryset = Product.objects.all()
    serializer_class = ProductSerializer
    # permission_classes = [IsAdminOrHasEndpointPermission]

class ProductImageListCreateView(generics.ListCreateAPIView):
    queryset = ProductImage.objects.all()
    serializer_class = ProductImageSerializer
    filterset_fields = ['product']
    # permission_classes = [IsAdminOrHasEndpointPermission]

class ProductImageBulkCreateView(generics.CreateAPIView):
    # permission_classes = [IsAdminOrHasEndpointPermission]

    def post(self, request, *args, **kwargs):
        serializer = ProductImageBulkUploadSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        product = serializer.validated_data['product']
        images = serializer.validated_data['images']
        product_images = [
            ProductImage(product=product, image=image)
            for image in images
        ]
        ProductImage.objects.bulk_create(product_images)
        return Response(
            {"message": "Images uploaded successfully."},
            status=status.HTTP_201_CREATED
        )

class ProductImageDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = ProductImage.objects.all()
    serializer_class = ProductImageSerializer
    # permission_classes = [IsAdminOrHasEndpointPermission]

class ProductDescriptionListCreateView(generics.ListCreateAPIView):
    queryset = ProductDescription.objects.all()
    serializer_class = ProductDescriptionSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['product']
    # permission_classes = [IsAdminOrHasEndpointPermission]

    def get_serializer_class(self):
        if self.request.method == 'POST' and isinstance(self.request.data, list):
            return ProductDescriptionCreateSerializer
        return ProductDescriptionSerializer

class ProductDescriptionBulkCreateView(generics.CreateAPIView):
    queryset = ProductDescription.objects.all()
    # permission_classes = [IsAdminOrHasEndpointPermission]

    def get_serializer_class(self):
        if isinstance(self.request.data, list):
            class BulkSerializer(ProductDescriptionCreateSerializer):
                class Meta(ProductDescriptionCreateSerializer.Meta):
                    list_serializer_class = BulkProductDescriptionSerializer
            return BulkSerializer
        return ProductDescriptionCreateSerializer

    def create(self, request, *args, **kwargs):
        if isinstance(request.data, list):
            serializer = self.get_serializer(data=request.data, many=True)
        else:
            serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        headers = self.get_success_headers(serializer.data)
        return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)

class ProductDescriptionRetrieveUpdateDestroyView(generics.RetrieveUpdateDestroyAPIView):
    queryset = ProductDescription.objects.all()
    serializer_class = ProductDescriptionSerializer
    # permission_classes = [IsAdminOrHasEndpointPermission]

class SpecialProductListCreateView(generics.ListCreateAPIView):
    queryset = SpecialProduct.objects.all()
    serializer_class = SpecialProductSerializer
    filter_backends = [DjangoFilterBackend, rest_filters.SearchFilter]
    filterset_fields = ['is_active', 'product']
    search_fields = ['product__name', 'product__category__name']
    ordering_fields = ['order', 'created_at']
    # permission_classes = [IsAdminOrHasEndpointPermission]

    def perform_create(self, serializer):
        serializer.save()

class SpecialProductRetrieveUpdateDestroyView(generics.RetrieveUpdateDestroyAPIView):
    queryset = SpecialProduct.objects.all()
    serializer_class = SpecialProductSerializer
    # permission_classes = [IsAdminOrHasEndpointPermission]

class BestProductListCreateView(generics.ListCreateAPIView):
    queryset = BestProduct.objects.all()
    serializer_class = BestProductSerializer
    filter_backends = [DjangoFilterBackend, rest_filters.SearchFilter]
    filterset_fields = ['is_active', 'product']
    search_fields = ['product__name', 'product__category__name']
    ordering_fields = ['order', 'created_at']
    # permission_classes = [IsAdminOrHasEndpointPermission]

    def perform_create(self, serializer):
        serializer.save()

class BestProductRetrieveUpdateDestroyView(generics.RetrieveUpdateDestroyAPIView):
    queryset = BestProduct.objects.all()
    serializer_class = BestProductSerializer
    # permission_classes = [IsAdminOrHasEndpointPermission]

from django.db.models import Prefetch

class PillListCreateView(generics.ListCreateAPIView):
    serializer_class = PillCreateSerializer
    filter_backends = [DjangoFilterBackend, rest_filters.SearchFilter]
    filterset_class = PillFilter
    search_fields = ['user__name', 'user__username', 'pill_number','user__phone','user__parent_phone','shakeout_invoice_id', 'shakeout_invoice_ref', 'easypay_invoice_uid', 'easypay_invoice_sequence' , 'easypay_fawry_ref']
    pagination_class = CustomPageNumberPagination
    # permission_classes = [IsAdminOrHasEndpointPermission]

    def get_queryset(self):
        # Optimize queryset with select_related, prefetch_related, and annotations
        queryset = Pill.objects.select_related(
            'user',
            'coupon'
        ).prefetch_related(
            Prefetch(
                'items',
                queryset=PillItem.objects.select_related(
                    'product',
                    'color'
                )
            )
        ).annotate(
            items_count=Count('items')
        ).order_by('-date_added')
        
        # REMOVED: No automatic date filtering
        # This will return all pills
        
        return queryset

    def get_serializer_class(self):
        if self.request.method == 'POST':
            return PillCreateSerializer
        return PillSerializer

class PillRetrieveUpdateDestroyView(generics.RetrieveUpdateDestroyAPIView):
    queryset = Pill.objects.all()
    serializer_class = PillDetailSerializer
    # permission_classes = [IsAdminOrHasEndpointPermission]

class DiscountListCreateView(generics.ListCreateAPIView):
    queryset = Discount.objects.all()
    serializer_class = DiscountSerializer
    # permission_classes = [IsAdminOrHasEndpointPermission]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['product', 'category', 'is_active']

class DiscountRetrieveUpdateDestroyView(generics.RetrieveUpdateDestroyAPIView):
    queryset = Discount.objects.all()
    serializer_class = DiscountSerializer
    # permission_classes = [IsAdminOrHasEndpointPermission]

class CouponListCreateView(generics.ListCreateAPIView):
    queryset = CouponDiscount.objects.all()
    serializer_class = CouponDiscountSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_class = CouponDiscountFilter
    # permission_classes = [IsAdminOrHasEndpointPermission]

class CouponRetrieveUpdateDestroyView(generics.RetrieveUpdateDestroyAPIView):
    queryset = CouponDiscount.objects.all()
    serializer_class = CouponDiscountSerializer
    # permission_classes = [IsAdminOrHasEndpointPermission]

class RatingListCreateView(generics.ListCreateAPIView):
    queryset = Rating.objects.all()
    serializer_class = RatingSerializer
    filterset_fields = ['product']
    # permission_classes = [IsAdminOrHasEndpointPermission]

class RatingDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = Rating.objects.all()
    serializer_class = RatingSerializer
    # permission_classes = [IsAdminOrHasEndpointPermission]



from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from services.shakeout_service import shakeout_service
import logging

logger = logging.getLogger(__name__)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def create_shakeout_invoice_view(request, pill_id):
    """
    Create a Shake-out invoice for a specific pill
    """
    try:
        # Get the pill
        pill = Pill.objects.get(id=pill_id, user=request.user)
        
        # Check if pill already has a Shake-out invoice
        if pill.shakeout_invoice_id:
            # Check if the existing invoice is expired or invalid
            if pill.is_shakeout_invoice_expired():
                logger.info(f"Existing Shake-out invoice {pill.shakeout_invoice_id} for pill {pill_id} is expired/invalid - creating new one")
                
                # Clear old invoice data to create a new one
                pill.shakeout_invoice_id = None
                pill.shakeout_invoice_ref = None
                pill.shakeout_data = None
                pill.shakeout_created_at = None
                pill.save(update_fields=['shakeout_invoice_id', 'shakeout_invoice_ref', 'shakeout_data', 'shakeout_created_at'])
            else:
                return Response({
                    'success': False,
                    'error': 'Pill already has a Shake-out invoice',
                    'data': {
                        'invoice_id': pill.shakeout_invoice_id,
                        'invoice_ref': pill.shakeout_invoice_ref,
                        'payment_url': pill.shakeout_payment_url,
                        'created_at': pill.shakeout_created_at.isoformat() if pill.shakeout_created_at else None,
                        'status': 'active'
                    }
                }, status=status.HTTP_400_BAD_REQUEST)
        
        # Create Shake-out invoice
        payment_url = pill.create_shakeout_invoice()
        
        if payment_url:
            # Refresh pill from database to get updated data
            pill.refresh_from_db()
            
            return Response({
                'success': True,
                'message': 'Shake-out invoice created successfully',
                'data': {
                    'invoice_id': pill.shakeout_invoice_id,
                    'invoice_ref': pill.shakeout_invoice_ref,
                    'payment_url': payment_url,
                    'total_amount': pill.final_price(),
                    'pill_number': pill.pill_number
                }
            }, status=status.HTTP_201_CREATED)
        else:
            return Response({
                'success': False,
                'error': 'Failed to create Shake-out invoice'
            }, status=status.HTTP_400_BAD_REQUEST)
            
    except Pill.DoesNotExist:
        return Response({
            'success': False,
            'error': 'Pill not found or access denied'
        }, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        logger.error(f"Error creating Shake-out invoice for pill {pill_id}: {str(e)}")
        return Response({
            'success': False,
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)











