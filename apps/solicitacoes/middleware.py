from datetime import datetime, timedelta

from django.contrib.auth import logout
from django.contrib.sessions.models import Session
from django.utils import timezone

from .models import LogSistema, Solicitacao


class MonitoramentoAcessosMiddleware:
    """Registra acessos, atividade pública e o tempo do preenchimento externo."""

    CAMINHOS_IGNORADOS = ("/static/", "/media/", "/favicon.ico")
    CHAVE_ACESSO = "siev_acesso_registrado"
    CHAVE_ATIVIDADE = "siev_ultima_atividade"
    CHAVE_PUBLICO = "siev_acesso_publico"
    CHAVE_ATIVIDADE_PUBLICA = "siev_ultima_atividade_publica"
    CHAVE_ACEITE_TERMOS = "siev_termos_aceitos_em"
    INATIVIDADE_SEGUNDOS = 5 * 60

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        usuario = getattr(request.user, "is_authenticated", False) and request.user or None
        inicio_requisicao = timezone.now()

        if not request.path.startswith(self.CAMINHOS_IGNORADOS):
            try:
                agora = timezone.now()

                if request.path == "/nova/" and request.method == "GET":
                    aceite = request.GET.get("aceite")
                    if aceite == "1":
                        request.session[self.CHAVE_ACEITE_TERMOS] = agora.isoformat()
                        request.session.modified = True
                    elif aceite == "0":
                        request.session.pop(self.CHAVE_ACEITE_TERMOS, None)
                        request.session.modified = True

                if usuario:
                    ultima_atividade = self._ler_ultima_atividade(request)
                    if ultima_atividade and (agora - ultima_atividade).total_seconds() >= self.INATIVIDADE_SEGUNDOS:
                        logout(request)
                        return self.get_response(request)
                    if not request.session.get(self.CHAVE_ACESSO):
                        LogSistema.objects.create(usuario=usuario, acao="ACESSO_SESSAO", detalhes="Início de sessão", ip=self._ip(request))
                        request.session[self.CHAVE_ACESSO] = True
                    request.session.set_expiry(self.INATIVIDADE_SEGUNDOS)
                    request.session[self.CHAVE_ATIVIDADE] = agora.isoformat()
                    request.session.modified = True
                else:
                    request.session[self.CHAVE_PUBLICO] = True
                    request.session[self.CHAVE_ATIVIDADE_PUBLICA] = agora.isoformat()
                    request.session.modified = True
            except Exception:
                pass

        response = self.get_response(request)

        # Mede somente quando uma solicitação externa foi realmente criada.
        # O mesmo aceite pode gerar vários protocolos no fluxo de múltiplas datas.
        if request.method == "POST" and request.path in ("/nova/", "/confirmar-datas/"):
            try:
                valor = request.session.get(self.CHAVE_ACEITE_TERMOS)
                if valor and response.status_code < 400:
                    aceito_em = datetime.fromisoformat(valor)
                    if timezone.is_naive(aceito_em):
                        aceito_em = timezone.make_aware(aceito_em, timezone.get_current_timezone())
                    segundos = max(0.0, (timezone.now() - aceito_em).total_seconds())
                    if segundos <= 24 * 60 * 60:
                        solicitacoes = Solicitacao.objects.filter(origem="EXTERNA", criado_em__gte=inicio_requisicao).order_by("-criado_em")
                        for solicitacao in solicitacoes:
                            if not LogSistema.objects.filter(solicitacao=solicitacao, acao="TEMPO_ACEITE_TERMO_ATE_ENVIO").exists():
                                LogSistema.objects.create(solicitacao=solicitacao, acao="TEMPO_ACEITE_TERMO_ATE_ENVIO", detalhes=f"segundos={segundos:.3f}", ip=self._ip(request))
                        if solicitacoes:
                            request.session.pop(self.CHAVE_ACEITE_TERMOS, None)
                            request.session.modified = True
            except Exception:
                pass

        return response

    @classmethod
    def sessoes_ativas(cls, minutos=5):
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
                    if ultima >= limite: ativos.add(str(user_id))
                except (TypeError, ValueError):
                    continue
        except Exception:
            pass
        return ativos

    @classmethod
    def acessos_publicos_ativos(cls, minutos=5):
        limite = timezone.now() - timedelta(minutes=minutos)
        total = 0
        try:
            agora = timezone.now()
            for sessao in Session.objects.filter(expire_date__gte=agora):
                dados = sessao.get_decoded()
                if dados.get("_auth_user_id") or not dados.get(cls.CHAVE_PUBLICO): continue
                atividade = dados.get(cls.CHAVE_ATIVIDADE_PUBLICA)
                if not atividade: continue
                try:
                    ultima = datetime.fromisoformat(atividade)
                    if timezone.is_naive(ultima): ultima = timezone.make_aware(ultima, timezone.get_current_timezone())
                    if ultima >= limite: total += 1
                except (TypeError, ValueError): continue
        except Exception:
            pass
        return total

    @staticmethod
    def _ler_ultima_atividade(request):
        valor = request.session.get(MonitoramentoAcessosMiddleware.CHAVE_ATIVIDADE)
        if not valor: return None
        try:
            ultima = datetime.fromisoformat(valor)
            if timezone.is_naive(ultima): ultima = timezone.make_aware(ultima, timezone.get_current_timezone())
            return ultima
        except (TypeError, ValueError): return None

    @staticmethod
    def _ip(request):
        encaminhado = request.META.get("HTTP_X_FORWARDED_FOR")
        if encaminhado: return encaminhado.split(",")[0].strip()
        return request.META.get("REMOTE_ADDR")
