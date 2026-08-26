from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("solicitacoes", "0009_seed_bairros_feira_santana"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="AcessoInstitucional",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("matricula", models.CharField(max_length=30, unique=True)),
                ("cpf", models.CharField(blank=True, max_length=14, null=True, unique=True)),
                ("telefone", models.CharField(blank=True, max_length=25)),
                ("perfil", models.CharField(choices=[("COPPM", "COPPM"), ("CPR", "CPR"), ("UNIDADE", "Unidade")], max_length=20)),
                ("funcao", models.CharField(choices=[("GESTOR", "Gestor"), ("MEMBRO", "Membro")], default="MEMBRO", max_length=10)),
                ("primeiro_acesso", models.BooleanField(default=True)),
                ("ativo", models.BooleanField(default=True)),
                ("criado_em", models.DateTimeField(auto_now_add=True)),
                ("atualizado_em", models.DateTimeField(auto_now=True)),
                ("cpr", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="acessos_institucionais", to="solicitacoes.cpr")),
                ("unidade", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="acessos_institucionais", to="solicitacoes.unidade")),
                ("usuario", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="acesso_institucional", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "verbose_name": "Acesso Institucional",
                "verbose_name_plural": "Acessos Institucionais",
                "ordering": ["usuario__first_name", "matricula"],
            },
        ),
        migrations.CreateModel(
            name="DispositivoAutorizado",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("token_hash", models.CharField(max_length=64, unique=True)),
                ("rotulo", models.CharField(blank=True, max_length=120)),
                ("user_agent", models.TextField(blank=True)),
                ("criado_em", models.DateTimeField(auto_now_add=True)),
                ("ultimo_acesso", models.DateTimeField(auto_now=True)),
                ("ativo", models.BooleanField(default=True)),
                ("usuario", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="dispositivos_autorizados", to=settings.AUTH_USER_MODEL)),
            ],
            options={"verbose_name": "Dispositivo Autorizado", "verbose_name_plural": "Dispositivos Autorizados", "ordering": ["-ultimo_acesso"]},
        ),
        migrations.CreateModel(
            name="CodigoNovoNavegador",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("codigo_hash", models.CharField(max_length=128)),
                ("expira_em", models.DateTimeField()),
                ("criado_em", models.DateTimeField(auto_now_add=True)),
                ("tentativas", models.PositiveSmallIntegerField(default=0)),
                ("usado", models.BooleanField(default=False)),
                ("usuario", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="codigos_novo_navegador", to=settings.AUTH_USER_MODEL)),
            ],
            options={"verbose_name": "Código de Novo Navegador", "verbose_name_plural": "Códigos de Novo Navegador", "ordering": ["-criado_em"]},
        ),
    ]
