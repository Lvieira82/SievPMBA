from datetime import datetime, timedelta

from django.contrib.auth import logout
from django.contrib.sessions.models import Session
from django.utils import timezone

from .models import LogSistema


class MonitoramentoAcessosMiddleware:
    """Registra acessos e encerra sessões autenticadas após 5 min sem atividade."""

    CAMINHOS_IGNORADOS = ("/static/", "/media/", "/favicon.ico")
    CHAVE_ACESSO = "siev_acesso_registrado"
    CHAVE_ATIVIDADE = "siev_ultima_atividade"
    INATIVIDADE_SEGUNDOS = 5 * 60

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        usuario = getattr(request.user, "is_authenticated", False) and request.user or None

        if usuario and not request.path.startswith(self.CAMINHOS_IGNORADOS):
            try:
                agora = timezone.now()
                ultima_atividade = self._ler_ultima_atividade(request)

                # Se passaram 5 minutos sem nenhuma requisição do usuário,
                # encerra a sessão. O próximo acesso exigirá login novamente.
                if ultima_atividade and (agora - ultima_atividade).total_seconds() >= self.INATIVIDADE_SEGUNDOS:
                    logout(request)
                    return self.get_response(request)

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

                # Sliding expiration: cada atividade renova a sessão por mais
                # 5 minutos. Assim, 5 minutos sem atividade encerram a sessão.
                request.session.set_expiry(self.INATIVIDADE_SEGUNDOS)
                request.session[self.CHAVE_ATIVIDADE] = agora.isoformat()
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
                    ultima = datetime.fromisoformat(atividade)
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
    def _ler_ultima_atividade(request):
        valor = request.session.get(MonitoramentoAcessosMiddleware.CHAVE_ATIVIDADE)
        if not valor:
            return None
        try:
            ultima = datetime.fromisoformat(valor)
            if timezone.is_naive(ultima):
                ultima = timezone.make_aware(ultima, timezone.get_current_timezone())
            return ultima
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _ip(request):
        encaminhado = request.META.get("HTTP_X_FORWARDED_FOR")
        if encaminhado:
            return encaminhado.split(",")[0].strip()
        return request.META.get("REMOTE_ADDR")
