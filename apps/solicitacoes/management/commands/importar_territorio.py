import csv
import unicodedata

from django.core.management.base import BaseCommand

from apps.solicitacoes.models import (
    COPPM,
    CPR,
    Unidade,
    Municipio,
    Bairro,
    AreaResponsabilidade,
)


CSV_PATH = (
    "municipios_417_responsabilidade_SIEVPM.csv"
)


def normalizar(texto):

    if not texto:
        return ""

    texto = str(texto).strip().upper()

    texto = unicodedata.normalize(
        "NFKD",
        texto
    )

    return "".join(
        c
        for c in texto
        if not unicodedata.combining(c)
    )


class Command(BaseCommand):

    help = (
        "Importa a estrutura Município → Centro → "
        "Área de Responsabilidade → Unidade."
    )

    def handle(self, *args, **options):

        copppm, _ = COPPM.objects.get_or_create(
            sigla="COPPM",
            defaults={
                "nome": (
                    "Comando de Operações "
                    "Policiais Militares"
                ),
                "ativo": True,
            }
        )

        criados_cpr = 0
        criados_unidades = 0
        centros_criados = 0
        areas_criadas = 0
        municipios_direcionados = 0
        municipios_pendentes = 0

        self.stdout.write(
            self.style.WARNING(
                "Iniciando importação territorial..."
            )
        )

        with open(
            CSV_PATH,
            "r",
            encoding="utf-8-sig",
            newline=""
        ) as arquivo:

            leitor = csv.DictReader(
                arquivo,
                delimiter=";"
            )

            for linha in leitor:

                municipio_nome = (
                    linha.get("municipio") or ""
                ).strip()

                cpr_sigla = (
                    linha.get("cpr") or ""
                ).strip()

                unidade_nome = (
                    linha.get("unidade") or ""
                ).strip()

                status = (
                    linha.get("status") or ""
                ).strip()

                if not municipio_nome:
                    continue

                # ==================================================
                # LOCALIZA MUNICÍPIO
                # ==================================================

                municipio = Municipio.objects.filter(
                    nome__iexact=municipio_nome
                ).first()

                if not municipio:

                    self.stdout.write(
                        self.style.WARNING(
                            f"Município não encontrado: "
                            f"{municipio_nome}"
                        )
                    )

                    continue

                # ==================================================
                # MUNICÍPIO COM MAIS DE UMA UNIDADE
                # ==================================================

                if status != "MAPEADO":

                    municipios_pendentes += 1

                    self.stdout.write(
                        self.style.WARNING(
                            f"Pendente por bairro: "
                            f"{municipio_nome}"
                        )
                    )

                    continue

                if not cpr_sigla or not unidade_nome:

                    municipios_pendentes += 1

                    continue

                # ==================================================
                # CPR
                # ==================================================

                cpr, criado = CPR.objects.get_or_create(

                    sigla=cpr_sigla,

                    defaults={
                        "nome": cpr_sigla,
                        "coppm": copppm,
                        "ativo": True,
                    }
                )

                if criado:
                    criados_cpr += 1

                # ==================================================
                # UNIDADE
                # ==================================================

                unidade = Unidade.objects.filter(
                    cpr=cpr,
                    sigla=unidade_nome
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

                # ==================================================
                # MUNICÍPIO → UNIDADE PADRÃO
                # ==================================================

                if (
                    municipio.unidade_responsavel_id
                    != unidade.id
                ):

                    municipio.unidade_responsavel = (
                        unidade
                    )

                    municipio.save(
                        update_fields=[
                            "unidade_responsavel"
                        ]
                    )

                municipios_direcionados += 1

                # ==================================================
                # BAIRRO PADRÃO "CENTRO"
                # ==================================================

                bairro, criado = Bairro.objects.get_or_create(

                    municipio=municipio,

                    nome="Centro",

                    defaults={
                        "ativo": True
                    }
                )

                if criado:
                    centros_criados += 1

                # ==================================================
                # ÁREA DE RESPONSABILIDADE
                # ==================================================

                _, criado = (
                    AreaResponsabilidade.objects.get_or_create(

                        bairro=bairro,

                        unidade=unidade,

                        defaults={
                            "ativo": True
                        }
                    )
                )

                if criado:
                    areas_criadas += 1

        # ==========================================================
        # RESULTADO
        # ==========================================================

        self.stdout.write("")

        self.stdout.write(
            self.style.SUCCESS(
                "=========================================="
            )
        )

        self.stdout.write(
            self.style.SUCCESS(
                "IMPORTAÇÃO TERRITORIAL CONCLUÍDA"
            )
        )

        self.stdout.write(
            f"CPRs criados: {criados_cpr}"
        )

        self.stdout.write(
            f"Unidades criadas: {criados_unidades}"
        )

        self.stdout.write(
            f"Municípios direcionados: "
            f"{municipios_direcionados}"
        )

        self.stdout.write(
            f"Centros criados: {centros_criados}"
        )

        self.stdout.write(
            f"Áreas de responsabilidade criadas: "
            f"{areas_criadas}"
        )

        self.stdout.write(
            f"Municípios aguardando bairros: "
            f"{municipios_pendentes}"
        )

        self.stdout.write(
            self.style.SUCCESS(
                "=========================================="
            )
        )