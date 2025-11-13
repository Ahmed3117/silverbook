from rest_framework import serializers
from rest_framework.exceptions import ValidationError
from collections import defaultdict
from urllib.parse import urljoin
from django.utils import timezone
from django.db.models import Sum
from django.db import transaction
from accounts.models import User
from .models import (
    BestProduct, Category, CouponDiscount, Discount, LovedProduct,
    PillItem, ProductDescription,
    SpecialProduct,
    SubCategory, Product, ProductImage, Rating, Pill, Subject, Teacher
)

class SubCategorySerializer(serializers.ModelSerializer):
    category_name = serializers.SerializerMethodField()

    class Meta:
        model = SubCategory
        fields = ['id', 'name', 'category', 'category_name']

    def get_category_name(self, obj):
        return obj.category.name
    
class CategorySerializer(serializers.ModelSerializer):
    subcategories = SubCategorySerializer(many=True, read_only=True)

    class Meta:
        model = Category
        fields = ['id', 'name', 'image', 'subcategories']

class SubjectSerializer(serializers.ModelSerializer):
    class Meta:
        model = Subject
        fields = '__all__'

class TeacherSerializer(serializers.ModelSerializer):
    subject_name = serializers.SerializerMethodField()
    class Meta:
        model = Teacher
        fields = ['id', 'name', 'bio','image','subject','subject_name' , 'facebook', 'instagram', 'twitter', 'youtube', 'linkedin', 'telegram', 'website','tiktok', 'whatsapp']

    def get_subject_name(self, obj):
        return obj.subject.name if obj.subject else None

class ProductDescriptionSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductDescription
        fields = ['id', 'title', 'description', 'order', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']

class ProductDescriptionCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductDescription
        fields = ['product', 'title', 'description', 'order']
    
    def to_internal_value(self, data):
        if isinstance(data, list):
            return [super().to_internal_value(item) for item in data]
        return super().to_internal_value(data)

class BulkProductDescriptionSerializer(serializers.ListSerializer):
    def create(self, validated_data):
        descriptions = [ProductDescription(**item) for item in validated_data]
        return ProductDescription.objects.bulk_create(descriptions)

class ProductImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductImage
        fields = '__all__'

class RatingSerializer(serializers.ModelSerializer):
    class Meta:
        model = Rating
        fields = ['id', 'product', 'user', 'star_number', 'review', 'date_added']
        read_only_fields = ['date_added', 'user']

    def validate(self, data):
        if data.get('star_number') < 1 or data.get('star_number') > 5:
            raise serializers.ValidationError("Star number must be between 1 and 5.")
        return data

    def create(self, validated_data):
        validated_data['user'] = self.context['request'].user
        return super().create(validated_data)

class ProductImageBulkUploadSerializer(serializers.Serializer):
    product = serializers.PrimaryKeyRelatedField(queryset=Product.objects.all())
    images = serializers.ListField(
        child=serializers.ImageField(),
        allow_empty=False
    )

class ProductSerializer(serializers.ModelSerializer):
    images = ProductImageSerializer(many=True, read_only=True)
    discounted_price = serializers.SerializerMethodField()
    has_discount = serializers.SerializerMethodField()
    main_image = serializers.SerializerMethodField()
    number_of_ratings = serializers.SerializerMethodField()
    average_rating = serializers.SerializerMethodField()
    current_discount = serializers.SerializerMethodField()
    discount_expiry = serializers.SerializerMethodField()
    descriptions = ProductDescriptionSerializer(many=True, read_only=True)
    category_id = serializers.SerializerMethodField()
    category_name = serializers.SerializerMethodField()
    subject_id = serializers.SerializerMethodField()
    subject_name = serializers.SerializerMethodField()
    teacher_id = serializers.SerializerMethodField()
    teacher_name = serializers.SerializerMethodField()
    teacher_image = serializers.SerializerMethodField()
    sub_category_id = serializers.SerializerMethodField()
    sub_category_name = serializers.SerializerMethodField()

    class Meta:
        model = Product
        fields = [
            'id', 'product_number','name','year','category','sub_category','subject' ,'teacher', 
            'category_id', 'category_name', 'subject_id' ,'subject_name', 'teacher_id','teacher_name','teacher_image', 
            'sub_category_id', 'sub_category_name', 'price', 'description', 'date_added', 'discounted_price',
            'has_discount', 'current_discount', 'discount_expiry', 'main_image', 'images', 'number_of_ratings',
            'average_rating', 'descriptions', 'pdf_file', 'base_image', 'page_count', 'file_size_mb', 'language', 'is_available'
        ]
        read_only_fields = [
            'product_number', 'date_added'
        ]

    def get_category_id(self, obj):
        return obj.category.id if obj.category else None

    def get_category_name(self, obj):
        return obj.category.name if obj.category else None

    def get_sub_category_id(self, obj):
        return obj.sub_category.id if obj.sub_category else None

    def get_sub_category_name(self, obj):
        return obj.sub_category.name if obj.sub_category else None

    def get_subject_id(self, obj):
        return obj.subject.id if obj.subject else None
    def get_subject_name(self, obj):
        return obj.subject.name if obj.subject else None
    def get_teacher_id(self, obj):
        return obj.teacher.id if obj.teacher else None
    def get_teacher_name(self, obj):
        return obj.teacher.name if obj.teacher else None
    def get_teacher_image(self, obj):
        if obj.teacher and obj.teacher.image:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.teacher.image.url)
            return obj.teacher.image.url
        return None

    def get_discounted_price(self, obj):
        return obj.discounted_price()

    def get_current_discount(self, obj):
        now = timezone.now()
        product_discount = obj.discounts.filter(
            is_active=True,
            discount_start__lte=now,
            discount_end__gte=now
        ).order_by('-discount').first()
        category_discount = None
        if obj.category:
            category_discount = obj.category.discounts.filter(
                is_active=True,
                discount_start__lte=now,
                discount_end__gte=now
            ).order_by('-discount').first()
        if product_discount and category_discount:
            return max(product_discount.discount, category_discount.discount)
        elif product_discount:
            return product_discount.discount
        elif category_discount:
            return category_discount.discount
        return None

    def get_discount_expiry(self, obj):
        now = timezone.now()
        discount = obj.discounts.filter(
            is_active=True,
            discount_start__lte=now,
            discount_end__gte=now
        ).order_by('-discount_end').first()
        if not discount and obj.category:
            discount = obj.category.discounts.filter(
                is_active=True,
                discount_start__lte=now,
                discount_end__gte=now
            ).order_by('-discount_end').first()
        return discount.discount_end if discount else None
    
    def get_has_discount(self, obj):
        return obj.has_discount()

    def get_main_image(self, obj):
        main_image = obj.main_image()
        if main_image and hasattr(main_image, 'url'):
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(main_image.url)
            return main_image.url
        return None

    def get_number_of_ratings(self, obj):
        return obj.number_of_ratings()

    def get_average_rating(self, obj):
        return obj.average_rating()

class ProductBreifedSerializer(serializers.ModelSerializer):
    class Meta:
        model = Product
        fields = ['id', 'name']

class CouponCodeField(serializers.Field):
    def to_internal_value(self, data):
        try:
            return CouponDiscount.objects.get(coupon=data)
        except CouponDiscount.DoesNotExist:
            raise serializers.ValidationError("Coupon does not exist.")

    def to_representation(self, value):
        return value.coupon

class SpecialProductSerializer(serializers.ModelSerializer):
    product = ProductSerializer(read_only=True)
    product_id = serializers.PrimaryKeyRelatedField(
        queryset=Product.objects.all(),
        source='product',
        write_only=True
    )

    class Meta:
        model = SpecialProduct
        fields = [
            'id', 'product', 'product_id', 'special_image',
            'order', 'is_active', 'created_at', 'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at']


