from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("solicitacoes", "0017_limpeza_controlada_territorio"),
    ]

    operations = [
        migrations.RunSQL(
            sql=(
                "CREATE UNIQUE INDEX IF NOT EXISTS "
                "siev_arearesp_bairro_unq "
                "ON solicitacoes_arearesponsabilidade (bairro_id)"
            ),
            reverse_sql=(
                "DROP INDEX IF EXISTS siev_arearesp_bairro_unq"
            ),
        ),
    ]
