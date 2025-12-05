from datetime import timedelta
from django.utils import timezone
from rest_framework import viewsets, mixins, status
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny, IsAuthenticated, IsAdminUser
from rest_framework.response import Response
from rest_framework import serializers
from rest_framework.views import APIView
from rest_framework.exceptions import AuthenticationFailed, PermissionDenied
from rest_framework_simplejwt.views import TokenObtainPairView
from django.conf import settings
from .models import User
from .serializers import (
    UserRegistrationSerializer, 
    InitiateRecoverySerializer,
    FinalizeRecoverySerializer,
    UserDetailSerializer,
    PasswordChangeSerializer,
    CustomTokenObtainPairSerializer
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
        elif self.action == 'initiate_recovery':
            return InitiateRecoverySerializer
        elif self.action == 'finalize_recovery':
            return FinalizeRecoverySerializer
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
        # AllowAny for registration, salt fetching, and recovery steps
        if self.action in ['create', 'get_salt', 'get_recovery_salt', 'initiate_recovery', 'finalize_recovery']:
            self.permission_classes = [AllowAny]
        elif self.action == 'list':
            self.permission_classes = [IsAdminUser]
        elif self.action in ['retrieve', 'update', 'partial_update', 'destroy']:
            self.permission_classes = [IsAuthenticated, IsSelfOrAdmin]
        else:
            self.permission_classes = [IsAuthenticated]            
        return super().get_permissions()

    def perform_update(self, serializer):
        user = self.request.user
        instance = self.get_object()
        
        # Protect subscription plan changes
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

    # --- Get Salt specifically for Recovery Key hashing ---
    @action(detail=False, methods=['get'], url_path='get-recovery-salt')
    def get_recovery_salt(self, request):
        username = request.query_params.get('username')
        if not username:
            return Response({'error': 'Username query parameter is required.'}, status=status.HTTP_400_BAD_REQUEST)
        try:
            user = User.objects.get(username=username)
            return Response({'recovery_salt': user.recovery_salt})
        except User.DoesNotExist:
            return Response({'error': 'User not found.'}, status=status.HTTP_404_NOT_FOUND)

    # --- Step 1 of Recovery (Get Encrypted DEK) ---
    @action(detail=False, methods=['post'], url_path='initiate-recovery')
    def initiate_recovery(self, request):
        serializer = self.get_serializer(data=request.data)
        if serializer.is_valid():
            # Return the encrypted backup envelope so the client can decrypt the DEK
            return Response({
                "recovery_encrypted_dek": serializer.validated_data['recovery_encrypted_dek'],
                "recovery_salt": serializer.validated_data['recovery_salt']
            }, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    # --- Step 2 of Recovery (Save new Password data) ---
    @action(detail=False, methods=['post'], url_path='finalize-recovery')
    def finalize_recovery(self, request):
        serializer = self.get_serializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response({"message": "Account recovered successfully. Please log in with your new password."}, status=status.HTTP_200_OK)
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
        if user.is_locked:
            return Response(
                {"detail": "User account is locked."}, 
                status=status.HTTP_403_FORBIDDEN
            )
        return Response({
            "id":str(user.id),
            "username":str(user.username),
            'salt':str(user.salt),
            'encrypted_dek':str(user.encrypted_dek),
            'subscription_plan':str(user.subscription_plan),
            'is_locked':str(user.is_locked)
        })

class CustomTokenObtainPairView(TokenObtainPairView):
    serializer_class = CustomTokenObtainPairSerializer

class AppInfoView(APIView):
    permission_classes = [AllowAny]

    def get(self, request, format=None):
        min_version = getattr(settings, 'MINIMUM_APP_VERSION', None)
        data = {"minimum_required_version": min_version}
        return Response(data)