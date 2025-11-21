from datetime import timedelta
from django.utils import timezone
from rest_framework import viewsets, mixins, status
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny, IsAuthenticated, BasePermission, IsAdminUser
from rest_framework.response import Response
from rest_framework import serializers
from rest_framework.views import APIView
from rest_framework.exceptions import AuthenticationFailed, PermissionDenied
from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from django.conf import settings
from .models import User
from .serializers import (
    UserRegistrationSerializer, 
    KeyResetSerializer, 
    UserDetailSerializer,
    PasswordChangeSerializer
)
from .permissions import IsSelfOrAdmin

class UserAccountViewSet(
    mixins.CreateModelMixin, 
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    mixins.DestroyModelMixin,
    mixins.ListModelMixin,
    viewsets.GenericViewSet
):
    queryset = User.objects.all()
    
    def get_serializer_class(self):
        if self.action == 'create':
            return UserRegistrationSerializer
        elif self.action == 'reset_key':
            return KeyResetSerializer
        elif self.action == 'change_password':
            return PasswordChangeSerializer
        
        return UserDetailSerializer 

    def get_queryset(self):
        """
        Admins see all users. Regular users only see their own account.
        """
        user = self.request.user
        
        if user.is_authenticated and (user.is_staff or user.is_superuser):
            return super().get_queryset()        
        return User.objects.filter(pk=user.pk)

    def get_permissions(self):
        if self.action in ['create', 'reset_key', 'get_salt']:
            self.permission_classes = [AllowAny]
        elif self.action == 'list':
            self.permission_classes = [IsAdminUser]
        elif self.action in ['retrieve', 'update', 'partial_update', 'destroy']:
            self.permission_classes = [IsAuthenticated, IsSelfOrAdmin]
        else:
            self.permission_classes = [IsAuthenticated]            
        return super().get_permissions()

    def perform_update(self, serializer):
        """
        Enforces that only admin users can change the 'subscription_plan'.
        """
        user = self.request.user
        instance = self.get_object() # The user being updated
        
        if 'subscription_plan' in serializer.validated_data:
            new_plan = serializer.validated_data['subscription_plan']
            current_plan = instance.subscription_plan
            if new_plan != current_plan and not (user.is_staff or user.is_superuser):
                raise PermissionDenied("Only administrators can change the subscription plan.")        
        serializer.save()

    @action(detail=False, methods=['get'])
    def me(self, request):
        user = request.user
        serializer = self.get_serializer(user)
        return Response(serializer.data)

    @action(detail=False, methods=['get'], url_path='get-salt')
    def get_salt(self, request):
        username = request.query_params.get('username')
        if not username:
            return Response({'error': 'Username query parameter is required.'}, status=status.HTTP_400_BAD_REQUEST)
        try:
            user = User.objects.get(username=username)
            return Response({'salt': user.salt, 'username': user.username})
        except User.DoesNotExist:
            return Response({'error': 'User not found.'}, status=status.HTTP_404_NOT_FOUND)
        
    @action(detail=False, methods=['post'], url_path='reset-key')
    def reset_key(self, request):
        serializer = self.get_serializer(data=request.data)
        if serializer.is_valid():
            user = serializer.instance
            user.salt = serializer.validated_data['new_salt']
            user.key_hash = serializer.validated_data['new_key_hash']
            user.encrypted_dek = serializer.validated_data['new_encrypted_dek']
            user.save()
            return Response({"message": "Your key has been reset successfully."}, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=['post'], url_path='change-password')
    def change_password(self, request):
        user = request.user
        serializer = self.get_serializer(user, data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response({"message": "Password changed successfully."}, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class ValidateTokenView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        return Response({
            "success": True,
             "id":str(user.id),
        "username":str(user.username),
        'salt':str(user.salt),
        'encrypted_dek':str(user.encrypted_dek),
        'subscription_plan':str(user.subscription_plan)

        })

class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    MAX_FAILED_ATTEMPTS = 3
    LOCKOUT_DURATION = 15 # IT IS IN MINUTES.
    
    def validate(self, attrs):
        username = attrs.get('username')
        key_hash = attrs.get('password')

        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            raise AuthenticationFailed("Invalid credentials.")

        if user.is_locked and not user.lockout_until:
             raise PermissionDenied("Account is locked. Please contact an administrator to unlock your account.")
        
        now = timezone.now()
        if user.is_locked and user.lockout_until and now < user.lockout_until:
            time_left = (user.lockout_until - now)
            minutes_left = (time_left.total_seconds() + 59) // 60
            raise PermissionDenied(f"Account is locked due to failed attempts. Please try again in {int(minutes_left)} minutes.")

        if user.key_hash != key_hash:
            user.failed_login_attempts += 1
            if user.failed_login_attempts >= self.MAX_FAILED_ATTEMPTS:
                user.is_locked = True
                user.lockout_until = timezone.now() + timedelta(minutes=self.LOCKOUT_DURATION)
                user.save()
                raise AuthenticationFailed(f"Account locked due to {self.MAX_FAILED_ATTEMPTS} failed attempts. Please try again after {self.LOCKOUT_DURATION} minutes.")
            user.save()
            raise AuthenticationFailed("Invalid username or password.")

        if user.failed_login_attempts > 0 or user.lockout_until is not None:
            user.failed_login_attempts = 0
            user.lockout_until = None
            user.save()
        
        self.user = user 
        
        refresh = self.get_token(self.user)
        
        return {
            'refresh': str(refresh), 
            'access': str(refresh.access_token),
            "id": str(self.user.id),
            "username": str(self.user.username),
            'salt': str(self.user.salt),
            'encrypted_dek': str(self.user.encrypted_dek),
            'subscription_plan':str(self.user.subscription_plan)
        }

class CustomTokenObtainPairView(TokenObtainPairView):
    serializer_class = CustomTokenObtainPairSerializer