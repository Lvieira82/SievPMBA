import csv
import unicodedata

from django.core.management.base import BaseCommand
from django.db import transaction

from apps.solicitacoes.models import (
    COPPM,
    CPR,
    Unidade,
    Municipio,
    Bairro,
    AreaResponsabilidade,
)


CSV_PATH = "municipios_417_responsabilidade_SIEVPM.csv"


def normalizar(texto):
    if not texto:
        return ""

    texto = str(texto).strip().upper()
    texto = unicodedata.normalize("NFKD", texto)

    return "".join(
        c for c in texto if not unicodedata.combining(c)
    )


class Command(BaseCommand):
    help = (
        "Importa a estrutura Município → Área de Responsabilidade → Unidade, "
        "mantendo cada bairro/distrito ligado a uma única unidade."
    )

    @transaction.atomic
    def handle(self, *args, **options):
        coppm, _ = COPPM.objects.get_or_create(
            sigla="COPPM",
            defaults={
                "nome": "Comando de Operações Policiais Militares",
                "ativo": True,
            },
        )

        criados_cpr = 0
        criados_unidades = 0
        bairros_atualizados = 0
        areas_atualizadas = 0
        municipios_direcionados = 0
        municipios_pendentes = 0

        self.stdout.write(
            self.style.WARNING("Iniciando importação territorial...")
        )

        with open(
            CSV_PATH,
            "r",
            encoding="utf-8-sig",
            newline="",
        ) as arquivo:
            leitor = csv.DictReader(arquivo, delimiter=";")

            for linha in leitor:
                municipio_nome = (linha.get("municipio") or "").strip()
                cpr_sigla = (linha.get("cpr") or "").strip()
                unidade_nome = (linha.get("unidade") or "").strip()
                status = (linha.get("status") or "").strip()

                if not municipio_nome:
                    continue

                municipio = Municipio.objects.filter(
                    nome__iexact=municipio_nome
                ).first()

                if not municipio:
                    self.stdout.write(
                        self.style.WARNING(
                            f"Município não encontrado: {municipio_nome}"
                        )
                    )
                    continue

                if status != "MAPEADO":
                    municipios_pendentes += 1
                    self.stdout.write(
                        self.style.WARNING(
                            f"Pendente por bairro: {municipio_nome}"
                        )
                    )
                    continue

                if not cpr_sigla or not unidade_nome:
                    municipios_pendentes += 1
                    continue

                cpr, criado = CPR.objects.get_or_create(
                    sigla=cpr_sigla,
                    defaults={
                        "nome": cpr_sigla,
                        "coppm": coppm,
                        "ativo": True,
                    },
                )
                if criado:
                    criados_cpr += 1

                unidade = Unidade.objects.filter(
                    cpr=cpr,
                    sigla__iexact=unidade_nome,
                ).first()

                if not unidade:
                    unidade = Unidade.objects.create(
                        cpr=cpr,
                        nome=unidade_nome,
                        sigla=unidade_nome,
                        tipo=(
                            "BPM"
                            if "BPM" in unidade_nome.upper()
                            else "CIPM"
                        ),
                        ativo=True,
                    )
                    criados_unidades += 1

                if municipio.unidade_responsavel_id != unidade.id:
                    municipio.unidade_responsavel = unidade
                    municipio.save(update_fields=["unidade_responsavel"])

                municipios_direcionados += 1

                bairro, criado = Bairro.objects.get_or_create(
                    municipio=municipio,
                    nome="Centro",
                    defaults={"ativo": True},
                )
                if criado:
                    bairros_atualizados += 1

                area = AreaResponsabilidade.objects.filter(
                    bairro=bairro
                ).order_by("id").first()

                if area:
                    if area.unidade_id != unidade.id or not area.ativo:
                        area.unidade = unidade
                        area.ativo = True
                        area.save(update_fields=["unidade", "ativo"])
                        areas_atualizadas += 1

                    AreaResponsabilidade.objects.filter(
                        bairro=bairro
                    ).exclude(pk=area.pk).delete()
                else:
                    AreaResponsabilidade.objects.create(
                        bairro=bairro,
                        unidade=unidade,
                        ativo=True,
                    )
                    areas_atualizadas += 1

        self.stdout.write("")
        self.stdout.write(
            self.style.SUCCESS("==========================================")
        )
        self.stdout.write(
            self.style.SUCCESS("IMPORTAÇÃO TERRITORIAL CONCLUÍDA")
        )
        self.stdout.write(f"CPRs criados: {criados_cpr}")
        self.stdout.write(f"Unidades criadas: {criados_unidades}")
        self.stdout.write(
            f"Municípios direcionados: {municipios_direcionados}"
        )
        self.stdout.write(f"Bairros criados: {bairros_atualizados}")
        self.stdout.write(f"Áreas atualizadas: {areas_atualizadas}")
        self.stdout.write(
            f"Municípios aguardando bairros: {municipios_pendentes}"
        )
        self.stdout.write(
            self.style.SUCCESS("==========================================")
        )
