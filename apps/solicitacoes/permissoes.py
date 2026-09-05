from .models import Unidade


def acesso_do_usuario(user):
    if not user or not user.is_authenticated:
        return None
    return getattr(user, "acesso_institucional", None)


def eh_desenvolvedor(user):
    # Desenvolvedor é exclusivamente o superuser do Django.
    return bool(user and user.is_authenticated and user.is_superuser)


def acesso_ativo(user):
    a = acesso_do_usuario(user)
    return bool(a and a.ativo and user.is_active)


def eh_gestor(user):
    a = acesso_do_usuario(user)
    return bool(eh_desenvolvedor(user) or (a and a.ativo and user.is_active and a.funcao == "GESTOR"))


def eh_membro(user):
    a = acesso_do_usuario(user)
    return bool(a and a.ativo and user.is_active and a.funcao == "MEMBRO" and a.perfil in {"COPPM", "CPR", "UNIDADE"})


def eh_operador(user):
    a = acesso_do_usuario(user)
    return bool(a and a.ativo and user.is_active and a.perfil == "OPERADOR")


def perfil_gestor(user, perfil):
    if eh_desenvolvedor(user):
        return True
    a = acesso_do_usuario(user)
    return bool(a and a.ativo and user.is_active and a.funcao == "GESTOR" and a.perfil == perfil)


def pode_ver_historico(user):
    return bool(eh_desenvolvedor(user) or perfil_gestor(user, "COPPM") or perfil_gestor(user, "CPR") or perfil_gestor(user, "UNIDADE"))


def pode_ver_ranking(user):
    return bool(eh_desenvolvedor(user) or perfil_gestor(user, "COPPM") or perfil_gestor(user, "CPR") or perfil_gestor(user, "UNIDADE"))


def pode_ver_proximos_eventos(user):
    return bool(eh_desenvolvedor(user) or perfil_gestor(user, "COPPM") or perfil_gestor(user, "CPR") or perfil_gestor(user, "UNIDADE"))


def pode_ver_cprs(user):
    return bool(eh_desenvolvedor(user) or perfil_gestor(user, "COPPM"))


def pode_ver_unidades(user):
    return bool(eh_desenvolvedor(user) or perfil_gestor(user, "COPPM") or perfil_gestor(user, "CPR") or perfil_gestor(user, "UNIDADE"))


def pode_ver_mapa_eventos(user):
    return bool(eh_desenvolvedor(user) or perfil_gestor(user, "CPR") or perfil_gestor(user, "UNIDADE"))


def pode_ver_dashboard(user):
    return bool(eh_desenvolvedor(user) or perfil_gestor(user, "UNIDADE"))


def pode_ver_documentacao_solicitacao(user):
    return bool(eh_desenvolvedor(user) or perfil_gestor(user, "UNIDADE"))


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


def pode_administrar_usuarios(user):
    # Somente desenvolvedor e gestores institucionais. Membros não administram usuários.
    return bool(eh_desenvolvedor(user) or perfil_gestor(user, "COPPM") or perfil_gestor(user, "CPR") or perfil_gestor(user, "UNIDADE"))


def pode_lancamento_manual(user):
    a = acesso_do_usuario(user)
    return bool(
        eh_desenvolvedor(user)
        or (a and a.ativo and user.is_active and a.funcao in {"GESTOR", "MEMBRO"} and a.perfil in {"CPR", "UNIDADE"})
    )


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
    return bool(a and a.ativo and user.is_active and a.funcao in {"GESTOR", "MEMBRO"} and a.perfil in {"CPR", "UNIDADE"} and pode_ver_solicitacao(user, solicitacao))


def pode_gerar_opo(user, solicitacao):
    if eh_desenvolvedor(user):
        return True
    a = acesso_do_usuario(user)
    return bool(a and a.ativo and user.is_active and a.funcao in {"GESTOR", "MEMBRO"} and a.perfil in {"CPR", "UNIDADE"} and pode_ver_solicitacao(user, solicitacao))


def descricao_acesso(user):
    if eh_desenvolvedor(user):
        return "Desenvolvedor / Administrador"
    a = acesso_do_usuario(user)
    if not a:
        return "Sem acesso institucional"
    return f"{a.get_funcao_display()} {a.get_perfil_display()}"