class RatingSerializer(serializers.ModelSerializer):
    class Meta:
        model = Rating
        fields = ['id', 'product', 'user', 'star_number', 'review', 'date_added']
        read_only_fields = ['date_added', 'user']

    def validate(self, data):
        if data.get('star_number') < 1 or data.get('star_number') > 5:
            raise serializers.ValidationError("Star number must be between 1 and 5.")
        return data

    def create(self, validated_data):
        validated_data['user'] = self.context['request'].user
        return super().create(validated_data)


class ProductImageBulkUploadSerializer(serializers.Serializer):
    product = serializers.PrimaryKeyRelatedField(queryset=Product.objects.all())
    images = serializers.ListField(
        child=serializers.ImageField(),
        allow_empty=False
    )


class SpecialProductSerializer(serializers.ModelSerializer):
    product = ProductSerializer(read_only=True)
    product_id = serializers.PrimaryKeyRelatedField(
        queryset=Product.objects.all(),
        source='product',
        write_only=True
    )

    class Meta:
        model = SpecialProduct
        fields = [
            'id', 'product', 'product_id', 'special_image',
            'order', 'is_active', 'created_at', 'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at']


class BestProductSerializer(serializers.ModelSerializer):
    product = ProductSerializer(read_only=True)
    product_id = serializers.PrimaryKeyRelatedField(
        queryset=Product.objects.all(),
        source='product',
        write_only=True
    )

    class Meta:
        model = BestProduct
        fields = [
            'id', 'product', 'product_id',
            'order', 'is_active', 'created_at', 'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at']








class PillItemCreateUpdateSerializer(serializers.ModelSerializer):
    product = serializers.PrimaryKeyRelatedField(queryset=Product.objects.all())

    class Meta:
        model = PillItem
        fields = ['id', 'product']

    def validate(self, data):
        return data


class PillItemSerializer(serializers.ModelSerializer):
    product = ProductSerializer(read_only=True)

    class Meta:
        model = PillItem
        fields = ['id', 'product', 'status', 'date_added']


class PillItemCreateSerializer(serializers.ModelSerializer):
    product = serializers.PrimaryKeyRelatedField(queryset=Product.objects.all())
    status = serializers.CharField(read_only=True)

    class Meta:
        model = PillItem
        fields = ['id', 'product', 'status']


class AdminPillItemSerializer(PillItemCreateUpdateSerializer):
    user = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.all(),
        required=False
    )
    user_details = serializers.SerializerMethodField()
    product_details = serializers.SerializerMethodField()
    pill_details = serializers.SerializerMethodField()

    class Meta(PillItemCreateUpdateSerializer.Meta):
        fields = ['id', 'user', 'user_details', 'product', 'product_details', 'status', 'date_added', 'pill', 'pill_details']
        read_only_fields = ['date_added']

    def get_user_details(self, obj):
        user = obj.user
        if not user:
            return None
        return {
            'id': user.id,
            'name': user.name,
            'email': user.email,
            'phone': user.phone
        }

    def get_product_details(self, obj):
        product = obj.product
        request = self.context.get('request')

        image = product.main_image()
        image_url = None
        if image:
            if hasattr(image, 'url'):
                image_url = image.url
                if request is not None:
                    image_url = request.build_absolute_uri(image_url)
            else:
                image_url = str(image)

        return {
            'id': product.id,
            'name': product.name,
            'price': float(product.price),
            'product_number': product.product_number,
            'image': image_url
        }

    def get_pill_details(self, obj):
        pill = obj.pill
        if not pill:
            return None
        return {
            'id': pill.id,
            'pill_number': pill.pill_number,
            'status': pill.status
        }


