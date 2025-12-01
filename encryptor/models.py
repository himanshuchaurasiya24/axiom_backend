from django.db import models
from django.conf import settings
from auth_app.models import User
import uuid
class Category(models.Model):
    category= models.CharField(max_length=20, unique= True)
    owner = models.ForeignKey(User, on_delete= models.CASCADE, related_name='categories')
    def __str__(self):
            return f"{self.category}, owned by {self.owner}"
class FileMetadata(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='files')
    category = models.ForeignKey(Category, on_delete= models.CASCADE, related_name='files')
    file_name = models.CharField(max_length=255)
    file_type = models.CharField(max_length=100)
    file_size = models.BigIntegerField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
    def __str__(self):
        return f"{self.file_name}, {self.file_type}, {self.file_size} bytes"
