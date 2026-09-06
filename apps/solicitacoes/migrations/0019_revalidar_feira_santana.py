from django.db import migrations


def executar(apps, schema_editor):
    # A partir desta migration, o território dos municípios presentes no
    # cadastro_bairros_sievpm.csv já foi reconstruído exclusivamente pela
    # migration 0017. Não reutilizar as listas antigas de Feira, pois elas
    # poderiam reintroduzir bairros ou unidades que não constam da base oficial.
    pass


def desfazer(apps, schema_editor):
    pass


class Migration(migrations.Migration):
    dependencies = [
        ("solicitacoes", "0018_bloquear_multiplas_unidades_por_bairro"),
    ]

    operations = [
        migrations.RunPython(executar, desfazer),
    ]
