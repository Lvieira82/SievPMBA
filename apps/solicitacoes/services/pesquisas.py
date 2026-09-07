from datetime import datetime, timedelta

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.core import signing
from django.template.loader import render_to_string
from django.utils import timezone

from apps.solicitacoes.models import HistoricoSolicitacao, Solicitacao


MARCADOR_PESQUISA = "PESQUISA DE SATISFAÇÃO ENVIADA"


def gerar_token_pesquisa(solicitacao):
    return signing.dumps({"protocolo": solicitacao.protocolo}, salt="sievpm-pesquisa")


def enviar_pesquisas_pendentes():
    """Envia a pesquisa 6 horas após o término do evento aprovado."""
    agora = timezone.now()
    enviados = 0

    solicitacoes = Solicitacao.objects.filter(
        status="APROVADA",
    ).select_related("unidade")

    for solicitacao in solicitacoes:
        if not solicitacao.email:
            continue

        if HistoricoSolicitacao.objects.filter(
            solicitacao=solicitacao,
            acao=MARCADOR_PESQUISA,
        ).exists():
            continue

        inicio = datetime.combine(solicitacao.data_evento, solicitacao.hora_inicio)
        fim = datetime.combine(solicitacao.data_evento, solicitacao.hora_fim)
        if fim <= inicio:
            fim += timedelta(days=1)

        momento_envio = timezone.make_aware(
            fim + timedelta(hours=6),
            timezone.get_current_timezone(),
        )
        if agora < momento_envio:
            continue

        token = gerar_token_pesquisa(solicitacao)
        link = f"{settings.SITE_URL.rstrip('/')}/pesquisa/{token}/"

        mensagem = f"""Olá, {solicitacao.solicitante}!

Esperamos que seu evento tenha ocorrido da melhor forma possível.

PROTOCOLO: {solicitacao.protocolo}
EVENTO: {solicitacao.nome_evento}
DATA: {solicitacao.data_evento.strftime('%d/%m/%Y')}

Sua opinião é muito importante para o aprimoramento do atendimento do SiEvPM.

Acesse o link abaixo para responder à Pesquisa de Avaliação:
{link}

PMBA - Uma força a serviço do cidadão.
"""

        html = render_to_string(
            "emails/pesquisa_satisfacao.html",
            {
                "nome_solicitante": solicitacao.solicitante,
                "link_pesquisa": link,
                "ano": agora.year,
            },
        )

        email = EmailMultiAlternatives(
            subject="Pesquisa de Avaliação - SiEvPM",
            body=mensagem,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[solicitacao.email],
        )
        email.attach_alternative(html, "text/html")
        email.send(fail_silently=False)

        HistoricoSolicitacao.objects.create(
            solicitacao=solicitacao,
            acao=MARCADOR_PESQUISA,
            observacao=f"Pesquisa enviada para {solicitacao.email}.",
        )
        enviados += 1

    return enviados
