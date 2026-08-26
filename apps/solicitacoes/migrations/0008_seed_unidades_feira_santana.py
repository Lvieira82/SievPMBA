from django.db import migrations


def criar_unidades_feira(apps, schema_editor):
    CPR = apps.get_model("solicitacoes", "CPR")
    Unidade = apps.get_model("solicitacoes", "Unidade")

    cpr_leste = CPR.objects.filter(sigla="CPR-L", ativo=True).first()
    if not cpr_leste:
        return

    unidades = (
        ("64ª CIPM/FEIRA DE SANTANA", "64ª CIPM/FEIRA DE SANTANA"),
        ("65ª CIPM/FEIRA DE SANTANA", "65ª CIPM/FEIRA DE SANTANA"),
    )

    for nome, sigla in unidades:
        Unidade.objects.get_or_create(
            nome=nome,
            defaults={
                "cpr": cpr_leste,
                "sigla": sigla,
                "tipo": "CIPM",
                "telefone": "",
                "email": "",
                "ativo": True,
            },
        )


def remover_unidades_feira(apps, schema_editor):
    Unidade = apps.get_model("solicitacoes", "Unidade")
    Unidade.objects.filter(
        nome__in=(
            "64ª CIPM/FEIRA DE SANTANA",
            "65ª CIPM/FEIRA DE SANTANA",
        )
    ).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("solicitacoes", "0007_historicosolicitacao_acao_and_more"),
    ]

    operations = [
        migrations.RunPython(
            criar_unidades_feira,
            remover_unidades_feira,
        ),
    ]
