from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.solicitacoes.models import AreaResponsabilidade, Bairro, Municipio, Unidade


class Command(BaseCommand):
    help = "Cadastra/atualiza as áreas de responsabilidade de Feira de Santana."

    REGRAS = (
        ("Queimadinha", "25ª BPM/FEIRA DE SANTANA"),
        ("São João", "25ª BPM/FEIRA DE SANTANA"),
        ("CASEB", "25ª BPM/FEIRA DE SANTANA"),
        ("Lagoa Grande", "25ª BPM/FEIRA DE SANTANA"),
        ("Parque Getulio Vargas", "25ª BPM/FEIRA DE SANTANA"),
        ("Cidade Nova", "25ª BPM/FEIRA DE SANTANA"),
        ("Parque Ipê", "25ª BPM/FEIRA DE SANTANA"),
        ("Papagaio", "25ª BPM/FEIRA DE SANTANA"),
        ("Mantiba", "25ª BPM/FEIRA DE SANTANA"),
        ("Tiquaruçu", "25ª BPM/FEIRA DE SANTANA"),
        ("Mangabeira", "25ª BPM/FEIRA DE SANTANA"),
        ("Aeroporto", "25ª BPM/FEIRA DE SANTANA"),
        ("Conceição", "25ª BPM/FEIRA DE SANTANA"),
        ("Santo Antonio dos Prazeres", "25ª BPM/FEIRA DE SANTANA"),
        ("SIM", "25ª BPM/FEIRA DE SANTANA"),
        ("Registro", "25ª BPM/FEIRA DE SANTANA"),
        ("Lagoa Salgada", "25ª BPM/FEIRA DE SANTANA"),
        ("São Roque", "25ª BPM/FEIRA DE SANTANA"),
        ("Subaé", "25ª BPM/FEIRA DE SANTANA"),
        ("Santa Mônica II", "25ª BPM/FEIRA DE SANTANA"),
        ("Chaparral", "25ª BPM/FEIRA DE SANTANA"),
        ("Tomba", "67ª CIPM/FEIRA DE SANTANA"),
        ("CIS", "67ª CIPM/FEIRA DE SANTANA"),
        ("Aviário", "67ª CIPM/FEIRA DE SANTANA"),
        ("Parque Viver", "67ª CIPM/FEIRA DE SANTANA"),
        ("Panorama", "67ª CIPM/FEIRA DE SANTANA"),
        ("Fraternidade", "67ª CIPM/FEIRA DE SANTANA"),
        ("35º BI", "67ª CIPM/FEIRA DE SANTANA"),
        ("Viveiros", "67ª CIPM/FEIRA DE SANTANA"),
        ("Ipuaçu", "67ª CIPM/FEIRA DE SANTANA"),
        ("Humildes", "67ª CIPM/FEIRA DE SANTANA"),
        ("Limoeiro", "67ª CIPM/FEIRA DE SANTANA"),
        ("Parque Tamandari", "67ª CIPM/FEIRA DE SANTANA"),
        ("Olhos D`água", "67ª CIPM/FEIRA DE SANTANA"),
        ("Jardim Acácia", "67ª CIPM/FEIRA DE SANTANA"),
        ("Sítio Matias", "67ª CIPM/FEIRA DE SANTANA"),
        ("Chácara São Cosme", "67ª CIPM/FEIRA DE SANTANA"),
        ("Mochila", "67ª CIPM/FEIRA DE SANTANA"),
        ("Feira X", "67ª CIPM/FEIRA DE SANTANA"),
        ("Feira VII", "67ª CIPM/FEIRA DE SANTANA"),
        ("Caboronga", "67ª CIPM/FEIRA DE SANTANA"),
        ("Liberdade", "67ª CIPM/FEIRA DE SANTANA"),
        ("Santa Mônica", "64ª CIPM/FEIRA DE SANTANA"),
        ("Capuchinhos", "64ª CIPM/FEIRA DE SANTANA"),
        ("Ponto Central", "64ª CIPM/FEIRA DE SANTANA"),
        ("Centro", "64ª CIPM/FEIRA DE SANTANA"),
        ("Rua Nova", "64ª CIPM/FEIRA DE SANTANA"),
        ("Serraria Brasil", "64ª CIPM/FEIRA DE SANTANA"),
        ("Cruzeiro", "64ª CIPM/FEIRA DE SANTANA"),
        ("Tanque da Nação", "64ª CIPM/FEIRA DE SANTANA"),
        ("Baraúnas", "65ª CIPM/FEIRA DE SANTANA"),
        ("Sobradinho", "65ª CIPM/FEIRA DE SANTANA"),
        ("Jardim Cruzeiro", "65ª CIPM/FEIRA DE SANTANA"),
        ("Calumbi", "65ª CIPM/FEIRA DE SANTANA"),
        ("Pedra do Descanso", "65ª CIPM/FEIRA DE SANTANA"),
        ("Nova Esperança", "65ª CIPM/FEIRA DE SANTANA"),
        ("Gabriela", "65ª CIPM/FEIRA DE SANTANA"),
        ("Campo Limpo", "65ª CIPM/FEIRA DE SANTANA"),
        ("George Americo", "65ª CIPM/FEIRA DE SANTANA"),
        ("Campo do Gado Novo", "65ª CIPM/FEIRA DE SANTANA"),
        ("Sítio Novo", "65ª CIPM/FEIRA DE SANTANA"),
        ("Pampalona", "65ª CIPM/FEIRA DE SANTANA"),
        ("Pedra Ferrada", "65ª CIPM/FEIRA DE SANTANA"),
        ("Asa Branca", "65ª CIPM/FEIRA DE SANTANA"),
        ("UEFS", "65ª CIPM/FEIRA DE SANTANA"),
        ("Novo Horizonte", "65ª CIPM/FEIRA DE SANTANA"),
        ("Maria Quitéria", "65ª CIPM/FEIRA DE SANTANA"),
        ("São José", "65ª CIPM/FEIRA DE SANTANA"),
        ("Feira VI", "65ª CIPM/FEIRA DE SANTANA"),
    )

    @transaction.atomic
    def handle(self, *args, **options):
        try:
            municipio = Municipio.objects.get(nome__iexact="Feira de Santana")
        except Municipio.DoesNotExist as exc:
            raise CommandError("Feira de Santana ainda não está cadastrada.") from exc
        except Municipio.MultipleObjectsReturned as exc:
            raise CommandError("Existem municípios duplicados com o nome Feira de Santana.") from exc

        for nome_bairro, nome_unidade in self.REGRAS:
            try:
                unidade = Unidade.objects.get(nome__iexact=nome_unidade, ativo=True)
            except Unidade.DoesNotExist as exc:
                raise CommandError(f"Unidade não encontrada: {nome_unidade}") from exc
            except Unidade.MultipleObjectsReturned as exc:
                raise CommandError(f"Unidade duplicada: {nome_unidade}") from exc

            bairro, _ = Bairro.objects.get_or_create(
                municipio=municipio,
                nome=nome_bairro,
                defaults={"ativo": True},
            )
            bairro.ativo = True
            bairro.save(update_fields=["ativo"])

            area = AreaResponsabilidade.objects.filter(bairro=bairro).order_by("id").first()
            if area:
                area.unidade = unidade
                area.ativo = True
                area.save(update_fields=["unidade", "ativo"])
                AreaResponsabilidade.objects.filter(bairro=bairro).exclude(pk=area.pk).delete()
            else:
                AreaResponsabilidade.objects.create(
                    bairro=bairro,
                    unidade=unidade,
                    ativo=True,
                )

            self.stdout.write(self.style.SUCCESS(
                f"{municipio.nome} / {nome_bairro} → {unidade.nome}"
            ))

        self.stdout.write(self.style.SUCCESS(
            "Território de Feira de Santana corrigido sem misturar bairros homônimos."
        ))
