from django.apps import AppConfig


class SolicitacoesConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.solicitacoes"

    def ready(self):
        from django.conf import settings

        # O agendamento é executado exclusivamente pelo Render Cron Job.
        # Nao iniciar APScheduler nos workers web: isso pode duplicar envios.

        # Registra os sinais de criação de usuários institucionais.
        from . import signals  # noqa: F401

        # Registra os modelos auxiliares de apoio operacional.
        from . import models_apoio  # noqa: F401

        # O monitoramento é anexado aqui para evitar alterar o settings.py.
        middleware = "apps.solicitacoes.middleware.MonitoramentoAcessosMiddleware"
        if middleware not in settings.MIDDLEWARE:
            settings.MIDDLEWARE.append(middleware)
