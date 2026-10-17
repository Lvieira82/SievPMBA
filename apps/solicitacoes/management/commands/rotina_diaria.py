from django.core.management.base import BaseCommand

from apps.solicitacoes.services.rotina import executar_rotina_diaria


class Command(BaseCommand):
    help = "Executa uma vez a rotina diária: pesquisas pendentes e limpeza de documentos."

    def handle(self, *args, **options):
        self.stdout.write("Iniciando rotina diária do SiEvPM...")
        executar_rotina_diaria()
        self.stdout.write(self.style.SUCCESS("Rotina diária concluída."))
