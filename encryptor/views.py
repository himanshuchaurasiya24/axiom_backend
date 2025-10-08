from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from .models import FileMetadata, FileContent
from .serializers import FileMetadataSerializer, FileContentSerializer

class FileViewSet(viewsets.ModelViewSet):
    serializer_class = FileMetadataSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return FileMetadata.objects.filter(owner=self.request.user)

    def perform_create(self, serializer):
        serializer.save(owner=self.request.user)
    
    @action(detail=True, methods=['get', 'put'], url_path='content')
    def content(self, request, pk=None):
        metadata = self.get_object()

        if request.method == 'GET':
            try:
                serializer = FileContentSerializer(metadata.content)
                return Response(serializer.data)
            except FileContent.DoesNotExist:
                return Response({"error": "Content not found."}, status=status.HTTP_404_NOT_FOUND)

        elif request.method == 'PUT':
            serializer = FileContentSerializer(data=request.data)
            if serializer.is_valid():
                FileContent.objects.update_or_create(
                    metadata=metadata,
                    defaults={'encrypted_blob': serializer.validated_data['encrypted_blob']}
                )
                return Response(status=status.HTTP_204_NO_CONTENT)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
