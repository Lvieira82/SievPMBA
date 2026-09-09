from datetime import timedelta

from django.contrib.sessions.models import Session
from django.utils import timezone

from .models import LogSistema


class MonitoramentoAcessosMiddleware:
    """Registra uma entrada por sessão e mantém a atividade da sessão."""

    CAMINHOS_IGNORADOS = ("/static/", "/media/", "/favicon.ico")
    CHAVE_ACESSO = "siev_acesso_registrado"
    CHAVE_ATIVIDADE = "siev_ultima_atividade"

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        usuario = getattr(request.user, "is_authenticated", False) and request.user or None

        if usuario and not request.path.startswith(self.CAMINHOS_IGNORADOS):
            try:
                # Refreshes and page navigation within the same session do not
                # create another historical access record.
                if not request.session.get(self.CHAVE_ACESSO):
                    LogSistema.objects.create(
                        usuario=usuario,
                        acao="ACESSO_SESSAO",
                        detalhes="Início de sessão",
                        ip=self._ip(request),
                    )
                    request.session[self.CHAVE_ACESSO] = True

                # Keep the last activity so simultaneous access can be measured
                # without turning every refresh into a new historical access.
                request.session[self.CHAVE_ATIVIDADE] = timezone.now().isoformat()
                request.session.modified = True
            except Exception:
                # Monitoring must never prevent the system from working.
                pass

        return self.get_response(request)

    @classmethod
    def sessoes_ativas(cls, minutos=5):
        """Return user IDs with recent activity in authenticated sessions."""
        limite = timezone.now() - timedelta(minutes=minutos)
        ativos = set()
        try:
            agora = timezone.now()
            for sessao in Session.objects.filter(expire_date__gte=agora):
                dados = sessao.get_decoded()
                user_id = dados.get("_auth_user_id")
                atividade = dados.get(cls.CHAVE_ATIVIDADE)
                if not user_id or not atividade:
                    continue
                try:
                    ultima = timezone.datetime.fromisoformat(atividade)
                    if timezone.is_naive(ultima):
                        ultima = timezone.make_aware(ultima, timezone.get_current_timezone())
                    if ultima >= limite:
                        ativos.add(str(user_id))
                except (TypeError, ValueError):
                    continue
        except Exception:
            pass
        return ativos

    @staticmethod
    def _ip(request):
        encaminhado = request.META.get("HTTP_X_FORWARDED_FOR")
        if encaminhado:
            return encaminhado.split(",")[0].strip()
        return request.META.get("REMOTE_ADDR")
