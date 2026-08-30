from .models import PerfilUsuario
from .models_acesso import AcessoInstitucional


def sincronizar_acesso(
    user,
    *,
    perfil,
    funcao="MEMBRO",
    cpr=None,
    unidade=None,
    matricula=None,
    cpf=None,
    telefone="",
    ativo=True,
    primeiro_acesso=True,
):
    matricula = str(matricula or user.username).strip()

    acesso, _ = AcessoInstitucional.objects.update_or_create(
        usuario=user,
        defaults={
            "matricula": matricula,
            "cpf": cpf,
            "telefone": telefone or "",
            "perfil": perfil,
            "funcao": funcao,
            "cpr": cpr,
            "unidade": unidade,
            "primeiro_acesso": primeiro_acesso,
            "ativo": ativo,
        },
    )

    PerfilUsuario.objects.update_or_create(
        usuario=user,
        defaults={
            "perfil": perfil,
            "cpr": cpr,
            "unidade": unidade,
            "ativo": ativo,
        },
    )
    return acesso


def escopo_usuario(user):
    if not user or not user.is_authenticated:
        return None
    if user.is_superuser:
        return {"tipo": "SUPERUSER"}

    acesso = getattr(user, "acesso_institucional", None)
    if not acesso or not acesso.ativo or not user.is_active:
        return None
    return acesso


def pode_gerenciar_usuarios(user):
    acesso = escopo_usuario(user)
    if isinstance(acesso, dict):
        return True
    if not acesso:
        return False
    return acesso.funcao == "GESTOR" and acesso.perfil in {"COPPM", "CPR", "UNIDADE"}


def pode_criar_usuario(user, perfil_destino, funcao_destino="MEMBRO", unidade=None, cpr=None):
    """Define exatamente o que cada gestor pode cadastrar.

    COPPM -> somente Membro do COPPM.
    CPR   -> somente Membro do seu próprio CPR.
    Unidade -> Membro ou Operador da própria Unidade.
    """
    acesso = escopo_usuario(user)

    if isinstance(acesso, dict):
        return True
    if not acesso or acesso.funcao != "GESTOR":
        return False

    if acesso.perfil == "COPPM":
        return perfil_destino == "COPPM" and funcao_destino == "MEMBRO"

    if acesso.perfil == "CPR":
        return (
            perfil_destino == "CPR"
            and funcao_destino == "MEMBRO"
            and cpr is not None
            and cpr.id == acesso.cpr_id
        )

    if acesso.perfil == "UNIDADE":
        return (
            perfil_destino == "UNIDADE"
            and funcao_destino in {"MEMBRO", "OPERADOR"}
            and unidade is not None
            and unidade.id == acesso.unidade_id
        )

    return False
