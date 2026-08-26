from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("solicitacoes", "0011_migrar_perfis_existentes_para_acesso"),
    ]

    operations = [
        migrations.AlterField(
            model_name="acessoinstitucional",
            name="perfil",
            field=models.CharField(
                max_length=20,
                choices=[
                    ("COPPM", "COPPM"),
                    ("CPR", "CPR"),
                    ("UNIDADE", "Unidade"),
                    ("OPERADOR", "Operador"),
                ],
            ),
        ),
    ]
