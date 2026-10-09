from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render

from apps.solicitacoes.models import ConfiguracaoUnidade, TipoDocumento, Unidade
from apps.solicitacoes.permissoes import acesso_do_usuario, eh_desenvolvedor


def _nome_oficio(tipo_documento):
    nome = (tipo_documento.nome or "").casefold()
    return "ofício" in nome and "comandante" in nome


@login_required
def configuracoes_opm(request):
    """Configura os documentos exigidos por uma OPM, usando os tipos já cadastrados."""
    acesso = acesso_do_usuario(request.user)
    desenvolvedor = eh_desenvolvedor(request.user)

    if not desenvolvedor:
        if not acesso or not acesso.ativo or not request.user.is_active or acesso.perfil != "UNIDADE" or acesso.funcao not in {"GESTOR", "MEMBRO"} or not acesso.unidade_id:
            messages.error(request, "Apenas o gestor ou membro autorizado da OPM pode configurar seus documentos.")
            return redirect("painel_gestao")
        unidades = Unidade.objects.filter(pk=acesso.unidade_id, ativo=True)
        unidade_id = acesso.unidade_id
    else:
        unidades = Unidade.objects.filter(ativo=True).order_by("sigla")
        unidade_id = request.POST.get("unidade") or request.GET.get("unidade")

    unidade = unidades.filter(pk=unidade_id).first() if unidade_id else (unidades.first() if desenvolvedor else None)
    if not unidade:
        messages.error(request, "Não foi possível identificar uma OPM ativa para configurar.")
        return redirect("painel_gestao")

    # Lista oficial de tipos já utilizada pelo formulário público do SIEVPMBA.
    # Mantém os nomes e a ordem existentes no sistema, mesmo que algum tipo
    # ainda não tenha sido cadastrado na tabela TipoDocumento deste ambiente.
    nomes_documentos_siev = [
        "Corpo de Bombeiros",
        "Vigilância Sanitária",
        "Meio Ambiente",
        "Ministério Público",
        "TAC",
        "CREA",
        "CRM",
        "CRMV",
        "CRO",
        "IBAMA",
        "INEMA",
        "Prefeitura",
        "Polícia Civil",
        "Exército Brasileiro",
        "Marinha do Brasil",
        "PRF",
        "DETRAN",
        "Defesa Civil",
        "ANAC",
        "DNIT",
        "DERBA / SIT",
        "Outro Documento",
    ]

    # Garante que cada opção já existente no formulário tenha um registro
    # correspondente para poder ser associada à unidade, sem criar tabelas.
    tipos_por_nome = {}
    for nome in nomes_documentos_siev:
        tipo, _ = TipoDocumento.objects.get_or_create(
            nome=nome,
            defaults={"descricao": nome, "ativo": True},
        )
        if not tipo.ativo:
            tipo.ativo = True
            tipo.save(update_fields=["ativo"])
        tipos_por_nome[nome] = tipo

    tipos_opcionais = [tipos_por_nome[nome] for nome in nomes_documentos_siev]
    oficio = TipoDocumento.objects.filter(ativo=True).filter(
        nome__icontains="Ofício"
    ).filter(nome__icontains="Comandante").first()

    if request.method == "POST":
        ids_recebidos = set(request.POST.getlist("documentos"))
        ids_validos = {str(tipo.pk) for tipo in tipos_opcionais}
        if not ids_recebidos.issubset(ids_validos):
            messages.error(request, "A seleção contém um tipo de documento inválido. Nenhuma alteração foi salva.")
            return redirect(f"{request.path}?unidade={unidade.pk}")

        with transaction.atomic():
            ConfiguracaoUnidade.objects.filter(unidade=unidade, tipo_documento__isnull=False).delete()
            selecionados = [tipo for tipo in tipos_opcionais if str(tipo.pk) in ids_recebidos]
            ConfiguracaoUnidade.objects.bulk_create([
                ConfiguracaoUnidade(
                    unidade=unidade,
                    tipo_documento=tipo,
                    obrigatorio=True,
                    ativo=True,
                )
                for tipo in selecionados
            ])

        messages.success(request, f"Configurações de documentos da OPM {unidade.sigla} salvas.")
        return redirect(f"{request.path}?unidade={unidade.pk}")

    selecionados = set(
        ConfiguracaoUnidade.objects.filter(
            unidade=unidade,
            tipo_documento__isnull=False,
            ativo=True,
            obrigatorio=True,
        ).values_list("tipo_documento_id", flat=True)
    )
    return render(request, "gestao/configuracoes_opm.html", {
        "unidade": unidade,
        "unidades": unidades,
        "selecionados": selecionados,
        "tipos_documento": tipos_opcionais,
        "oficio": oficio,
        "eh_desenvolvedor": desenvolvedor,
    })
