from rest_framework import viewsets, mixins, status
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework import serializers
from rest_framework.views import APIView
from .models import User
from .serializers import (
    UserRegistrationSerializer, 
    KeyResetSerializer, 
    UserDetailSerializer,
    PasswordChangeSerializer
)
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

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

class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    def validate(self, attrs):
        key_hash = attrs.get('password')
        username = attrs.get('username')
        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            raise serializers.ValidationError("Invalid credentials.")
        if user.key_hash != key_hash:
            raise serializers.ValidationError("Invalid credentials.")
        refresh = self.get_token(user)
        return {'refresh': str(refresh), 
        'access': str(refresh.access_token),
        "id":str(user.id),
        "username":str(user.username),
        'salt':str(user.salt),
        'encrypted_dek':str(user.encrypted_dek),
        }

class CustomTokenObtainPairView(TokenObtainPairView):
    serializer_class = CustomTokenObtainPairSerializer