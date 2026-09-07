from django.core.management.base import BaseCommand

from apps.solicitacoes.services.pesquisas import enviar_pesquisas_pendentes


class Command(BaseCommand):
    help = "Envia as pesquisas de avaliação pendentes."

    def handle(self, *args, **kwargs):
        total = enviar_pesquisas_pendentes()
        self.stdout.write(self.style.SUCCESS(f"Pesquisas enviadas: {total}"))
