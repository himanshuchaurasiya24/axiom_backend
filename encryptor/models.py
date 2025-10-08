from django.db import models
from django.conf import settings
import uuid

class FileMetadata(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='files')
    file_name = models.CharField(max_length=255)
    file_type = models.CharField(max_length=100)
    file_size = models.BigIntegerField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

class FileContent(models.Model):
    metadata = models.OneToOneField(FileMetadata, on_delete=models.CASCADE, primary_key=True, related_name='content')
    encrypted_blob = models.TextField()