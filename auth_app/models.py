from django.db import models
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
import uuid
from django.utils import timezone
from datetime import timedelta

class UserManager(BaseUserManager):
    def create_user(self, username, salt, key_hash, recovery_key_hash, recovery_salt, encrypted_dek, recovery_encrypted_dek, **extra_fields):
        user = self.model(
            username=username,
            salt=salt,
            key_hash=key_hash, 
            recovery_key_hash=recovery_key_hash,
            recovery_salt=recovery_salt,
            encrypted_dek=encrypted_dek,
            recovery_encrypted_dek=recovery_encrypted_dek, 
            **extra_fields
        )
        user.save(using=self._db)
        return user

    def create_superuser(self, username, password, **extra_fields):
        extra_fields.setdefault('salt', 'dummy_salt_for_admin')
        extra_fields.setdefault('key_hash', 'dummy_hash_for_admin')
        extra_fields.setdefault('recovery_key_hash', 'dummy_hash')
        extra_fields.setdefault('recovery_salt', 'dummy_salt')
        extra_fields.setdefault('encrypted_dek', 'dummy_dek')
        extra_fields.setdefault('recovery_encrypted_dek', 'dummy_recovery_dek')
        # Admins get PRO plan by default
        extra_fields.setdefault('subscription_plan', SubscriptionPlan.PRO)
        
        user = self.model(username=username, **extra_fields)
        user.set_password(password)
        user.is_staff = True
        user.is_superuser = True
        user.save(using=self._db)
        return user

class SubscriptionPlan(models.TextChoices):
    FREE = "FREE", "Free Tier"
    STANDARD = "STANDARD", "Standard Tier"
    PRO = "PRO", "Pro Tier"

    def get_duration(self):
        """Returns the locking period duration in days."""
        if self == self.FREE:
            return 30   # 1 Month duration for Free Tier
        elif self == self.STANDARD:
            return 180  # 6 months
        elif self == self.PRO:
            return 365  # 1 year
        return 30 # Default fallback

    def get_upload_limit(self):
        """Returns upload limit in MB."""
        if self == self.FREE:
            return 10  # 500 MB
        elif self == self.STANDARD:
            return 5120  # 5 GB
        elif self == self.PRO:
            return 51200  # 50 GB
        return 0

class User(AbstractBaseUser, PermissionsMixin):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    username = models.CharField(max_length=255, unique=True)    
    salt = models.CharField(max_length=255)
    key_hash = models.CharField(max_length=255)
    encrypted_dek = models.TextField() 
    recovery_encrypted_dek = models.TextField(default='') 
    recovery_key_hash = models.CharField(max_length=255)
    recovery_salt = models.CharField(max_length=255)    
    subscription_plan = models.CharField(
        max_length=10, 
        choices=SubscriptionPlan.choices, 
        default=SubscriptionPlan.FREE, 
        help_text="Current Subscription Tier"
    )
    subscription_expiry = models.DateTimeField(null=True, blank=True)    
    upload_limit_mb = models.IntegerField(default=500, help_text="Max upload size in MB")    
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    is_locked = models.BooleanField(default=False, help_text='If true, the user is locked out.')
    failed_login_attempts = models.IntegerField(default=0)
    lockout_until = models.DateTimeField(null=True, blank=True)
    objects = UserManager()
    USERNAME_FIELD = 'username'
    REQUIRED_FIELDS = []

    def __str__(self):
        return self.username

    def save(self, *args, **kwargs):
        plan_enum = SubscriptionPlan(self.subscription_plan)
        self.upload_limit_mb = plan_enum.get_upload_limit()
        should_recalculate_expiry = False
        
        if self._state.adding:
            should_recalculate_expiry = True
        else:
            try:
                old_user = User.objects.get(pk=self.pk)
                if old_user.subscription_plan != self.subscription_plan:
                    should_recalculate_expiry = True
            except User.DoesNotExist:
                should_recalculate_expiry = True

        if should_recalculate_expiry:
            duration = plan_enum.get_duration()
            if duration:
                self.subscription_expiry = timezone.now() + timedelta(days=duration)

        super().save(*args, **kwargs)
        
    @property
    def is_subscription_active(self):
        if not self.subscription_expiry:
            return True
        return timezone.now() < self.subscription_expiry
    @property
    def days_left(self):
        if not self.subscription_expiry:
            return -1
            
        remaining = self.subscription_expiry - timezone.now()
        
        if remaining.total_seconds() < 0:
            return 0
            
        return remaining.days