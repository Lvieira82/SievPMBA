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

    # Somente superuser possui privilégios de desenvolvedor.
    # is_staff não transforma usuário institucional em administrador.
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

    return (
        (acesso.funcao == "GESTOR" and acesso.perfil in {"COPPM", "CPR", "UNIDADE"})
        or
        (acesso.funcao == "MEMBRO" and acesso.perfil in {"CPR", "UNIDADE"})
    )


def pode_criar_usuario(
    user,
    perfil_destino,
    funcao_destino="MEMBRO",
    unidade=None,
    cpr=None,
):
    acesso = escopo_usuario(user)

    if isinstance(acesso, dict):
        return True

    if not acesso:
        return False

    if perfil_destino == "OPERADOR":
        if not unidade:
            return False
        if acesso.perfil == "COPPM":
            return True
        if acesso.perfil == "CPR":
            return unidade.cpr_id == acesso.cpr_id
        if acesso.perfil == "UNIDADE":
            return unidade.id == acesso.unidade_id
        return False

    if funcao_destino not in {"GESTOR", "MEMBRO"}:
        return False

    if acesso.funcao == "MEMBRO":
        if funcao_destino != "MEMBRO":
            return False
        if acesso.perfil == "CPR":
            return perfil_destino in {"CPR", "UNIDADE"} and (
                (perfil_destino == "CPR" and cpr and cpr.id == acesso.cpr_id)
                or (perfil_destino == "UNIDADE" and unidade and unidade.cpr_id == acesso.cpr_id)
            )
        if acesso.perfil == "UNIDADE":
            return perfil_destino == "UNIDADE" and unidade and unidade.id == acesso.unidade_id
        return False

    if acesso.perfil == "COPPM":
        return perfil_destino in {"COPPM", "CPR", "UNIDADE"}

    if acesso.perfil == "CPR":
        if perfil_destino == "CPR":
            return bool(cpr and cpr.id == acesso.cpr_id)
        if perfil_destino == "UNIDADE":
            return bool(unidade and unidade.cpr_id == acesso.cpr_id)
        return False

    if acesso.perfil == "UNIDADE":
        return perfil_destino == "UNIDADE" and bool(unidade and unidade.id == acesso.unidade_id)

    return False
