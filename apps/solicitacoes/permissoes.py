from .models import Unidade


def acesso_do_usuario(user):
    if not user or not user.is_authenticated:
        return None
    return getattr(user, "acesso_institucional", None)


def eh_desenvolvedor(user):
    return bool(user and user.is_authenticated and (user.is_superuser or user.is_staff))


def acesso_ativo(user):
    a = acesso_do_usuario(user)
    return bool(a and a.ativo and user.is_active)


def escopo_unidades(user):
    if eh_desenvolvedor(user):
        return Unidade.objects.filter(ativo=True)
    a = acesso_do_usuario(user)
    if not a or not a.ativo or not user.is_active:
        return Unidade.objects.none()
    if a.perfil == "COPPM":
        return Unidade.objects.filter(ativo=True)
    if a.perfil == "CPR" and a.cpr_id:
        return Unidade.objects.filter(cpr_id=a.cpr_id, ativo=True)
    if a.perfil in {"UNIDADE", "OPERADOR"} and a.unidade_id:
        return Unidade.objects.filter(pk=a.unidade_id, ativo=True)
    return Unidade.objects.none()


def eh_gestor(user):
    a = acesso_do_usuario(user)
    return bool(eh_desenvolvedor(user) or (a and a.ativo and a.funcao == "GESTOR"))


def eh_membro(user):
    a = acesso_do_usuario(user)
    return bool(a and a.ativo and a.funcao == "MEMBRO" and a.perfil in {"COPPM", "CPR", "UNIDADE"})


def eh_operador(user):
    a = acesso_do_usuario(user)
    return bool(a and a.ativo and a.perfil == "OPERADOR")


def pode_administrar_usuarios(user):
    if eh_desenvolvedor(user):
        return True
    a = acesso_do_usuario(user)
    return bool(
        a and a.ativo and user.is_active and
        (
            (a.funcao == "GESTOR" and a.perfil in {"COPPM", "CPR", "UNIDADE"})
            or
            (a.funcao == "MEMBRO" and a.perfil in {"CPR", "UNIDADE"})
        )
    )


def pode_lancamento_manual(user):
    a = acesso_do_usuario(user)
    return bool(eh_desenvolvedor(user) or (a and a.ativo and a.funcao in {"GESTOR", "MEMBRO"} and a.perfil in {"CPR", "UNIDADE"}))


def pode_aprovar_solicitacao(user, solicitacao):
    if eh_desenvolvedor(user):
        return True
    a = acesso_do_usuario(user)
    if not a or not a.ativo or not user.is_active or a.funcao not in {"GESTOR", "MEMBRO"}:
        return False
    if a.perfil == "COPPM":
        return a.funcao == "GESTOR"
    if a.perfil == "CPR":
        return bool(a.cpr_id and solicitacao.unidade_id and solicitacao.unidade.cpr_id == a.cpr_id)
    if a.perfil == "UNIDADE":
        return bool(a.unidade_id and solicitacao.unidade_id == a.unidade_id)
    return False


def pode_ver_solicitacao(user, solicitacao):
    if eh_desenvolvedor(user):
        return True
    a = acesso_do_usuario(user)
    if not a or not a.ativo or not user.is_active:
        return False
    if a.perfil == "COPPM":
        return True
    if a.perfil == "CPR":
        return bool(a.cpr_id and solicitacao.unidade_id and solicitacao.unidade.cpr_id == a.cpr_id)
    if a.perfil in {"UNIDADE", "OPERADOR"}:
        return bool(a.unidade_id and solicitacao.unidade_id == a.unidade_id)
    return False


def pode_transferir(user, solicitacao):
    if eh_desenvolvedor(user):
        return True
    a = acesso_do_usuario(user)
    return bool(a and a.ativo and a.funcao in {"GESTOR", "MEMBRO"} and a.perfil in {"CPR", "UNIDADE"} and pode_ver_solicitacao(user, solicitacao))


def pode_gerar_opo(user, solicitacao):
    if eh_desenvolvedor(user):
        return True
    a = acesso_do_usuario(user)
    return bool(a and a.ativo and a.funcao in {"GESTOR", "MEMBRO"} and a.perfil in {"CPR", "UNIDADE"} and pode_ver_solicitacao(user, solicitacao))


def pode_administrar_usuario(user, usuario_alvo):
    if not usuario_alvo or usuario_alvo.id == getattr(user, "id", None):
        return False
    if eh_desenvolvedor(user):
        return True

    a = acesso_do_usuario(user)
    alvo = getattr(usuario_alvo, "acesso_institucional", None)

    if not a or not a.ativo or not user.is_active or not alvo or not alvo.ativo:
        return False

    if a.perfil == "COPPM" and a.funcao in {"GESTOR", "MEMBRO"}:
        return alvo.perfil in {"COPPM", "CPR", "UNIDADE", "OPERADOR"}

    if a.perfil == "CPR" and a.funcao in {"GESTOR", "MEMBRO"}:
        if alvo.perfil == "CPR":
            return alvo.cpr_id == a.cpr_id
        if alvo.perfil in {"UNIDADE", "OPERADOR"}:
            return bool(alvo.unidade_id and Unidade.objects.filter(pk=alvo.unidade_id, cpr_id=a.cpr_id, ativo=True).exists())
        return False

    if a.perfil == "UNIDADE" and a.funcao in {"GESTOR", "MEMBRO"}:
        return bool(alvo.unidade_id and alvo.unidade_id == a.unidade_id)

    return False


def descricao_acesso(user):
    if eh_desenvolvedor(user):
        return "Desenvolvedor / Administrador"
    a = acesso_do_usuario(user)
    if not a:
        return "Sem acesso institucional"
    return f"{a.get_funcao_display()} {a.get_perfil_display()}"
