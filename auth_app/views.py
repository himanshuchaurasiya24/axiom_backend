from django.utils import timezone
from django.http import JsonResponse
from rest_framework import viewsets, mixins, status
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny, IsAuthenticated, IsAdminUser
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.exceptions import PermissionDenied
from rest_framework_simplejwt.views import TokenObtainPairView
from django.conf import settings
from .models import User,SubscriptionPlan
from .serializers import (
    UserRegistrationSerializer, 
    InitiateRecoverySerializer,
    FinalizeRecoverySerializer,
    UserDetailSerializer,
    PasswordChangeSerializer,
    CustomTokenObtainPairSerializer,
    AccountDashboardSerializer
)
from .permissions import IsSelfOrAdmin, IsSubscriptionActive

class SubscriptionInfoView(APIView):
    """
    Returns a list of all available subscription plans with their 
    configured limits and duration.
    """
    permission_classes = [AllowAny]

    def get(self, request):
        plans_data = []
        
        for plan in SubscriptionPlan:
            plans_data.append({
                "plan_id": plan.value,             # e.g. "FREE", "STANDARD"
                "name": plan.label,                # e.g. "Free Tier", "Standard Tier"
                "storage_limit_mb": plan.get_upload_limit(),
                "duration_days": plan.get_duration(),
                "description": f"{plan.get_duration()} days validity with {plan.get_upload_limit()} MB storage."
            })
            
        return Response(plans_data)

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
        user = self.request.user
        if user.is_authenticated and (user.is_staff or user.is_superuser):
            return super().get_queryset()        
        return User.objects.filter(pk=user.pk)

    def get_permissions(self):
        if self.action in ['create', 'get_salt', 'get_recovery_salt', 'initiate_recovery', 'finalize_recovery']:
            self.permission_classes = [AllowAny]
        elif self.action == 'list':
            self.permission_classes = [IsAdminUser]
        elif self.action in ['retrieve', 'update', 'partial_update', 'destroy']:
            self.permission_classes = [IsAuthenticated, IsSelfOrAdmin, IsSubscriptionActive]
        else:
            self.permission_classes = [IsAuthenticated, IsSubscriptionActive]            
        return super().get_permissions()

    def perform_update(self, serializer):
        user = self.request.user
        instance = self.get_object()
        
        if 'subscription_plan' in serializer.validated_data:
            new_plan = serializer.validated_data['subscription_plan']
            current_plan = instance.subscription_plan
            if new_plan != current_plan and not (user.is_staff or user.is_superuser):
                raise PermissionDenied("Only administrators can change the subscription plan manually.")
        
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

    @action(detail=False, methods=['post'], url_path='initiate-recovery')
    def initiate_recovery(self, request):
        serializer = self.get_serializer(data=request.data)
        if serializer.is_valid():
            return Response({
                "recovery_encrypted_dek": serializer.validated_data['recovery_encrypted_dek'],
                "recovery_salt": serializer.validated_data['recovery_salt']
            }, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=['post'], url_path='finalize-recovery')
    def finalize_recovery(self, request):
        serializer = self.get_serializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response({"message": "Account recovered successfully."}, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=['post'], url_path='change-password')
    def change_password(self, request):
        user = request.user
        serializer = self.get_serializer(user, data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response({"message": "Password changed successfully."}, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

def health_check(request):
        return JsonResponse({'status': 'running'}, status=200)

class ValidateTokenView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        
        if user.is_locked:
            return Response({"detail": "User account is locked."}, status=status.HTTP_403_FORBIDDEN)
        if not (user.is_staff or user.is_superuser):
            if not user.is_subscription_active:
                return Response(
                    {"detail": "Your plan has expired. To login, you need to upgrade your account."}, 
                    status=status.HTTP_403_FORBIDDEN
                )
        
        serializer = AccountDashboardSerializer(user)
        return Response(serializer.data)

class CustomTokenObtainPairView(TokenObtainPairView):
    serializer_class = CustomTokenObtainPairSerializer

class AppInfoView(APIView):
    authentication_classes=[]
    permission_classes = [AllowAny]
    def get(self, request, format=None):
        min_version = getattr(settings, 'MINIMUM_APP_VERSION', None)
        return Response({"minimum_required_version": min_version})