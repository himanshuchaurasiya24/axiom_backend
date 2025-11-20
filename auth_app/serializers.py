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
        fields = ['id', 'username', 'salt', 'encrypted_dek', 'created_at']

class UserRegistrationSerializer(serializers.ModelSerializer):
    recovery_key = serializers.CharField(read_only=True)

    class Meta:
        model = User
        fields = ['username', 'salt', 'key_hash', 'encrypted_dek', 'recovery_key']
        extra_kwargs = {
            'salt': {'write_only': True},
            'key_hash': {'write_only': True},
            'encrypted_dek': {'write_only': True},
            'recovery_key': {'read_only': True},
        }

    def create(self, validated_data):
        recovery_salt = generate_secure_token(16)
        recovery_key_plaintext = generate_secure_token(32)
        recovery_key_hashed = hash_token(recovery_key_plaintext, recovery_salt)

        user = User.objects.create_user(
            username=validated_data['username'],
            salt=validated_data['salt'],
            key_hash=validated_data['key_hash'],
            encrypted_dek=validated_data['encrypted_dek'],
            recovery_key_hash=recovery_key_hashed,
            recovery_salt=recovery_salt
        )
        user.recovery_key = recovery_key_plaintext
        return user

class KeyResetSerializer(serializers.Serializer):
    username = serializers.CharField(write_only=True)
    recovery_key = serializers.CharField(write_only=True)
    new_salt = serializers.CharField(write_only=True)
    new_key_hash = serializers.CharField(write_only=True)
    new_encrypted_dek = serializers.CharField(write_only=True)

    def validate(self, data):
        try:
            user = User.objects.get(username=data['username'])
        except User.DoesNotExist:
            raise serializers.ValidationError("Invalid credentials provided.")

        provided_key_hash = hash_token(data['recovery_key'], user.recovery_salt)
        if provided_key_hash != user.recovery_key_hash:
            raise serializers.ValidationError("Invalid credentials provided.")
        
        self.instance = user
        return data

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

# --- Custom Token Serializer (FIXED) ---

class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    MAX_FAILED_ATTEMPTS = 3
    LOCKOUT_DURATION = 15 # IT IS IN MINUTES.
    
    def validate(self, attrs):
        username = attrs.get('username')
        key_hash = attrs.get('password') # Client sends the key_hash in the 'password' field

        # 1. User Lookup
        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            raise AuthenticationFailed("Invalid credentials.") 

        # 2. Check and Clear Lockout Status
        now = timezone.now()
        
        # A. Check if account is actively locked due to failed attempts (lockout_until is in the future)
        if user.is_locked and user.lockout_until and now < user.lockout_until:
            time_left = (user.lockout_until - now)
            minutes_left = (time_left.total_seconds() + 59) // 60
            raise PermissionDenied(f"Account is locked due to failed attempts. Please try again in {int(minutes_left)} minutes.")
        
        # B. Check if account is locked but the time has expired (SYSTEM AUTO-UNLOCK)
        # This only happens if lockout_until is set (meaning it was a system lock)
        elif user.is_locked and user.lockout_until and now >= user.lockout_until:
            # Lockout period has expired - clear the lock fields before proceeding
            user.is_locked = False
            user.lockout_until = None
            user.failed_login_attempts = 0
            user.save()
            # Execution continues to Step 3
            
        # C. New check: If is_locked is True, but lockout_until is None or in the past, 
        # assume this is a PERMANENT ADMIN LOCK.
        elif user.is_locked and not user.lockout_until:
             # This prevents login if an admin explicitly set is_locked=True without a time limit
             # The user must contact the admin to unlock.
             raise PermissionDenied("Account is locked. Please contact support to unlock your account.")


        # 3. Perform Key Hash Authentication
        if user.key_hash != key_hash:
            # Key hash failed - update failed attempts and potentially lock account
            user.failed_login_attempts += 1
            
            if user.failed_login_attempts >= self.MAX_FAILED_ATTEMPTS:
                user.is_locked = True
                user.lockout_until = timezone.now() + timedelta(minutes=self.LOCKOUT_DURATION)
                user.save()
                raise AuthenticationFailed(f"Account locked due to {self.MAX_FAILED_ATTEMPTS} failed attempts. Please try again after {self.LOCKOUT_DURATION} minutes.")
            
            user.save()
            raise AuthenticationFailed("Invalid username or password.")

        # 4. Authentication Successful - Reset attempts and set self.user
        
        # CRITICAL FIX: Only reset failed_login_attempts and lockout_until.
        # DO NOT set user.is_locked = False here. If an admin set it to True 
        # without a time limit, we respect that lock (handled in 2.C).
        if user.failed_login_attempts > 0 or user.lockout_until is not None:
            user.failed_login_attempts = 0
            user.lockout_until = None
            user.save()
        
        # Manually set self.user for token generation
        self.user = user 
        
        refresh = self.get_token(self.user)
        
        return {
            'refresh': str(refresh), 
            'access': str(refresh.access_token),
            "id": str(self.user.id),
            "username": str(self.user.username),
            'salt': str(self.user.salt),
            'encrypted_dek': str(self.user.encrypted_dek),
        }