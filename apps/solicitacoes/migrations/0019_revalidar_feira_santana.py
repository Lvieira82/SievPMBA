import importlib

from django.db import migrations


FEIRA = "apps.solicitacoes.migrations.0013_cadastrar_unidades_bairros_feira_santana"


def executar(apps, schema_editor):
    Municipio = apps.get_model("solicitacoes", "Municipio")
    Bairro = apps.get_model("solicitacoes", "Bairro")
    Unidade = apps.get_model("solicitacoes", "Unidade")
    AreaResponsabilidade = apps.get_model("solicitacoes", "AreaResponsabilidade")

    municipio = Municipio.objects.filter(nome__iexact="Feira de Santana").first()
    if municipio is None:
        return

    fonte = importlib.import_module(FEIRA)

    for nome_unidade, nomes_bairros in fonte.BAIRROS.items():
        unidades_ativas = list(
            Unidade.objects.filter(
                nome__iexact=nome_unidade,
                ativo=True,
            ).order_by("id")
        )
        unidades_inativas = list(
            Unidade.objects.filter(
                nome__iexact=nome_unidade,
                ativo=False,
            ).order_by("id")
        )

        if len(unidades_ativas) == 1:
            unidade = unidades_ativas[0]
        elif len(unidades_ativas) == 0 and len(unidades_inativas) == 1:
            # Não reativa a unidade. Apenas preserva a associação territorial
            # correta para que o cadastro administrativo continue soberano.
            unidade = unidades_inativas[0]
        else:
            raise RuntimeError(
                f"A unidade '{nome_unidade}' de Feira de Santana não pôde ser resolvida de forma única."
            )

        for nome_bairro in nomes_bairros:
            bairro = Bairro.objects.filter(
                municipio=municipio,
                nome__iexact=nome_bairro,
            ).first()

            if bairro is None:
                bairro = Bairro.objects.create(
                    municipio=municipio,
                    nome=nome_bairro,
                    ativo=True,
                )
            elif not bairro.ativo:
                bairro.ativo = True
                bairro.save(update_fields=["ativo"])

            area = AreaResponsabilidade.objects.filter(
                bairro=bairro,
            ).order_by("id").first()

            if area is None:
                AreaResponsabilidade.objects.create(
                    bairro=bairro,
                    unidade=unidade,
                    ativo=True,
                )
            else:
                area.unidade = unidade
                area.ativo = True
                area.save(update_fields=["unidade", "ativo"])
                AreaResponsabilidade.objects.filter(
                    bairro=bairro,
                ).exclude(pk=area.pk).delete()


def desfazer(apps, schema_editor):
    pass


class Migration(migrations.Migration):
    dependencies = [
        ("solicitacoes", "0018_bloquear_multiplas_unidades_por_bairro"),
    ]

    operations = [
        migrations.RunPython(executar, desfazer),
    ]
