from django.apps import AppConfig


class NewsAppConfig(AppConfig):
    """
    Django AppConfig for the news_app application.
    """
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'news_app'

    def ready(self):
        from . import signals
        print("Signals are ready")