class AdminLovedProductSerializer(serializers.ModelSerializer):
    user = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.all(),
        required=False
    )
    product = serializers.PrimaryKeyRelatedField(
        queryset=Product.objects.all()
    )
    user_details = serializers.SerializerMethodField()
    product_details = serializers.SerializerMethodField()

    class Meta:
        model = LovedProduct
        fields = [
            'id', 'user', 'user_details', 'product', 'product_details', 
            'created_at'
        ]
        read_only_fields = ['created_at']

    def get_user_details(self, obj):
        return {
            'id': obj.user.id if obj.user else None,
            'name': obj.user.name if obj.user else None,
            'email': obj.user.email if obj.user else None
        }

    def get_product_details(self, obj):
        product = obj.product
        request = self.context.get('request')
        
        main_image = None
        if product.main_image():
            if request:
                main_image = request.build_absolute_uri(product.main_image())
            else:
                main_image = product.main_image()
        
        return {
            'id': product.id,
            'name': product.name,
            'price': product.price,
            'image': main_image
        }

    def validate(self, data):
        # Check for duplicates
        if self.instance is None and LovedProduct.objects.filter(
            user=data.get('user', self.context.get('request').user),
            product=data['product']
        ).exists():
            raise serializers.ValidationError({
                'product': 'This product is already in the user\'s loved items'
            })
        return data

    def create(self, validated_data):
        # Set default user if not provided
        if 'user' not in validated_data and hasattr(self.context.get('request'), 'user'):
            validated_data['user'] = self.context['request'].user
        return super().create(validated_data)


class PillCreateSerializer(serializers.ModelSerializer):
    items = PillItemCreateSerializer(many=True, required=False)
    user_name = serializers.SerializerMethodField()
    user_username = serializers.SerializerMethodField()
    user_phone = serializers.SerializerMethodField()
    user_parent_phone = serializers.SerializerMethodField()
    user = serializers.HiddenField(default=serializers.CurrentUserDefault())

    class Meta:
        model = Pill
        fields = ['id', 'user', 'user_name', 'user_username','user_phone', 'user_parent_phone','items', 'status', 'date_added', 'paid']
        read_only_fields = ['id', 'status', 'date_added', 'paid']
    def get_user_name(self, obj):
        return obj.user.name

    def get_user_username(self, obj):
        return obj.user.username
    def get_user_phone(self, obj):
        return obj.user.phone if obj.user else None
    def get_user_parent_phone(self, obj):
        return obj.user.parent_phone if obj.user else None

    def create(self, validated_data):
        user = validated_data['user']
        items_data = validated_data.pop('items', None)
        
        with transaction.atomic():
            # Create the pill first
            pill = Pill.objects.create(**validated_data)
            
            if items_data:
                # Create new items specifically for this pill
                pill_items = []
                for item_data in items_data:
                    item = PillItem.objects.create(
                        user=user,
                        product=item_data['product'],
                        quantity=item_data['quantity'],
                        size=item_data.get('size'),
                        color=item_data.get('color'),
                        status=pill.status,
                        pill=pill  # Link directly to the pill
                    )
                    pill_items.append(item)
                pill.items.set(pill_items)
            else:
                # Move cart items (status=None) to this pill
                cart_items = PillItem.objects.filter(user=user, status__isnull=True)
                if not cart_items.exists():
                    raise ValidationError("No items provided in request and no items in cart to create a pill.")
                
                # Update cart items to belong to this pill
                for item in cart_items:
                    item.status = pill.status
                    item.pill = pill
                    item.save()
                pill.items.set(cart_items)
            
            return pill

class CouponDiscountSerializer(serializers.ModelSerializer):
    is_active = serializers.SerializerMethodField()
    is_available = serializers.SerializerMethodField()

    class Meta:
        model = CouponDiscount
        fields = ['id', 'coupon', 'discount_value', 'coupon_start', 'coupon_end', 'available_use_times', 'is_wheel_coupon', 'user', 'min_order_value', 'is_active', 'is_available']

    def get_is_active(self, obj):
        now = timezone.now()
        return obj.coupon_start <= now <= obj.coupon_end

    def get_is_available(self, obj):
        return obj.available_use_times > 0 and self.get_is_active(obj)

