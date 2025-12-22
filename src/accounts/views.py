from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import AllowAny,IsAuthenticated,IsAdminUser
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.views import APIView
from django.contrib.auth import authenticate
from services.beon_service import send_beon_sms
from rest_framework_simplejwt.tokens import RefreshToken
from django.core.mail import send_mail
from django.utils import timezone
from datetime import timedelta
import random
import secrets


def get_client_ip(request):
    """Extract client IP address from request headers."""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0].strip()
    else:
        ip = request.META.get('REMOTE_ADDR', 'Unknown')
    return ip


def get_device_info_from_request(request):
    """
    Extract device information from request headers.
    Returns a dict with IP, User-Agent, and parsed device name.
    """
    ip_address = get_client_ip(request)
    user_agent = request.META.get('HTTP_USER_AGENT', 'Unknown')
    
    # Parse User-Agent to get a friendly device name
    device_name = 'Unknown Device'
    if user_agent and user_agent != 'Unknown':
        ua_lower = user_agent.lower()
        if 'iphone' in ua_lower:
            device_name = 'iPhone'
        elif 'ipad' in ua_lower:
            device_name = 'iPad'
        elif 'android' in ua_lower:
            device_name = 'Android Device'
        elif 'windows' in ua_lower:
            device_name = 'Windows PC'
        elif 'macintosh' in ua_lower or 'mac os' in ua_lower:
            device_name = 'Mac'
        elif 'linux' in ua_lower:
            device_name = 'Linux PC'
        else:
            # Use first part of user agent as fallback
            device_name = user_agent[:50] if len(user_agent) > 50 else user_agent
    
    return {
        'ip_address': ip_address,
        'user_agent': user_agent,
        'device_name': device_name
    }
from accounts.pagination import CustomPageNumberPagination
from products.models import Pill, PillItem
from django.db.models import Prefetch
from .serializers import (
    ChangePasswordSerializer,
    UserProfileImageCreateSerializer,
    UserProfileImageSerializer,
    UserSerializer,
    PasswordResetRequestSerializer,
    PasswordResetConfirmSerializer,
    UserOrderSerializer,
    UserDeviceSerializer,
    StudentDeviceListSerializer,
    UpdateMaxDevicesSerializer,
)
from .models import User, UserProfileImage, UserDevice
from django.contrib.auth import update_session_auth_hash
from rest_framework import generics
from rest_framework.filters import SearchFilter, OrderingFilter
from django.db.models import Count


@api_view(['POST'])
@permission_classes([AllowAny])
def signup(request):
    serializer = UserSerializer(data=request.data)
    if serializer.is_valid():
        user = serializer.save()
        
        # Generate device token and register device for students
        device_token = None
        if user.user_type == 'student':
            # Get device info from request body (sent by mobile app)
            device_id = request.data.get('device_id')  # Unique ID from mobile app
            device_name_from_request = request.data.get('device_name')  # e.g., "iPhone 15 Pro", "Samsung Galaxy S24"
            
            # Auto-detect device info from request headers (fallback)
            device_info_data = get_device_info_from_request(request)
            device_token = secrets.token_hex(32)  # 64 character hex string
            
            # Use device_name from request if provided, otherwise use auto-detected
            final_device_name = device_name_from_request or device_info_data['device_name']
            
            # Create device record
            UserDevice.objects.create(
                user=user,
                device_token=device_token,
                device_id=device_id,  # From mobile app (may be None)
                device_name=final_device_name,
                ip_address=device_info_data['ip_address'],
                user_agent=device_info_data['user_agent'],
                is_active=True
            )
        
        # Generate JWT tokens
        refresh = RefreshToken.for_user(user)
        
        # Add device_token to JWT payload for students
        if device_token:
            refresh['device_token'] = device_token
        
        user_data = serializer.data
        user_data['is_admin'] = user.is_staff or user.is_superuser
        
        return Response({
            'refresh': str(refresh),
            'access': str(refresh.access_token),
            'user': user_data
        }, status=status.HTTP_201_CREATED)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

