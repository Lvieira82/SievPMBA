from django.contrib.auth.models import User
from django.db.models import Q

from .models import Unidade
from .models_acesso import AcessoInstitucional


def acesso_do_usuario(user):
    if not user or not user.is_authenticated:
        return None
    return getattr(user, "acesso_institucional", None)


def eh_desenvolvedor(user):
    return bool(user and user.is_authenticated and (user.is_superuser or user.is_staff))


def acesso_ativo(user):
    acesso = acesso_do_usuario(user)
    return bool(acesso and acesso.ativo and user.is_active)


def escopo_unidades(user):
    if eh_desenvolvedor(user):
        return Unidade.objects.filter(ativo=True)

    acesso = acesso_do_usuario(user)
    if not acesso or not acesso.ativo or not user.is_active:
        return Unidade.objects.none()

    if acesso.perfil == "COPPM":
        return Unidade.objects.filter(ativo=True)

    if acesso.perfil == "CPR" and acesso.cpr_id:
        return Unidade.objects.filter(cpr_id=acesso.cpr_id, ativo=True)

    if acesso.perfil in {"UNIDADE", "OPERADOR"} and acesso.unidade_id:
        return Unidade.objects.filter(pk=acesso.unidade_id, ativo=True)

    return Unidade.objects.none()


def eh_gestor(user):
    if eh_desenvolvedor(user):
        return True
    acesso = acesso_do_usuario(user)
    return bool(acesso and acesso.ativo and acesso.funcao == "GESTOR")


def eh_membro(user):
    acesso = acesso_do_usuario(user)
    return bool(acesso and acesso.ativo and acesso.funcao == "MEMBRO")


def eh_operador(user):
    acesso = acesso_do_usuario(user)
    return bool(acesso and acesso.ativo and acesso.perfil == "OPERADOR")


def pode_administrar_usuarios(user):
    return eh_gestor(user)


def pode_lancamento_manual(user):
    if eh_desenvolvedor(user):
        return True
    acesso = acesso_do_usuario(user)
    return bool(
        acesso
        and acesso.ativo
        and acesso.funcao == "GESTOR"
        and acesso.perfil == "UNIDADE"
        and acesso.unidade_id
    )


def pode_aprovar_solicitacao(user, solicitacao):
    if eh_desenvolvedor(user):
        return True

    acesso = acesso_do_usuario(user)
    if not acesso or not acesso.ativo or acesso.funcao != "GESTOR":
        return False

    if acesso.perfil == "COPPM":
        return True

    if acesso.perfil == "CPR":
        return bool(acesso.cpr_id and solicitacao.unidade_id and solicitacao.unidade.cpr_id == acesso.cpr_id)

    if acesso.perfil == "UNIDADE":
        return bool(acesso.unidade_id and solicitacao.unidade_id == acesso.unidade_id)

    return False


def pode_ver_solicitacao(user, solicitacao):
    if eh_desenvolvedor(user):
        return True

    acesso = acesso_do_usuario(user)
    if not acesso or not acesso.ativo:
        return False

    if acesso.perfil == "COPPM":
        return True

    if acesso.perfil == "CPR":
        return bool(acesso.cpr_id and solicitacao.unidade_id and solicitacao.unidade.cpr_id == acesso.cpr_id)

    if acesso.perfil in {"UNIDADE", "OPERADOR"}:
        return bool(acesso.unidade_id and solicitacao.unidade_id == acesso.unidade_id)

    return False


def descricao_acesso(user):
    if eh_desenvolvedor(user):
        return "Desenvolvedor / Administrador"

    acesso = acesso_do_usuario(user)
    if not acesso:
        return "Sem acesso institucional"

    nomes = {
        "COPPM": "COPPM",
        "CPR": "CPR",
        "UNIDADE": "Unidade",
        "OPERADOR": "Operador",
    }
    funcoes = {
        "GESTOR": "Gestor",
        "MEMBRO": "Membro",
    }
    return f"{funcoes.get(acesso.funcao, acesso.funcao)} {nomes.get(acesso.perfil, acesso.perfil)}"
