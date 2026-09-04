from django.apps import AppConfig


class SolicitacoesConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.solicitacoes"

    def ready(self):

        from django.conf import settings

        if settings.DEBUG:
            return

        from .scheduler import iniciar_scheduler

        iniciar_scheduler()
