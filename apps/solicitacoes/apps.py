from django.apps import AppConfig


class SolicitacoesConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.solicitacoes"

    def ready(self):
        from . import models_acesso  # noqa: F401
