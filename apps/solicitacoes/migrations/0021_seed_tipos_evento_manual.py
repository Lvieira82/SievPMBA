from django.db import migrations


TIPOS = (
    ("ORDINÁRIO", "Emprego ordinário de policiamento."),
    ("EXTRAORDINÁRIO", "Emprego extraordinário de policiamento."),
)


def incluir_tipos(apps, schema_editor):
    TipoEvento = apps.get_model("solicitacoes", "TipoEvento")
    for nome, descricao in TIPOS:
        TipoEvento.objects.update_or_create(
            nome=nome,
            defaults={"descricao": descricao, "ativo": True},
        )


def remover_tipos(apps, schema_editor):
    TipoEvento = apps.get_model("solicitacoes", "TipoEvento")
    for nome, _ in TIPOS:
        TipoEvento.objects.filter(nome=nome).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("solicitacoes", "0020_cumprimento_opo"),
    ]

    operations = [
        migrations.RunPython(incluir_tipos, remover_tipos),
    ]
