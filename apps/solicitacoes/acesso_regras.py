from django.contrib.auth.models import User
from .models import PerfilUsuario
from .models_acesso import AcessoInstitucional


def sincronizar_acesso(user, *, perfil, funcao="MEMBRO", cpr=None, unidade=None, matricula=None, cpf=None, telefone="", ativo=True, primeiro_acesso=True):
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
        defaults={"perfil": perfil if perfil != "OPERADOR" else "UNIDADE", "cpr": cpr, "unidade": unidade, "ativo": ativo},
    )
    return acesso


def escopo_usuario(user):
    if user.is_superuser or user.is_staff:
        return {"tipo": "SUPERUSER"}
    acesso = getattr(user, "acesso_institucional", None)
    if not acesso or not acesso.ativo or not user.is_active:
        return None
    return acesso


def pode_gerenciar_usuarios(user):
    acesso = escopo_usuario(user)
    if isinstance(acesso, dict):
        return True
    return bool(acesso and ((acesso.funcao == "GESTOR" and acesso.perfil in {"COPPM", "CPR", "UNIDADE"}) or (acesso.funcao == "MEMBRO" and acesso.perfil in {"CPR", "UNIDADE"})))


def pode_criar_usuario(user, perfil_destino, funcao_destino="MEMBRO", unidade=None, cpr=None):
    acesso = escopo_usuario(user)
    if isinstance(acesso, dict):
        return True
    if not acesso:
        return False
    if acesso.funcao == "GESTOR":
        if acesso.perfil == "COPPM":
            return perfil_destino == "COPPM" and funcao_destino == "MEMBRO"
        if acesso.perfil == "CPR":
            return perfil_destino in {"CPR", "OPERADOR"} and (perfil_destino != "OPERADOR" or cpr and cpr.id == acesso.cpr_id)
        if acesso.perfil == "UNIDADE":
            return perfil_destino in {"UNIDADE", "OPERADOR"} and (unidade and unidade.id == acesso.unidade_id)
    if acesso.funcao == "MEMBRO":
        if perfil_destino != "OPERADOR":
            return False
        return bool(unidade and unidade.id == acesso.unidade_id) if acesso.perfil == "UNIDADE" else bool(cpr and cpr.id == acesso.cpr_id)
    return False
