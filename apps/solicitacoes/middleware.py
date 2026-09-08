from django.utils import timezone

from .models import LogSistema


class MonitoramentoAcessosMiddleware:
    """Registra acessos HTTP para as métricas do Dashboard do sistema."""

    CAMINHOS_IGNORADOS = ("/static/", "/media/", "/favicon.ico")

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)

        if not request.path.startswith(self.CAMINHOS_IGNORADOS):
            try:
                ip = self._ip(request)
                usuario = request.user if getattr(request.user, "is_authenticated", False) else None
                LogSistema.objects.create(
                    usuario=usuario,
                    acao="ACESSO_SISTEMA",
                    detalhes=f"{request.method} {request.path}",
                    ip=ip,
                )
            except Exception:
                # O monitoramento jamais pode impedir o funcionamento do sistema.
                pass

        return response

    @staticmethod
    def _ip(request):
        encaminhado = request.META.get("HTTP_X_FORWARDED_FOR")
        if encaminhado:
            return encaminhado.split(",")[0].strip()
        return request.META.get("REMOTE_ADDR")
