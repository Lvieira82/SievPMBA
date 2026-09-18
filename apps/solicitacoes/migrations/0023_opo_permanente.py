from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("solicitacoes", "0022_seed_comandos_especializados"),
    ]

    operations = [
        migrations.AddField(
            model_name="solicitacao",
            name="opo_permanente",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="solicitacao",
            name="opo_permanente_data_fim",
            field=models.DateField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="solicitacao",
            name="opo_permanente_indeterminado",
            field=models.BooleanField(default=False),
        ),
    ]
