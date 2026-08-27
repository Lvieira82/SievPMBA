from django.core.management.base import BaseCommand

from apps.solicitacoes.models import COPPM, CPR, Unidade


UNIDADES_CPR_L = [
    ("25º BPM/FEIRA DE SANTANA", "BPM"),
    ("64ª CIPM/FEIRA DE SANTANA", "CIPM"),
    ("65ª CIPM/FEIRA DE SANTANA", "CIPM"),
    ("66ª CIPM/CONCEIÇÃO DO JACUÍPE", "CIPM"),
    ("67ª CIPM/FEIRA DE SANTANA", "CIPM"),
    ("57ª CIPM/SANTO ESTEVÃO", "CIPM"),
    ("97ª CIPM/IRARÁ", "CIPM"),
]


class Command(BaseCommand):
    help = "Garante as unidades do CPR-L, incluindo as 64ª e 65ª CIPM."

    def handle(self, *args, **options):
        coppm = COPPM.objects.filter(sigla="COPPM", ativo=True).first()
        if not coppm:
            self.stdout.write(self.style.ERROR("COPPM ativo não encontrado."))
            return

        cpr = CPR.objects.filter(sigla="CPR-L", coppm=coppm).first()
        if not cpr:
            self.stdout.write(self.style.ERROR("CPR-L não encontrado."))
            return

        criadas = 0
        reativadas = 0

        for sigla, tipo in UNIDADES_CPR_L:
            unidade = Unidade.objects.filter(cpr=cpr, sigla=sigla).first()

            if unidade:
                if not unidade.ativo:
                    unidade.ativo = True
                    unidade.save(update_fields=["ativo"])
                    reativadas += 1
                continue

            Unidade.objects.create(
                cpr=cpr,
                nome=sigla,
                sigla=sigla,
                tipo=tipo,
                ativo=True,
            )
            criadas += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"CPR-L atualizado: {criadas} unidade(s) criada(s), "
                f"{reativadas} reativada(s)."
            )
        )
        self.stdout.write("Unidades do CPR-L:")
        for unidade in Unidade.objects.filter(cpr=cpr, ativo=True).order_by("sigla"):
            self.stdout.write(f" - {unidade.sigla}")
