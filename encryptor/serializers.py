from rest_framework import serializers
from .models import FileMetadata, Category
from rest_framework.validators import UniqueTogetherValidator

class NestedCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ['id', 'category']

class CategorySerializer(serializers.ModelSerializer):
    owner = serializers.HiddenField(default= serializers.CurrentUserDefault())
    class Meta:
        model = Category
        fields=['id','category', 'owner']
        validators = [
            UniqueTogetherValidator(
                queryset= Category.objects.all(),
                fields = ['category', 'owner'],
                message="A category with this name already exists for this user."
            )
        ]

class FileMetadataSerializer(serializers.ModelSerializer):
    owner = serializers.PrimaryKeyRelatedField(read_only=True)
    
    category = serializers.PrimaryKeyRelatedField(
        queryset=Category.objects.none(),
        label='Category ID'
    )

    class Meta:
        model = FileMetadata
        fields = ['id', 'file_name', 'file_type', 'file_size', 'created_at', 'updated_at', 'category', 'owner']
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        request = self.context.get('request')
        
        if request and not request.user.is_anonymous:
            self.fields['category'].queryset = Category.objects.filter(owner=request.user)
            
    def to_representation(self, instance):
        representation = super().to_representation(instance)
        
        category_instance = instance.category
        if category_instance:
            representation['category'] = NestedCategorySerializer(category_instance).data
        else:
            representation['category'] = None
            
        return representation

class CategorySummarySerializer(serializers.ModelSerializer):
    files_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = Category
        fields = ['id', 'category', 'files_count']