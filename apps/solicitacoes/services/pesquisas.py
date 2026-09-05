from datetime import datetime, timedelta
import secrets

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils import timezone

from apps.solicitacoes.models import Solicitacao


def enviar_pesquisas_pendentes():
    """Envia, após o evento, o e-mail informando a OPO gerada e a pesquisa."""
    print("=== ENVIO DE PESQUISAS ===")

    agora = timezone.now()
    enviados = 0

    solicitacoes = Solicitacao.objects.filter(
        status="APROVADO",
        pesquisa_enviada=False,
    )

    for s in solicitacoes:
        try:
            if not s.email:
                print(f"Solicitação {s.protocolo} sem e-mail; pesquisa não enviada.")
                continue

            if not s.pesquisa_token:
                s.pesquisa_token = secrets.token_urlsafe(32)

            inicio = datetime.combine(s.data_evento, s.hora_inicio)
            fim = datetime.combine(s.data_evento, s.hora_fim)

            if fim <= inicio:
                fim += timedelta(days=1)

            momento_envio = timezone.make_aware(
                fim + timedelta(hours=6),
                timezone.get_current_timezone(),
            )

            if agora < momento_envio:
                continue

            print(f"Enviando pesquisa para {s.email}")

            link = f"{settings.SITE_URL}/pesquisa/{s.pesquisa_token}/"

            mensagem = f"""Olá, {s.solicitante}!

Seu evento foi realizado e sua Ordem de Policiamento (OPO) foi gerada pelo SiEv.

PROTOCOLO: {s.protocolo}
EVENTO: {s.nome_evento}
DATA: {s.data_evento.strftime('%d/%m/%Y')}

Agora gostaríamos de conhecer sua experiência com o atendimento.

Acesse o link abaixo para responder à Pesquisa de Satisfação:
{link}

Sua avaliação é muito importante para o aprimoramento do serviço.

PMBA - Uma força a serviço do cidadão.
"""

            html = render_to_string(
                "emails/pesquisa_satisfacao.html",
                {
                    "nome_solicitante": s.solicitante,
                    "link_pesquisa": link,
                    "ano": timezone.now().year,
                },
            )

            email = EmailMultiAlternatives(
                subject="OPO gerada - Pesquisa de Satisfação - SiEvPM",
                body=mensagem,
                from_email=settings.DEFAULT_FROM_EMAIL,
                to=[s.email],
            )
            email.attach_alternative(html, "text/html")
            email.send(fail_silently=False)

            s.pesquisa_enviada = True
            s.data_envio_pesquisa = agora
            s.save(update_fields=[
                "pesquisa_token",
                "pesquisa_enviada",
                "data_envio_pesquisa",
            ])

            enviados += 1
            print(f"Pesquisa/OPO enviada para {s.email}")

        except Exception as erro:
            # Não marcar como enviada quando o SMTP falhar. A rotina poderá
            # tentar novamente no próximo ciclo.
            print(f"ERRO AO ENVIAR PESQUISA/OPO ({s.protocolo}): {erro}")

    print(f"Total de pesquisas enviadas: {enviados}")
    return enviados
