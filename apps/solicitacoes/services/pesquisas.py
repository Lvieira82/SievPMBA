from datetime import datetime, timedelta
import secrets
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.conf import settings
from django.utils import timezone
from apps.solicitacoes.models import Solicitacao


def enviar_pesquisas_pendentes():

    print("=== ENVIO DE PESQUISAS ===")

    agora = timezone.now()
    enviados = 0

    solicitacoes = Solicitacao.objects.filter(
        status="APROVADO",
        pesquisa_enviada=False
    )

    for s in solicitacoes:

        try:

            if not s.pesquisa_token:
                s.pesquisa_token = secrets.token_urlsafe(32)

            inicio = datetime.combine(
                s.data_evento,
                s.hora_inicio
            )

            fim = datetime.combine(
                s.data_evento,
                s.hora_fim
            )

            if fim <= inicio:
                fim += timedelta(days=1)

            momento_envio = timezone.make_aware(
                fim + timedelta(hours=6),
                timezone.get_current_timezone()
            )

            if agora < momento_envio:
                continue

            print(f"Enviando pesquisa para {s.email}")

            link = (
                f"https://siev95.com.br/pesquisa/"
                f"{s.pesquisa_token}/"
            )

            mensagem = f"""
            Olá {s.solicitante},

            Esperamos que seu evento tenha ocorrido da melhor forma possível.

            Sua opinião é muito importante para nós.

            Avalie nosso atendimento acessando:

            {link}

            Muito obrigado.

            95ª CIPM
            Polícia Militar da Bahia
            """

            html = render_to_string(
                "emails/pesquisa_satisfacao.html",
                {
                    "nome_solicitante": s.solicitante,
                    "link_pesquisa": link,
                    "ano": timezone.now().year,
                }
            )

            email = EmailMultiAlternatives(
                subject="Pesquisa de Satisfação - SiEv",
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

            print(f"Pesquisa enviada para {s.email}")

        except Exception as erro:
            print(erro)

    print(f"Total de pesquisas enviadas: {enviados}")

    return enviados
