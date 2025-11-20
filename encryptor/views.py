import os
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.filters import SearchFilter
from rest_framework_simplejwt.authentication import JWTAuthentication
from django.conf import settings
from django_filters.rest_framework import DjangoFilterBackend
from .models import FileMetadata
from .serializers import FileMetadataSerializer
from .pagination import StandardResultsSetPagination
from .filter import FileFilter
from auth_app.permissions import IsUserNotLocked
from django.db.models import Sum
from rest_framework import serializers
class FileViewSet(viewsets.ModelViewSet):
    serializer_class = FileMetadataSerializer
    permission_classes = [IsAuthenticated, IsUserNotLocked]
    authentication_classes= [JWTAuthentication]
    pagination_class = StandardResultsSetPagination
    filter_backends= [DjangoFilterBackend, SearchFilter]
    filterset_class = FileFilter
    search_fields = ['file_name','file_type','category','created_at']
    # Define the total storage quota per user (4 GB)
    STORAGE_QUOTA_GB = 0.01
    STORAGE_QUOTA_BYTES = STORAGE_QUOTA_GB * 1024 * 1024 * 1024
    def get_queryset(self):
        return FileMetadata.objects.filter(owner=self.request.user)

    def perform_create(self, serializer):
        user  = self.request.user
        new_file_size = serializer.validated_data.get('file_size',0)
        current_usage_bytes = self.get_queryset().aggregate(Sum('file_size'))['file_size__sum'] or 0
        projected_usage_bytes = current_usage_bytes + new_file_size
        if projected_usage_bytes>self.STORAGE_QUOTA_BYTES:
            current_usage_gb = current_usage_bytes/(1024*1024*1024)
            error_message = (
                f"Storage quota exceeded. Your current usage is {current_usage_gb:.2f} GB. "
                f"The maximum allowed storage is {self.STORAGE_QUOTA_GB} GB. "
                "Please delete some data or upgrade your plan."
            )
            raise serializers.ValidationError({'file_size': [error_message]})
        serializer.save(owner=user)
    
    def _get_content_filepath(self, metadata_id):
        content_dir = os.path.join(settings.MEDIA_ROOT, 'file_content')
        os.makedirs(content_dir, exist_ok=True)
        return os.path.join(content_dir, f"{metadata_id}.txt")

    @action(detail=True, methods=['get', 'put'], url_path='content')
    def content(self, request, pk=None):
        metadata = self.get_object()
        filepath = self._get_content_filepath(metadata.id)

        if request.method == 'GET':
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    encrypted_blob = f.read()
                # Return the blob in the exact same format as before
                return Response({'encrypted_blob': encrypted_blob})
            except FileNotFoundError:
                return Response({"error": "Content not found."}, status=status.HTTP_404_NOT_FOUND)
            except Exception as e:
                return Response({"error": f"Error reading file: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        elif request.method == 'PUT':
            encrypted_blob = request.data.get('encrypted_blob')
            
            # Manual validation since we removed the serializer
            if encrypted_blob is None:
                 return Response({"encrypted_blob": ["This field is required."]}, status=status.HTTP_400_BAD_REQUEST)

            try:
                with open(filepath, 'w', encoding='utf-8') as f:
                    f.write(encrypted_blob)
                # Return 204 No Content, just like update_or_create did
                return Response(status=status.HTTP_204_NO_CONTENT)
            except Exception as e:
                return Response({"error": f"Error writing file: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