class PillDetailSerializer(serializers.ModelSerializer):
    items = PillItemSerializer(many=True, read_only=True)
    coupon = CouponDiscountSerializer(read_only=True)
    status_display = serializers.SerializerMethodField()
    user_name = serializers.SerializerMethodField()
    user_username = serializers.SerializerMethodField()
    user_phone = serializers.SerializerMethodField()
    user_parent_phone = serializers.SerializerMethodField()
    final_price = serializers.SerializerMethodField()
    payment_url = serializers.SerializerMethodField()
    payment_status = serializers.SerializerMethodField()

    class Meta:
        model = Pill
        fields = [
            'id','pill_number', 'user_name', 'user_username', 'user_phone','user_parent_phone' ,'items', 'status', 
            'status_display', 'date_added', 'coupon', 'final_price', 'shakeout_invoice_id', 
            'easypay_invoice_uid','easypay_fawry_ref', 'easypay_invoice_sequence', 'payment_gateway', 'payment_url', 'payment_status'
        ]
        read_only_fields = [
            'id','pill_number', 'user_name', 'user_username', 'items', 'status', 'status_display', 'date_added', 'coupon',
            'final_price', 'shakeout_invoice_id', 'easypay_invoice_uid','easypay_fawry_ref', 
            'easypay_invoice_sequence', 'payment_gateway', 'payment_url', 'payment_status'
        ]

    def get_user_name(self, obj):
        return obj.user.name

    def get_user_username(self, obj):
        return obj.user.username
    
    def get_user_phone(self, obj):
        return obj.user.phone if obj.user else None
    
    def get_user_parent_phone(self, obj):
        return obj.user.parent_phone if obj.user else None

    def get_status_display(self, obj):
        return obj.get_status_display()
    
    def get_final_price(self, obj):
        return obj.final_price()
    
    def get_shakeout_invoice_url(self, obj):
        if obj.shakeout_invoice_id and obj.shakeout_invoice_ref:
            return f"https://dash.shake-out.com/invoice/{obj.shakeout_invoice_id}/{obj.shakeout_invoice_ref}"
        return None
    
    def get_easypay_invoice_url(self, obj):
        if obj.easypay_invoice_uid and obj.easypay_invoice_sequence:
            return f"https://stu.easy-adds.com/invoice/{obj.easypay_invoice_uid}/{obj.easypay_invoice_sequence}"
        return None
    
    def get_payment_url(self, obj):
        return obj.payment_url
    
    def get_payment_status(self, obj):
        return obj.payment_status


class PillSerializer(serializers.ModelSerializer):
    coupon = CouponDiscountSerializer(read_only=True)
    status_display = serializers.SerializerMethodField()
    user_name = serializers.SerializerMethodField()
    user_username = serializers.SerializerMethodField()
    user_phone = serializers.SerializerMethodField()
    user_parent_phone = serializers.SerializerMethodField()
    final_price = serializers.SerializerMethodField()
    items_count = serializers.SerializerMethodField()
    shakeout_invoice_url = serializers.SerializerMethodField()
    easypay_invoice_url = serializers.SerializerMethodField()
    payment_url = serializers.SerializerMethodField()
    payment_status = serializers.SerializerMethodField()

    class Meta:
        model = Pill
        fields = [
            'id', 'pill_number', 'user_name', 'user_username', 
            'user_phone', 'user_parent_phone', 'items', 'items_count', 'status', 
            'status_display', 'date_added', 'coupon', 'final_price', 'shakeout_invoice_id', 
            'shakeout_invoice_url', 'easypay_invoice_uid', 'easypay_invoice_sequence', 
            'easypay_invoice_url', 'payment_gateway', 'payment_url', 'payment_status'
        ]
        read_only_fields = [
            'id', 'pill_number', 'user_name', 'user_username', 
            'status', 'status_display', 'date_added', 'coupon', 'final_price', 'items_count',
            'shakeout_invoice_id', 'shakeout_invoice_url', 'easypay_invoice_uid', 
            'easypay_invoice_sequence', 'easypay_invoice_url', 'payment_gateway', 
            'payment_url', 'payment_status'
        ]

    def get_user_name(self, obj):
        return obj.user.name if obj.user else None

    def get_user_username(self, obj):
        return obj.user.username if obj.user else None

    def get_user_phone(self, obj):
        return obj.user.phone if obj.user else None

    def get_user_parent_phone(self, obj):
        return obj.user.parent_phone if obj.user else None

    def get_status_display(self, obj):
        return obj.get_status_display()

    def get_final_price(self, obj):
        return obj.final_price()

    def get_items_count(self, obj):
        return getattr(obj, 'items_count', obj.items.count())
    
    def get_shakeout_invoice_url(self, obj):
        if obj.shakeout_invoice_id and obj.shakeout_invoice_ref:
            return f"https://dash.shake-out.com/invoice/{obj.shakeout_invoice_id}/{obj.shakeout_invoice_ref}"
        return None
    
    def get_easypay_invoice_url(self, obj):
        if obj.easypay_invoice_uid and obj.easypay_invoice_sequence:
            return f"https://stu.easy-adds.com/invoice/{obj.easypay_invoice_uid}/{obj.easypay_invoice_sequence}"
        return None
    
    def get_payment_url(self, obj):
        return obj.payment_url
    
    def get_payment_status(self, obj):
        return obj.payment_status


