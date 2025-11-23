from django.db.models import Count, Sum, F
from rest_framework import serializers
from rest_framework.fields import ImageField

from .models import User, UserProfileImage
from products.models import Pill, PillItem, Product
from django.db.models import Count, Sum, Case, When, Value, FloatField
from django.db.models.functions import Coalesce

class UserProfileImageSerializer(serializers.ModelSerializer):
    image = ImageField(use_url=True) # Explicitly set use_url to True

    class Meta:
        model = UserProfileImage
        fields = ['id', 'image', 'created_at', 'updated_at']

class UserProfileImageCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserProfileImage
        fields = ['image']
        
class UserSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, required=False)  # Make password optional for updates
    user_profile_image = UserProfileImageSerializer(read_only=True)
    user_profile_image_id = serializers.PrimaryKeyRelatedField(
        queryset=UserProfileImage.objects.all(),
        source='user_profile_image',
        required=False,
        allow_null=True
    )

    class Meta:
        model = User
        fields = (
            'id', 'username', 'email', 'password', 'name','government',
            'is_staff', 'is_superuser', 'user_type', 'phone','phone2','parent_phone',
            'year', 'division', 'user_profile_image',
            'user_profile_image_id','created_at'
        )
        extra_kwargs = {
            'is_staff': {'read_only': True},
            'is_superuser': {'read_only': True},
            'email': {'required': False, 'allow_null': True, 'allow_blank': True},
            'user_type': {'required': False, 'allow_null': True},
            'phone': {'required': False, 'allow_null': True, 'allow_blank': True},
            'phone2': {'required': False, 'allow_null': True, 'allow_blank': True},
            'parent_phone': {'required': False, 'allow_null': True, 'allow_blank': True},
            'year': {'required': False, 'allow_null': True},
            'division': {'required': False, 'allow_null': True},
            'password': {'required': False},  # Make password optional for updates
        }
    
    def update(self, instance, validated_data):
        """
        Handle user updates with proper password hashing
        """
        # Extract password from validated_data
        password = validated_data.pop('password', None)
        
        # Update all other fields
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        
        # Handle password separately to ensure proper hashing
        if password:
            instance.set_password(password)  # This properly hashes the password
        
        instance.save()
        return instance

    def create(self, validated_data):
        """
        Handle user creation with proper password hashing
        """
        profile_image = validated_data.pop('user_profile_image', None)
        email = validated_data.get('email', None)
        user = User.objects.create_user(
            username=validated_data['username'],
            email=email,
            password=validated_data['password'],
            name=validated_data.get('name', ''),
            is_staff=validated_data.get('is_staff', False),
            is_superuser=validated_data.get('is_superuser', False),
            user_type=validated_data.get('user_type', None),
            phone=validated_data.get('phone', None),
            phone2=validated_data.get('phone2', None),
            parent_phone=validated_data.get('parent_phone', None),
            year=validated_data.get('year', None),
            division=validated_data.get('division', None),
            government=validated_data.get('government', None),
            user_profile_image=profile_image
        )
        return user


class PasswordResetRequestSerializer(serializers.Serializer):
    phone = serializers.CharField()  # Changed from email to phone

class PasswordResetConfirmSerializer(serializers.Serializer):
    phone = serializers.CharField() 
    otp = serializers.CharField()
    new_password = serializers.CharField()

class ChangePasswordSerializer(serializers.Serializer):
    old_password = serializers.CharField(required=True, write_only=True)
    new_password = serializers.CharField(required=True, write_only=True, min_length=8)


class UserOrderItemSerializer(serializers.ModelSerializer):
    product_id = serializers.IntegerField(source='product.id', read_only=True)
    product_name = serializers.CharField(source='product.name', read_only=True)
    product_number = serializers.CharField(source='product.product_number', read_only=True)
    teacher_name = serializers.CharField(source='product.teacher.name', read_only=True)
    product_image = serializers.SerializerMethodField()
    status_display = serializers.CharField(source='get_status_display', read_only=True)

    class Meta:
        model = PillItem
        fields = [
            'id', 'status', 'status_display', 'price_at_sale', 'date_added',
            'product_id', 'product_name', 'product_number', 'teacher_name',
            'product_image'
        ]

    def get_product_image(self, obj):
        product = getattr(obj, 'product', None)
        if not product:
            return None

        image = product.base_image or product.main_image()
        if not image or not hasattr(image, 'url'):
            return None

        request = self.context.get('request')
        url = image.url
        if request is not None:
            return request.build_absolute_uri(url)
        return url


class UserOrderSerializer(serializers.ModelSerializer):
    items = serializers.SerializerMethodField()
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    subtotal = serializers.SerializerMethodField()
    final_total = serializers.SerializerMethodField()
    coupon_code = serializers.SerializerMethodField()
    items_count = serializers.SerializerMethodField()

    class Meta:
        model = Pill
        fields = [
            'id', 'pill_number', 'status', 'status_display', 'payment_gateway',
            'coupon_discount', 'coupon_code', 'items_count', 'subtotal',
            'final_total', 'date_added', 'items'
        ]

    def get_items(self, obj):
        items = obj.items.all()
        return UserOrderItemSerializer(items, many=True, context=self.context).data

    def get_subtotal(self, obj):
        return float(obj.items_subtotal())

    def get_final_total(self, obj):
        return float(obj.final_price())

    def get_coupon_code(self, obj):
        coupon = getattr(obj, 'coupon', None)
        if coupon:
            return coupon.coupon
        return None

    def get_items_count(self, obj):
        return obj.items.count()