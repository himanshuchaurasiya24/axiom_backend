import django_filters
from datetime import timedelta
from django.utils.timezone import now
from .models import FileMetadata
class FileFilter(django_filters.FilterSet):
    category = django_filters.CharFilter(field_name = 'category__category', lookup_expr = 'exact')
    file_name = django_filters.CharFilter(field_name='file_name',lookup_expr = 'icontains')
    file_type = django_filters.CharFilter(field_name='file_type',lookup_expr = 'icontains')
    created_at = django_filters.DateFilter(field_name='created_at__date',lookup_expr = 'exact')