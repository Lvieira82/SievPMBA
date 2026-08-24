from datetime import timedelta
from django.core.management.base import BaseCommand
from django.core.mail import send_mail
from django.conf import settings
from django.utils import timezone
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from apps.solicitacoes.models import Solicitacao



class Command(BaseCommand):
    help = "Envia pesquisas de satisfação"

    def handle(self, *args, **kwargs):
        self.stdout.write("INICIOU O COMANDO")
        limite = timezone.now() - timedelta(hours=24)

        solicitacoes = Solicitacao.objects.all()
        

        for s in solicitacoes:
            self.stdout.write(f"Enviando para: {s.email}")
            link = (
                f"https://siev95.com.br/"
                f"pesquisa/{s.pesquisa_token}/"
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

            try:

                send_mail(
                    "Pesquisa de Satisfação - SiEv",
                    mensagem,
                    settings.DEFAULT_FROM_EMAIL,
                    [s.email],
                    fail_silently=False
                )

                s.pesquisa_enviada = True
                s.data_envio_pesquisa = timezone.now()
                s.save()

                self.stdout.write(
                    self.style.SUCCESS(
                        f"Pesquisa enviada para {s.email}"
                    )
                )

            except Exception as erro:

                self.stdout.write(
                    self.style.ERROR(str(erro))
                )




class Command(BaseCommand):
    help = "Envia a pesquisa de satisfação para todas as solicitações aprovadas."

    def handle(self, *args, **kwargs):

        solicitacoes = Solicitacao.objects.filter(
            status="APROVADO",
            pesquisa_enviada=False,
            data_evento__lte=timezone.localdate()
        )

        total = 0

        for s in solicitacoes:

            if not s.email:
                continue

            import secrets

            if not s.pesquisa_token:
                s.pesquisa_token = secrets.token_urlsafe(32)
                s.save(update_fields=["pesquisa_token"])

            link = (
                f"https://siev95.com.br/pesquisa/"
                f"{s.pesquisa_token}/"
            )

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
                body="Sua opinião é muito importante para nós.",
                from_email=settings.DEFAULT_FROM_EMAIL,
                to=[s.email],
            )

            email.attach_alternative(html, "text/html")
            email.send()

            s.pesquisa_enviada = True
            s.data_envio_pesquisa = timezone.now()
            s.save()

            total += 1

            self.stdout.write(
                self.style.SUCCESS(
                    f"✔ Pesquisa enviada para {s.email}"
                )
            )

        self.stdout.write(
            self.style.SUCCESS(
                f"\nTotal de pesquisas enviadas: {total}"
            )
        )