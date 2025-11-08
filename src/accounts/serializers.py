from django.db.models import Count, Sum, F
from rest_framework import serializers
from rest_framework.fields import ImageField

from .models import User, UserProfileImage
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