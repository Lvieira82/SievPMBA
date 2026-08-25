from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.solicitacoes.models import (
    AreaResponsabilidade,
    Bairro,
    Municipio,
    Unidade,
)


class Command(BaseCommand):
    help = "Cadastra/atualiza as áreas de responsabilidade informadas para Feira de Santana."

    REGRAS = (
        ("Humildes", "67ª CIPM"),
        ("Caboronga", "67ª CIPM"),
        ("João Durval Carneiro", "67ª CIPM"),
        ("Ipuaçu", "67ª CIPM"),
    )

    @transaction.atomic
    def handle(self, *args, **options):
        try:
            municipio = Municipio.objects.get(nome__iexact="Feira de Santana")
        except Municipio.DoesNotExist as exc:
            raise CommandError(
                "Feira de Santana ainda não está cadastrada em Municipio."
            ) from exc
        except Municipio.MultipleObjectsReturned as exc:
            raise CommandError(
                "Existem municípios duplicados com o nome Feira de Santana."
            ) from exc

        unidade = (
            Unidade.objects
            .filter(ativo=True)
            .filter(sigla__iexact="67ª CIPM")
            .first()
        )

        if not unidade:
            unidade = (
                Unidade.objects
                .filter(ativo=True, nome__icontains="67")
                .filter(nome__icontains="CIPM")
                .first()
            )

        if not unidade:
            raise CommandError(
                "67ª CIPM não encontrada. Cadastre a unidade antes de executar este comando."
            )

        for nome_bairro, nome_unidade in self.REGRAS:
            bairro, _ = Bairro.objects.get_or_create(
                municipio=municipio,
                nome=nome_bairro,
            )

            AreaResponsabilidade.objects.update_or_create(
                bairro=bairro,
                defaults={"unidade": unidade, "ativo": True},
            )

            self.stdout.write(
                self.style.SUCCESS(
                    f"{municipio.nome} / {nome_bairro} → {nome_unidade}"
                )
            )

        self.stdout.write(
            self.style.SUCCESS(
                "Regras territoriais de Feira de Santana cadastradas/atualizadas."
            )
        )
