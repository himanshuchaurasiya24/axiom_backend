from rest_framework import serializers
from .models import FileMetadata, FileContent

class FileContentSerializer(serializers.ModelSerializer):
    class Meta:
        model = FileContent
        fields = ['encrypted_blob']

class FileMetadataSerializer(serializers.ModelSerializer):
    class Meta:
        model = FileMetadata
        fields = ['id', 'file_name', 'file_type', 'file_size', 'created_at', 'updated_at']
