from django.db import migrations


def reativar(apps, schema_editor):
    CPR = apps.get_model("solicitacoes", "CPR")
    Unidade = apps.get_model("solicitacoes", "Unidade")

    CPR.objects.all().update(ativo=True)
    Unidade.objects.all().update(ativo=True)


class Migration(migrations.Migration):
    dependencies = [
        ("solicitacoes", "0013_corrigir_acessos_e_estrutura_territorial"),
    ]

    operations = [
        migrations.RunPython(reativar, migrations.RunPython.noop),
    ]
