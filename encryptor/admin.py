from django.contrib import admin
from .models import FileMetadata, FileContent

class FileMetadataAdmin(admin.ModelAdmin):
    list_display = ('file_name', 'owner', 'file_type', 'file_size', 'created_at')
    list_filter = ('owner', 'file_type')
    search_fields = ('file_name', 'owner__username')

admin.site.register(FileMetadata, FileMetadataAdmin)
admin.site.register(FileContent)