from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("solicitacoes", "0025_efetivo_institucional"),
    ]

    operations = [
        migrations.AlterField(
            model_name="apoioevento",
            name="unidade_destino",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="apoios_recebidos",
                to="solicitacoes.unidade",
            ),
        ),
        migrations.AddField(
            model_name="apoioevento",
            name="cpr_destino",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="apoios_recebidos",
                to="solicitacoes.cpr",
            ),
        ),
    ]
