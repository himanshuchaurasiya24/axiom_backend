from django.contrib import admin
from .models import User

class UserAdmin(admin.ModelAdmin):
    list_display = ('username', 'id', 'created_at', 'is_staff')
    search_fields = ('username',)
    readonly_fields = ('id', 'created_at', 'salt', 'key_hash', 'encrypted_dek', 'recovery_salt', 'recovery_key_hash', 'last_login', 'password')
    exclude = ('groups', 'user_permissions', 'is_superuser', 'is_active')

admin.site.register(User, UserAdmin)