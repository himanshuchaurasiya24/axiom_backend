from django.db.models.signals import post_delete
from django.dispatch import receiver
from .models import FileMetadata
import os
from django.conf import settings

@receiver(post_delete, sender=FileMetadata)
def delete_file_content(sender, instance, **kwargs):
    """
    Deletes the associated .txt file from the media directory
    when a FileMetadata object is deleted.
    """
    try:
        filepath = os.path.join(settings.MEDIA_ROOT, 'file_content', f"{instance.id}.txt")
        if os.path.exists(filepath):
            os.remove(filepath)
    except Exception as e:
        # Log this error in a real application
        print(f"Error deleting file for {instance.id}: {str(e)}")