@api_view(['POST'])
@permission_classes([AllowAny])
def signin(request):
    username = request.data.get('username')
    password = request.data.get('password')

    user = authenticate(username=username, password=password)
    if not user:
        return Response({'error': 'Invalid credentials'}, status=status.HTTP_401_UNAUTHORIZED)

    try:
        device_token = None
        
        # Handle device registration for students
        if user.user_type == 'student':
            # Get device info from request body (sent by mobile app)
            device_id = request.data.get('device_id')  # Unique ID from mobile app
            device_name_from_request = request.data.get('device_name')  # e.g., "iPhone 15 Pro", "Samsung Galaxy S24"
            
            # Auto-detect device info from request headers (fallback)
            device_info_data = get_device_info_from_request(request)
            ip_address = device_info_data['ip_address']
            
            # Use device_name from request if provided, otherwise use auto-detected
            final_device_name = device_name_from_request or device_info_data['device_name']
            
            # Try to find existing device
            # Logic:
            # - If device_id provided → match ONLY by device_id (most reliable, don't fall back)
            # - If device_id NOT provided → match by IP address (fallback for web/old clients)
            existing_device = None
            
            if device_id:
                # If device_id provided, match ONLY by device_id
                # Don't fall back to IP - this ensures each device_id is tracked separately
                existing_device = UserDevice.objects.filter(
                    user=user,
                    is_active=True,
                    device_id=device_id
                ).first()
            else:
                # No device_id provided - use IP address as identifier
                # This is the fallback for web clients or old mobile app versions
                existing_device = UserDevice.objects.filter(
                    user=user,
                    is_active=True,
                    ip_address=ip_address,
                    device_id__isnull=True  # Only match devices without device_id
                ).first()
            
            if existing_device:
                # Same device logging in again - update info and return existing token
                existing_device.last_used_at = timezone.now()
                existing_device.user_agent = device_info_data['user_agent']
                existing_device.device_name = final_device_name  # Use provided name or auto-detected
                existing_device.ip_address = ip_address  # Update IP (may have changed)
                if device_id and not existing_device.device_id:
                    # If device_id now provided but wasn't before, save it
                    existing_device.device_id = device_id
                existing_device.save(update_fields=['last_used_at', 'user_agent', 'device_name', 'ip_address', 'device_id'])
                device_token = existing_device.device_token
            else:
                # New device - check if limit is reached
                active_devices_count = UserDevice.objects.filter(user=user, is_active=True).count()
                
                if active_devices_count >= user.max_allowed_devices:
                    # Limit reached - block login from new device
                    return Response({
                        'error': 'لقد تجاوزت العدد المسموح به من الأجهزة لتسجيل الدخول إلى حسابك',
                        'error_en': 'You have exceeded the allowed number of devices to login to your account',
                        'code': 'device_limit_exceeded',
                        'max_allowed_devices': user.max_allowed_devices,
                        'current_devices_count': active_devices_count
                    }, status=status.HTTP_403_FORBIDDEN)
                
                # Under limit - register new device
                device_token = secrets.token_hex(32)  # 64 character hex string
                
                # Create new device record
                UserDevice.objects.create(
                    user=user,
                    device_token=device_token,
                    device_id=device_id,  # From mobile app (may be None)
                    device_name=final_device_name,  # Use provided name or auto-detected
                    ip_address=ip_address,
                    user_agent=device_info_data['user_agent'],
                    is_active=True
                )
        
        # Generate JWT tokens
        refresh = RefreshToken.for_user(user)
        
        # Add device_token to JWT payload for students
        if device_token:
            refresh['device_token'] = device_token
        
        # Pass the request object into the serializer's context
        serializer = UserSerializer(user, context={'request': request})
        user_data = serializer.data
        user_data['is_admin'] = user.is_staff or user.is_superuser

        return Response({
            'refresh': str(refresh),
            'access': str(refresh.access_token),
            'user': user_data
        })
    except Exception as e:
        return Response({'error': f'Token generation failed: {str(e)}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['POST'])
@permission_classes([AllowAny])
def request_password_reset(request):
    serializer = PasswordResetRequestSerializer(data=request.data)
    if serializer.is_valid():
        username = serializer.validated_data['username']
        try:
            user = User.objects.filter(username=username).first()
            if not user:
                return Response({'error': 'User not found'}, status=status.HTTP_404_NOT_FOUND)
            
            otp = ''.join([str(random.randint(0, 9)) for _ in range(6)])
            user.otp = otp
            user.otp_created_at = timezone.now()
            user.save()
            
            message = f'Your PIN code is {otp}'
            # Send OTP to username (which is a phone number)
            sms_response = send_beon_sms(phone_numbers=username, message=message)

            if sms_response.get('success'):
                return Response({'message': 'OTP sent to your phone via SMS'})
            else:
                error_detail = sms_response.get('error') or sms_response.get('detail')
                return Response(
                    {'error': 'Failed to send OTP via SMS', 'detail': error_detail},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )
        except Exception as e:
            return Response({'error': f'An error occurred: {str(e)}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

@api_view(['POST'])
@permission_classes([AllowAny])
def reset_password_confirm(request):
    serializer = PasswordResetConfirmSerializer(data=request.data)
    if serializer.is_valid():
        username = serializer.validated_data['username']
        otp = serializer.validated_data['otp']
        new_password = serializer.validated_data['new_password']
        
        try:
            user = User.objects.filter(username=username, otp=otp).first()
            if not user:
                return Response({'error': 'Invalid OTP or username'}, status=status.HTTP_400_BAD_REQUEST)
            
            if user.otp_created_at < timezone.now() - timedelta(minutes=10):
                return Response({'error': 'OTP expired'}, status=status.HTTP_400_BAD_REQUEST)
            
            user.set_password(new_password)
            user.otp = None
            user.otp_created_at = None
            user.save()
            
            return Response({'message': 'Password reset successful'})
        except Exception as e:
            return Response({'error': f'An error occurred: {str(e)}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)



class UpdateUserData(generics.UpdateAPIView):
    queryset = User.objects.all()
    serializer_class = UserSerializer
    permission_classes = [IsAuthenticated]

    def get_object(self):
        return self.request.user

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        
        # Prevent students from changing their username
        if instance.user_type == 'student' and 'username' in request.data:
            if request.data['username'] != instance.username:
                return Response(
                    {'username': ['Students cannot change their username']},
                    status=status.HTTP_400_BAD_REQUEST
                )
        
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        return Response(serializer.data)

class GetUserData(generics.RetrieveAPIView):
    serializer_class = UserSerializer
    permission_classes = [IsAuthenticated]

    def get_object(self):
        return self.request.user


class UserOrdersView(generics.ListAPIView):
    serializer_class = UserOrderSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = CustomPageNumberPagination

    def get_queryset(self):
        return (
            Pill.objects.filter(user=self.request.user)
            .select_related('coupon')
            .prefetch_related(
                Prefetch(
                    'items',
                    queryset=PillItem.objects.select_related('product', 'product__teacher')
                )
            )
            .order_by('-date_added')
        )


class DeleteAccountView(APIView):
    """Allow an authenticated student to permanently delete their account."""
    permission_classes = [IsAuthenticated]

    def delete(self, request):
        user = request.user

        if user.is_staff or user.is_superuser:
            return Response(
                {'detail': 'Admin accounts cannot be deleted via this endpoint.'},
                status=status.HTTP_403_FORBIDDEN
            )

        username = user.username
        user.delete()
        return Response(
            {
                'message': 'Account deleted successfully.',
                'username': username
            },
            status=status.HTTP_200_OK
        )
    
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def change_password(request):
    serializer = ChangePasswordSerializer(data=request.data)
    
    if serializer.is_valid():
        user = request.user
        old_password = serializer.validated_data['old_password']
        new_password = serializer.validated_data['new_password']
        
        # Verify old password
        if not user.check_password(old_password):
            return Response(
                {'error': 'Old password is incorrect'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Set new password
        user.set_password(new_password)
        user.save()
        
        # Update session to prevent logout
        update_session_auth_hash(request, user)
        
        return Response(
            {'message': 'Password updated successfully'}, 
            status=status.HTTP_200_OK
        )
    
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

#^ ---------------------------------------------------- Dashboard ---------------------------- ^#

@api_view(['POST'])
@permission_classes([IsAdminUser])
def create_admin_user(request):
    serializer = UserSerializer(data=request.data)
    if serializer.is_valid():
        user = serializer.save(is_staff=True, is_superuser=True)
        refresh = RefreshToken.for_user(user)
        return Response({
            'refresh': str(refresh),
            'access': str(refresh.access_token),
            'user': serializer.data
        }, status=status.HTTP_201_CREATED)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class UserCreateAPIView(APIView):
    permission_classes = [IsAdminUser]

    def post(self, request):
        serializer = UserSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class UserUpdateAPIView(APIView):
    permission_classes = [IsAdminUser]

    def patch(self, request, username):  # Changed from pk to username
        try:
            user = User.objects.get(username=username)  # Changed to use username
        except User.DoesNotExist:
            return Response({'error': 'User not found'}, status=status.HTTP_404_NOT_FOUND)
        
        serializer = UserSerializer(user, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class UserDeleteAPIView(APIView):
    permission_classes = [IsAdminUser]

    def delete(self, request, pk):
        try:
            user = User.objects.get(pk=pk)
        except User.DoesNotExist:
            return Response({'error': 'User not found'}, status=status.HTTP_404_NOT_FOUND)
        
        user.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

class UserProfileImageListCreateView(generics.ListCreateAPIView):
    queryset = UserProfileImage.objects.all()

    def get_permissions(self):
        if self.request.method == 'POST':
            return [IsAdminUser()]
        return [AllowAny()]

    def get_serializer_class(self):
        if self.request.method == 'POST':
            return UserProfileImageCreateSerializer
        return UserProfileImageSerializer

class UserProfileImageRetrieveUpdateDestroyView(generics.RetrieveUpdateDestroyAPIView):
    queryset = UserProfileImage.objects.all()
    serializer_class = UserProfileImageSerializer
    permission_classes = [IsAdminUser]


# user analysis

class AdminUserListView(generics.ListAPIView):
    serializer_class = UserSerializer
    permission_classes = [IsAdminUser]
    queryset = User.objects.all().order_by('-created_at')
    
    filter_backends = [SearchFilter, OrderingFilter,DjangoFilterBackend]
    ordering_fields = ['created_at']
    search_fields = ['username', 'name', 'email', 'government']
    filterset_fields = ['is_staff', 'is_superuser','year', 'division', 'government']


class AdminUserDetailView(generics.RetrieveAPIView):
    serializer_class = UserSerializer
    permission_classes = [IsAdminUser]
    queryset = User.objects.all()
    lookup_field = 'pk'


# ============== Device Management Views (Admin) ==============

class StudentDeviceListView(generics.ListAPIView):
    """
    List all students with their devices.
    Admin can see all registered devices for each student.
    """
    serializer_class = StudentDeviceListSerializer
    permission_classes = [IsAdminUser]
    filter_backends = [SearchFilter, OrderingFilter, DjangoFilterBackend]
    search_fields = ['username', 'name']
    ordering_fields = ['created_at', 'username', 'name']
    
    def get_queryset(self):
        return User.objects.filter(user_type='student').prefetch_related('devices').order_by('-created_at')


class StudentDeviceDetailView(generics.RetrieveAPIView):
    """
    Get detailed device information for a specific student.
    """
    serializer_class = StudentDeviceListSerializer
    permission_classes = [IsAdminUser]
    
    def get_queryset(self):
        return User.objects.filter(user_type='student').prefetch_related('devices')


@api_view(['PATCH'])
@permission_classes([IsAdminUser])
def update_student_max_devices(request, pk):
    """
    Update the maximum number of allowed devices for a specific student.
    Admin can increase or decrease the limit.
    """
    try:
        student = User.objects.get(pk=pk, user_type='student')
    except User.DoesNotExist:
        return Response({'error': 'Student not found'}, status=status.HTTP_404_NOT_FOUND)
    
    serializer = UpdateMaxDevicesSerializer(data=request.data)
    if serializer.is_valid():
        new_max = serializer.validated_data['max_allowed_devices']
        student.max_allowed_devices = new_max
        student.save(update_fields=['max_allowed_devices'])
        
        # If new max is less than current active devices, deactivate oldest ones
        active_devices = UserDevice.objects.filter(user=student, is_active=True).order_by('last_used_at')
        active_count = active_devices.count()
        
        if active_count > new_max:
            # Deactivate oldest devices to match new limit
            devices_to_deactivate = active_devices[:active_count - new_max]
            for device in devices_to_deactivate:
                device.is_active = False
                device.save(update_fields=['is_active'])
        
        return Response({
            'message': f'Max devices updated to {new_max}',
            'max_allowed_devices': new_max,
            'active_devices_count': UserDevice.objects.filter(user=student, is_active=True).count()
        })
    
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['DELETE'])
@permission_classes([IsAdminUser])
def remove_student_device(request, pk, device_id):
    """
    Remove (delete) a specific device from a student.
    This will log out that device immediately (next API call will fail).
    """
    try:
        student = User.objects.get(pk=pk, user_type='student')
    except User.DoesNotExist:
        return Response({'error': 'Student not found'}, status=status.HTTP_404_NOT_FOUND)
    
    try:
        device = UserDevice.objects.get(pk=device_id, user=student)
    except UserDevice.DoesNotExist:
        return Response({'error': 'Device not found for this student'}, status=status.HTTP_404_NOT_FOUND)
    
    device_name = device.device_name
    device.delete()
    
    return Response({
        'message': f'Device "{device_name}" has been removed',
        'active_devices_count': UserDevice.objects.filter(user=student, is_active=True).count()
    })


@api_view(['POST'])
@permission_classes([IsAdminUser])
def remove_all_student_devices(request, pk):
    """
    Remove all devices from a student, forcing them to login again.
    """
    try:
        student = User.objects.get(pk=pk, user_type='student')
    except User.DoesNotExist:
        return Response({'error': 'Student not found'}, status=status.HTTP_404_NOT_FOUND)
    
    deleted_count = UserDevice.objects.filter(user=student).delete()[0]
    
    return Response({
        'message': f'All {deleted_count} device(s) have been removed',
        'active_devices_count': 0
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def my_devices(request):
    """
    Get current user's registered devices (for students to see their own devices).
    """
    user = request.user
    
    if user.user_type != 'student':
        return Response({'message': 'Device tracking is only for students'}, status=status.HTTP_200_OK)
    
    devices = UserDevice.objects.filter(user=user, is_active=True)
    serializer = UserDeviceSerializer(devices, many=True)
    
    return Response({
        'max_allowed_devices': user.max_allowed_devices,
        'active_devices_count': devices.count(),
        'devices': serializer.data
    })

