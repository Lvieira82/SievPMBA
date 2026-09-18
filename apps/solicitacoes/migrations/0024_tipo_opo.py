from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("solicitacoes", "0023_opo_permanente"),
    ]

    operations = [
        migrations.AddField(
            model_name="solicitacao",
            name="tipo_opo",
            field=models.CharField(
                choices=[
                    ("FESTIVO", "Festivo"),
                    ("INSTITUCIONAL", "Institucional"),
                ],
                default="FESTIVO",
                max_length=20,
            ),
        ),
    ]
