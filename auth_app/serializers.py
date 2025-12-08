from rest_framework import serializers
from .models import User
from .utils import generate_secure_token, hash_token
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from datetime import timedelta
from django.utils import timezone
from rest_framework.exceptions import AuthenticationFailed, PermissionDenied

class UserDetailSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = [
            'id', 'username', 'salt', 'encrypted_dek', 'created_at', 
            'subscription_plan', 'subscription_expiry', 'upload_limit_mb'
        ]

class UserRegistrationSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = [
            'username', 'salt', 'key_hash', 'encrypted_dek', 
            'recovery_encrypted_dek', 'recovery_key_hash', 'recovery_salt'
        ]
        extra_kwargs = {
            'salt': {'write_only': True},
            'key_hash': {'write_only': True},
            'encrypted_dek': {'write_only': True},
            'recovery_encrypted_dek': {'write_only': True},
            'recovery_key_hash': {'write_only': True},
            'recovery_salt': {'write_only': True},
        }

    def create(self, validated_data):
        user = User.objects.create_user(
            username=validated_data['username'],
            salt=validated_data['salt'],
            key_hash=validated_data['key_hash'],
            encrypted_dek=validated_data['encrypted_dek'],
            recovery_encrypted_dek=validated_data['recovery_encrypted_dek'],
            recovery_key_hash=validated_data['recovery_key_hash'],
            recovery_salt=validated_data['recovery_salt']
        )
        return user

class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    MAX_FAILED_ATTEMPTS = 3
    LOCKOUT_DURATION = 15 
    
    def validate(self, attrs):
        username = attrs.get('username')
        key_hash = attrs.get('password')

        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            raise AuthenticationFailed("Invalid credentials.")

        # --- 1. Account Locking Check (Keep this first to prevent brute force on locked accounts) ---
        if user.is_locked and not user.lockout_until:
             raise PermissionDenied("Account is locked. Please contact support.")
        
        now = timezone.now()
        if user.is_locked and user.lockout_until and now < user.lockout_until:
            time_left = (user.lockout_until - now)
            minutes_left = (time_left.total_seconds() + 59) // 60
            raise PermissionDenied(f"Account is locked. Try again in {int(minutes_left)} minutes.")
        elif user.is_locked and user.lockout_until and now >= user.lockout_until:
            user.is_locked = False
            user.lockout_until = None
            user.failed_login_attempts = 0
            user.save()

        # --- 2. Password Validation (MOVED UP) ---
        # ⭐️ We check password BEFORE checking subscription status
        if user.key_hash != key_hash:
            user.failed_login_attempts += 1
            if user.failed_login_attempts >= self.MAX_FAILED_ATTEMPTS:
                user.is_locked = True
                user.lockout_until = timezone.now() + timedelta(minutes=self.LOCKOUT_DURATION)
                user.save()
                raise AuthenticationFailed(f"Account locked due to failed attempts.")
            user.save()
            raise AuthenticationFailed("Invalid username or password.")

        if user.failed_login_attempts > 0 or user.lockout_until is not None:
            user.failed_login_attempts = 0
            user.lockout_until = None
            user.save()

        # --- 3. Subscription Expiry Check (MOVED DOWN) ---
        # ⭐️ Only check this if the password was correct
        if not (user.is_staff or user.is_superuser):
            if not user.is_subscription_active:
                # Now we know the user is who they say they are, so it's safe to tell them about the plan
                raise AuthenticationFailed("Your plan has expired. To login, you need to upgrade your account.")

        
        self.user = user 
        refresh = self.get_token(self.user)
        
        return {
            'refresh': str(refresh), 
            'access': str(refresh.access_token),
            "id": str(self.user.id),
            "username": str(self.user.username),
            'salt': str(self.user.salt),
            'encrypted_dek': str(self.user.encrypted_dek),
            'subscription_plan': str(self.user.subscription_plan),
            'upload_limit_mb': self.user.upload_limit_mb,
            'is_locked': str(self.user.is_locked),
            'days_left':str(self.user.days_left)
        }

class InitiateRecoverySerializer(serializers.Serializer):
    username = serializers.CharField(write_only=True)
    recovery_key_hash = serializers.CharField(write_only=True)
    recovery_encrypted_dek = serializers.CharField(read_only=True)
    recovery_salt = serializers.CharField(read_only=True)

    def validate(self, data):
        try:
            user = User.objects.get(username=data['username'])
        except User.DoesNotExist:
            raise serializers.ValidationError("Invalid credentials.")
        if data['recovery_key_hash'] != user.recovery_key_hash:
             raise serializers.ValidationError("Invalid Recovery Key.")
        return {'user': user, 'recovery_encrypted_dek': user.recovery_encrypted_dek, 'recovery_salt': user.recovery_salt}

class FinalizeRecoverySerializer(serializers.Serializer):
    username = serializers.CharField(write_only=True)
    new_salt = serializers.CharField(write_only=True)
    new_key_hash = serializers.CharField(write_only=True)
    new_encrypted_dek = serializers.CharField(write_only=True)
    def validate(self, data):
        try:
            self.user = User.objects.get(username=data['username'])
        except User.DoesNotExist:
            raise serializers.ValidationError("User not found.")
        return data
    def save(self):
        user = self.user
        user.salt = self.validated_data['new_salt']
        user.key_hash = self.validated_data['new_key_hash']
        user.encrypted_dek = self.validated_data['new_encrypted_dek']
        user.save()
        return user

class PasswordChangeSerializer(serializers.Serializer):
    new_salt = serializers.CharField(write_only=True)
    new_key_hash = serializers.CharField(write_only=True)
    new_encrypted_dek = serializers.CharField(write_only=True)
    def update(self, instance, validated_data):
        instance.salt = validated_data['new_salt']
        instance.key_hash = validated_data['new_key_hash']
        instance.encrypted_dek = validated_data['new_encrypted_dek']
        instance.save(update_fields=['salt', 'key_hash', 'encrypted_dek'])
        return instance