from django.db import models
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
import uuid

class UserManager(BaseUserManager):
    def create_user(self, username, key_hash, recovery_key_hash, recovery_salt, encrypted_dek, **extra_fields):
        user = self.model(
            username=username, 
            key_hash=key_hash, 
            recovery_key_hash=recovery_key_hash,
            recovery_salt=recovery_salt,
            encrypted_dek=encrypted_dek,
            **extra_fields
        )
        user.save(using=self._db)
        return user

    def create_superuser(self, username, key_hash, password=None, **extra_fields):
        extra_fields.setdefault('recovery_key_hash', 'dummy_hash')
        extra_fields.setdefault('recovery_salt', 'dummy_salt')
        extra_fields.setdefault('encrypted_dek', 'dummy_dek')
        user = self.create_user(username, key_hash, **extra_fields)
        user.is_staff = True
        user.is_superuser = True
        user.set_password(password if password else 'adminpassword')
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

    objects = UserManager()
    USERNAME_FIELD = 'username'
    REQUIRED_FIELDS = ['key_hash']
