from django.apps import AppConfig


class SolicitacoesConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.solicitacoes"

    def ready(self):
        from django.conf import settings

        if not settings.DEBUG:
            from .scheduler import iniciar_scheduler
            iniciar_scheduler()

        # Registra os sinais de criação de usuários institucionais.
        from . import signals  # noqa: F401

        # Registra os modelos auxiliares de apoio operacional.
        from . import models_apoio  # noqa: F401
