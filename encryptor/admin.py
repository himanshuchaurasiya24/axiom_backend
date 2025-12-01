from django.contrib import admin
from .models import FileMetadata, Category

class FileMetadataAdmin(admin.ModelAdmin):
    list_display = ('file_name', 'owner', 'file_type', 'file_size', 'created_at')
    list_filter = ('owner', 'file_type')
    search_fields = ('file_name', 'owner__username')

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        # only limit the category field; admins/superuser can keep full access if you prefer
        if db_field.name == "category":
            if request.user.is_superuser:
                # superuser sees all categories
                kwargs["queryset"] = Category.objects.all()
            else:
                # regular users see only their categories
                kwargs["queryset"] = Category.objects.filter(owner=request.user)
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

admin.site.register(FileMetadata, FileMetadataAdmin)
admin.site.register(Category)
