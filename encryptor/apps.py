from django.apps import AppConfig

class EncryptorConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'encryptor'

    def ready(self):
        # Import signals when the app is ready
        import encryptor.signals
