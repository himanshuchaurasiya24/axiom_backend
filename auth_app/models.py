from django.db import models
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
import uuid

class UserManager(BaseUserManager):
    def create_user(self, username, salt, key_hash, recovery_key_hash, recovery_salt, encrypted_dek, **extra_fields):
        user = self.model(
            username=username,
            salt=salt,
            key_hash=key_hash, 
            recovery_key_hash=recovery_key_hash,
            recovery_salt=recovery_salt,
            encrypted_dek=encrypted_dek,
            **extra_fields
        )
        user.save(using=self._db)
        return user

    def create_superuser(self, username, password, **extra_fields):
        # Note: The superuser does not follow the zero-knowledge model for simplicity.
        extra_fields.setdefault('salt', 'dummy_salt_for_admin')
        extra_fields.setdefault('key_hash', 'dummy_hash_for_admin')
        extra_fields.setdefault('recovery_key_hash', 'dummy_hash')
        extra_fields.setdefault('recovery_salt', 'dummy_salt')
        extra_fields.setdefault('encrypted_dek', 'dummy_dek')
        user = self.model(username=username, **extra_fields)
        user.set_password(password) # Use standard Django password hashing for admin
        user.is_staff = True
        user.is_superuser = True
        user.save(using=self._db)
        return user

class User(AbstractBaseUser, PermissionsMixin):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    username = models.CharField(max_length=255, unique=True)
    salt = models.CharField(max_length=255)
    key_hash = models.CharField(max_length=255)
    encrypted_dek = models.TextField() # Stores the encrypted Data Encryption Key
    recovery_key_hash = models.CharField(max_length=255)
    recovery_salt = models.CharField(max_length=255)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    is_locked = models.BooleanField(
        default=False,
        help_text='If true, the user is locked out and cannot log in.'
    )
    
    # ✅ Fields required by the custom token serializer
    failed_login_attempts = models.IntegerField(default=0)
    lockout_until = models.DateTimeField(null=True, blank=True)
    objects = UserManager()
    USERNAME_FIELD = 'username'
    # No required fields for createsuperuser to prompt for custom fields
    REQUIRED_FIELDS = []
    def __str__(self):
        return self.username