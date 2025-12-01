from rest_framework import serializers
from .models import FileMetadata, Category


class FileMetadataSerializer(serializers.ModelSerializer):
    owner= serializers.PrimaryKeyRelatedField(read_only = True )
    category= serializers.PrimaryKeyRelatedField(queryset= Category.objects.none())
    class Meta:
        model = FileMetadata
        fields = ['id', 'file_name', 'file_type', 'file_size', 'created_at', 'updated_at', 'category', 'owner']
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        request = self.context.get('request')
        if request and not request.user.is_anonymous:
            self.fields['category'].queryset= Category.objects.filter(owner= request.user)
    def validate_category(self, value):
        request = self.context.get('request')
        if request and not request.user.is_superuser:
            if value.owner!=request.user:
                raise serializers.ValidationError("You can only add categories you own.")
        return value

class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields=['id','category']
        