from django.db import migrations


def migrar_perfis(apps, schema_editor):
    PerfilUsuario = apps.get_model("solicitacoes", "PerfilUsuario")
    AcessoInstitucional = apps.get_model("solicitacoes", "AcessoInstitucional")

    for perfil in PerfilUsuario.objects.select_related("usuario", "cpr", "unidade"):
        usuario = perfil.usuario
        if AcessoInstitucional.objects.filter(usuario_id=usuario.pk).exists():
            continue

        AcessoInstitucional.objects.create(
            usuario_id=usuario.pk,
            matricula=usuario.username,
            cpf=None,
            telefone="",
            perfil=perfil.perfil,
            funcao="GESTOR",
            cpr_id=perfil.cpr_id,
            unidade_id=perfil.unidade_id,
            primeiro_acesso=False,
            ativo=perfil.ativo and usuario.is_active,
        )


def remover_perfis_migrados(apps, schema_editor):
    # A reversão remove apenas os acessos criados a partir dos perfis antigos.
    # Como não há marcador de origem no modelo, a reversão é deliberadamente vazia.
    pass


class Migration(migrations.Migration):
    dependencies = [
        ("solicitacoes", "0009_acesso_institucional_seguro"),
    ]

    operations = [
        migrations.RunPython(migrar_perfis, remover_perfis_migrados),
    ]
