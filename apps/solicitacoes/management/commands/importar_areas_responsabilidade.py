import csv

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.solicitacoes.models import (
    AreaResponsabilidade,
    Bairro,
    Municipio,
    Unidade,
)


class Command(BaseCommand):
    help = (
        "Importa áreas de responsabilidade de um CSV com as colunas "
        "municipio,bairro,unidade."
    )

    @transaction.atomic
    def handle(self, *args, **options):
        # O caminho é lido de stdin para manter o comando simples e seguro.
        self.stdout.write("Cole o caminho completo do CSV e pressione ENTER:")
        caminho = input().strip().strip('"')

        if not caminho:
            raise CommandError("Informe o caminho do arquivo CSV.")

        try:
            arquivo = open(caminho, "r", encoding="utf-8-sig", newline="")
        except OSError as exc:
            raise CommandError(f"Não foi possível abrir o CSV: {exc}") from exc

        with arquivo:
            leitor = csv.DictReader(arquivo)
            campos = {campo.strip().lower() for campo in (leitor.fieldnames or [])}
            obrigatorios = {"municipio", "bairro", "unidade"}

            if not obrigatorios.issubset(campos):
                raise CommandError(
                    "O CSV precisa conter as colunas: municipio,bairro,unidade"
                )

            total = 0
            for numero, linha in enumerate(leitor, start=2):
                dados = {
                    str(chave).strip().lower(): (valor or "").strip()
                    for chave, valor in linha.items()
                }
                municipio_nome = dados.get("municipio", "")
                bairro_nome = dados.get("bairro", "")
                unidade_nome = dados.get("unidade", "")

                if not all((municipio_nome, bairro_nome, unidade_nome)):
                    raise CommandError(f"Linha {numero}: existem campos vazios.")

                municipio = Municipio.objects.filter(
                    nome__iexact=municipio_nome,
                    ativo=True,
                ).first()
                if not municipio:
                    raise CommandError(
                        f"Linha {numero}: município não encontrado: {municipio_nome}"
                    )

                unidade = (
                    Unidade.objects.filter(ativo=True)
                    .filter(nome__iexact=unidade_nome)
                    .first()
                ) or (
                    Unidade.objects.filter(ativo=True)
                    .filter(sigla__iexact=unidade_nome)
                    .first()
                )

                if not unidade:
                    raise CommandError(
                        f"Linha {numero}: unidade não encontrada: {unidade_nome}"
                    )

                bairro, _ = Bairro.objects.get_or_create(
                    municipio=municipio,
                    nome=bairro_nome,
                )

                AreaResponsabilidade.objects.update_or_create(
                    bairro=bairro,
                    defaults={"unidade": unidade, "ativo": True},
                )
                total += 1

        self.stdout.write(
            self.style.SUCCESS(f"{total} áreas de responsabilidade importadas/atualizadas.")
        )
