from django.db import migrations


def corrigir_acessos(apps, schema_editor):
    User = apps.get_model("auth", "User")
    AcessoInstitucional = apps.get_model("solicitacoes", "AcessoInstitucional")
    PerfilUsuario = apps.get_model("solicitacoes", "PerfilUsuario")

    ids_acesso = set(AcessoInstitucional.objects.values_list("usuario_id", flat=True))
    ids_perfil = set(PerfilUsuario.objects.values_list("usuario_id", flat=True))
    ids = ids_acesso | ids_perfil

    if ids:
        User.objects.filter(id__in=ids, is_superuser=False).update(is_staff=False)


def ativar_estrutura_territorial(apps, schema_editor):
    CPR = apps.get_model("solicitacoes", "CPR")
    Unidade = apps.get_model("solicitacoes", "Unidade")

    CPR.objects.all().update(ativo=True)
    Unidade.objects.all().update(ativo=True)


class Migration(migrations.Migration):
    dependencies = [
        ("solicitacoes", "0012_adicionar_perfil_operador"),
    ]

    operations = [
        migrations.RunPython(corrigir_acessos, migrations.RunPython.noop),
        migrations.RunPython(ativar_estrutura_territorial, migrations.RunPython.noop),
    ]
