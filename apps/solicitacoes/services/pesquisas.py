from datetime import datetime, timedelta

from django.conf import settings
from django.core import signing
from django.core.mail import EmailMultiAlternatives
from django.db import transaction
from django.template.loader import render_to_string
from django.utils import timezone

from apps.solicitacoes.models import HistoricoSolicitacao, Solicitacao


MARCADOR_PESQUISA = "PESQUISA DE SATISFAÇÃO ENVIADA"


def gerar_token_pesquisa(solicitacao):
    return signing.dumps({"protocolo": solicitacao.protocolo}, salt="sievpm-pesquisa")


def enviar_pesquisas_pendentes():
    """Envia uma única pesquisa por solicitação, 6 horas após o fim do evento."""
    agora = timezone.now()
    enviados = 0

    ids = Solicitacao.objects.filter(status="APROVADA").values_list("pk", flat=True)

    for solicitacao_id in ids.iterator():
        # O bloqueio da solicitação evita que dois processos enviem a mesma pesquisa.
        # O envio e o registro ficam na mesma transação para que outro processo,
        # após aguardar o bloqueio, encontre o marcador e não envie novamente.
        with transaction.atomic():
            try:
                solicitacao = (
                    Solicitacao.objects.select_for_update()
                    .select_related("unidade")
                    .get(pk=solicitacao_id, status="APROVADA")
                )
            except Solicitacao.DoesNotExist:
                continue

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

            mensagem = f"""Olá!

Esperamos que sua experiência com o Sistema Integrado de Eventos tenha ocorrido da melhor forma possível.

Sua opinião é muito importante para o aprimoramento do Sistema e do atendimento prestado pela Polícia Militar da Bahia.

Esta pesquisa é totalmente anônima, você não será identificado.

Acesse o link abaixo para responder à Pesquisa de Avaliação:
{link}

PMBA - Uma força a serviço do cidadão.
"""

            html = render_to_string(
                "emails/pesquisa_satisfacao.html",
                {
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