class DiscountSerializer(serializers.ModelSerializer):
    product_name = serializers.SerializerMethodField()
    category_name = serializers.SerializerMethodField()
    is_active = serializers.SerializerMethodField()

    class Meta:
        model = Discount
        fields = [
            'id', 'product', 'product_name', 'category', 'category_name',
            'discount', 'discount_start', 'discount_end', 'is_active'
        ]
        read_only_fields = ['is_active']

    def get_product_name(self, obj):
        return obj.product.name if obj.product else None

    def get_category_name(self, obj):
        return obj.category.name if obj.category else None

    def get_is_active(self, obj):
        return obj.is_currently_active

    def validate(self, data):
        if not data.get('product') and not data.get('category'):
            raise serializers.ValidationError("Either product or category must be set")
        if data.get('product') and data.get('category'):
            raise serializers.ValidationError("Cannot set both product and category")
        return data

class LovedProductSerializer(serializers.ModelSerializer):
    product = ProductSerializer(read_only=True)
    product_id = serializers.PrimaryKeyRelatedField(
        queryset=Product.objects.all(),
        source='product',
        write_only=True
    )

    class Meta:
        model = LovedProduct
        fields = ['id', 'product', 'product_id', 'created_at']
        read_only_fields = ['id', 'created_at']


class AdminLovedProductSerializer(LovedProductSerializer):
    user = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.all(),
        required=False
    )
    user_details = serializers.SerializerMethodField()

    class Meta(LovedProductSerializer.Meta):
        fields = LovedProductSerializer.Meta.fields + ['user', 'user_details']

    def get_user_details(self, obj):
        if not obj.user:
            return None
        return {
            'id': obj.user.id,
            'name': obj.user.name,
            'email': obj.user.email
        }


class PillCreateSerializer(serializers.ModelSerializer):
    items = PillItemSerializer(many=True, read_only=True)
    coupon = CouponDiscountSerializer(read_only=True)
    user = serializers.PrimaryKeyRelatedField(read_only=True)

    class Meta:
        model = Pill
        fields = ['id', 'pill_number', 'user', 'items', 'status', 'coupon', 'date_added', 'payment_gateway']
        read_only_fields = ['id', 'pill_number', 'user', 'items', 'status', 'coupon', 'date_added']

    def create(self, validated_data):
        request = self.context.get('request')
        user = request.user if request else None
        pill = Pill.objects.create(user=user, **validated_data)
        return pill


class PillCouponApplySerializer(serializers.ModelSerializer):
    coupon = CouponDiscountSerializer(read_only=True)

    class Meta:
        model = Pill
        fields = ['id', 'coupon']

    def validate_coupon(self, value):
        if not value:
            raise serializers.ValidationError("A coupon must be provided")
        if not value.is_active:
            raise serializers.ValidationError("The coupon is not currently active")
        if value.available_use_times <= 0:
            raise serializers.ValidationError("This coupon has been fully used")
        return value


class CouponCodeField(serializers.Field):
    def to_representation(self, value):
        return value.coupon


class UserCartSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    product = ProductSerializer(read_only=True)
    status = serializers.CharField(read_only=True)

    def to_representation(self, instance):
        ret = super().to_representation(instance)
        ret['product'] = ProductSerializer(instance.product, context=self.context).data
        return ret

















