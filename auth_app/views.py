from datetime import timedelta
from django.utils import timezone
from rest_framework import viewsets, mixins, status
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework import serializers
from rest_framework.views import APIView
# Assuming 'User' model and serializers are defined in the same project structure
from .models import User 
from .serializers import (
    UserRegistrationSerializer, 
    KeyResetSerializer, 
    UserDetailSerializer,
    PasswordChangeSerializer
)
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.exceptions import AuthenticationFailed, PermissionDenied
from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

# --- UserAccountViewSet remains unchanged ---

class UserAccountViewSet(mixins.CreateModelMixin, viewsets.GenericViewSet):
    queryset = User.objects.all()
    
    def get_serializer_class(self):
        if self.action == 'create':
            return UserRegistrationSerializer
        elif self.action == 'reset_key':
            return KeyResetSerializer
        elif self.action == 'change_password':
            return PasswordChangeSerializer
        return UserDetailSerializer

    def get_permissions(self):
        if self.action in ['create', 'reset_key', 'get_salt']:
            self.permission_classes = [AllowAny]
        else:
            self.permission_classes = [IsAuthenticated]
        return super().get_permissions()

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

# --- ValidateTokenView remains unchanged ---

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
        })

# --- Custom Token Serializer (FIXED) ---

class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    MAX_FAILED_ATTEMPTS = 3
    LOCKOUT_DURATION = 15 # IT IS IN MINUTES.
    
    def validate(self, attrs):
        username = attrs.get('username')
        key_hash = attrs.get('password') # Client sends the key_hash in the 'password' field

        # 1. User Lookup
        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            # Raise AuthenticationFailed for consistency
            raise AuthenticationFailed("Invalid credentials.") 

        # 2. Check and Clear Lockout Status
        now = timezone.now()
        
        # Check if user is locked and the time is still in the future
        if user.is_locked and user.lockout_until and now < user.lockout_until:
            time_left = (user.lockout_until - now)
            # Use total_seconds() and integer division for robust minute calculation
            minutes_left = (time_left.total_seconds() + 59) // 60
            raise PermissionDenied(f"Account is locked due to failed attempts. Please try again in {int(minutes_left)} minutes.")
        
        # Check if user is locked but the lockout time has expired (auto-unlock)
        elif user.is_locked and user.lockout_until and now >= user.lockout_until:
            # Lockout period has expired - clear the lock fields before proceeding
            user.is_locked = False
            user.lockout_until = None
            user.failed_login_attempts = 0
            # User is saved on successful authentication below, so we can defer save unless needed immediately

        # NOTE: If user was manually unlocked (is_locked=False) or auto-unlocked above, execution continues here.
        
        # 3. Perform Key Hash Authentication
        if user.key_hash != key_hash:
            # Key hash failed - update failed attempts and potentially lock account
            user.failed_login_attempts += 1
            
            if user.failed_login_attempts >= self.MAX_FAILED_ATTEMPTS:
                user.is_locked = True
                # FIX: Use timedelta for time arithmetic
                user.lockout_until = timezone.now() + timedelta(minutes=self.LOCKOUT_DURATION)
                user.save()
                raise AuthenticationFailed(f"Account locked due to {self.MAX_FAILED_ATTEMPTS} failed attempts. Please try again after {self.LOCKOUT_DURATION} minutes.")
            
            user.save()
            raise AuthenticationFailed("Invalid username or password.")

        # 4. Authentication Successful - Reset attempts, set self.user, and generate tokens
        
        # Ensure ALL lockout/attempt fields are reset upon successful login
        user.failed_login_attempts = 0
        user.is_locked = False
        user.lockout_until = None
        user.save()
        
        # Manually set self.user for token generation (since we bypassed super().validate())
        self.user = user 
        
        refresh = self.get_token(self.user)
        
        return {
            'refresh': str(refresh), 
            'access': str(refresh.access_token),
            "id": str(self.user.id),
            "username": str(self.user.username),
            'salt': str(self.user.salt),
            'encrypted_dek': str(self.user.encrypted_dek),
        }

# --- Custom Token View remains unchanged ---

class CustomTokenObtainPairView(TokenObtainPairView):
    serializer_class = CustomTokenObtainPairSerializer