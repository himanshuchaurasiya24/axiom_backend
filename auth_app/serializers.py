from rest_framework import serializers
from .models import User
from .utils import generate_secure_token, hash_token

class UserDetailSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'salt', 'encrypted_dek', 'created_at']

class UserRegistrationSerializer(serializers.ModelSerializer):
    recovery_key = serializers.CharField(read_only=True)

    class Meta:
        model = User
        fields = ['username', 'key_hash', 'encrypted_dek', 'salt', 'recovery_key']
        extra_kwargs = {
            'key_hash': {'write_only': True},
            'encrypted_dek': {'write_only': True},
            'salt': {'read_only': True},
        }

    def create(self, validated_data):
        main_salt = generate_secure_token(16)
        recovery_salt = generate_secure_token(16)
        recovery_key_plaintext = generate_secure_token(32)
        recovery_key_hashed = hash_token(recovery_key_plaintext, recovery_salt)

        user = User.objects.create_user(
            username=validated_data['username'],
            key_hash=validated_data['key_hash'],
            encrypted_dek=validated_data['encrypted_dek'],
            recovery_key_hash=recovery_key_hashed,
            recovery_salt=recovery_salt,
            salt=main_salt
        )
        user.recovery_key = recovery_key_plaintext
        return user

class KeyResetSerializer(serializers.Serializer):
    username = serializers.CharField(write_only=True)
    recovery_key = serializers.CharField(write_only=True)
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
    new_key_hash = serializers.CharField(write_only=True)
    new_encrypted_dek = serializers.CharField(write_only=True)

    def update(self, instance, validated_data):
        instance.key_hash = validated_data['new_key_hash']
        instance.encrypted_dek = validated_data['new_encrypted_dek']
        instance.save(update_fields=['key_hash', 'encrypted_dek'])
        return instance
