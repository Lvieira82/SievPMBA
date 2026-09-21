from datetime import datetime
from pathlib import Path

from django.conf import settings
from django.core.files.base import ContentFile
from django.db import transaction
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.files.storage import default_storage
from django.http import FileResponse, Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.contrib.staticfiles import finders

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.units import mm
from reportlab.platypus import Image, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from apps.solicitacoes.models import AnexoOPO, CumprimentoOPO, DocumentoSolicitacao, HistoricoSolicitacao, Solicitacao, TipoDocumento
from apps.solicitacoes.pdf_security import validar_pdf_upload
from apps.solicitacoes.permissoes import (
    eh_desenvolvedor,
    eh_gestor,
    eh_operador,
    pode_gerar_opo,
    pode_ver_mapa_eventos,
    pode_ver_solicitacao,
    pode_ver_documentacao_solicitacao,
    escopo_unidades,
)
from .geracao_opo import _gerar_pdf_opo, gerar_opo_com_evento_extra
from .forms import EditarOPOForm


def _abrir_pdf_seguro(arquivo_field):
    if not arquivo_field:
        raise Http404("Documento sem arquivo associado.")
    nome = getattr(arquivo_field, "name", "") or ""
    if not nome:
        raise Http404("Documento sem nome de arquivo.")
    try:
        if default_storage.exists(nome):
            return default_storage.open(nome, "rb")
    except (OSError, ValueError):
        pass
    try:
        caminho = Path(settings.MEDIA_ROOT) / nome
        if caminho.is_file():
            return caminho.open("rb")
    except (OSError, ValueError):
        pass
    raise Http404(f"O PDF não foi encontrado no armazenamento. Arquivo registrado: {nome}")


@login_required
def documentos_solicitacao_seguro(request, id):
    s = get_object_or_404(Solicitacao.objects.select_related("unidade", "municipio", "bairro"), pk=id)
    if not pode_ver_documentacao_solicitacao(request.user):
        messages.error(request, "A documentação das solicitações é exclusiva do Gestor de Unidade e do Desenvolvedor.")
        return redirect("painel_gestao")
    if not pode_ver_solicitacao(request.user, s):
        messages.error(request, "Você não possui acesso aos documentos desta solicitação.")
        return redirect("painel_gestao")
    docs = DocumentoSolicitacao.objects.filter(solicitacao=s).select_related("tipo_documento")
    opos = AnexoOPO.objects.filter(solicitacao=s).exclude(arquivo="").order_by("-criado_em")
    tipos = TipoDocumento.objects.filter(ativo=True).order_by("nome")
    pode_anexar = s.status != "PENDENTE" and (eh_desenvolvedor(request.user) or (eh_gestor(request.user) and getattr(request.user.acesso_institucional, "perfil", None) == "UNIDADE"))
    if request.method == "POST":
        if not pode_anexar:
            messages.error(request, "A documentação desta solicitação já está encerrada nesta fase.")
            return redirect("documentos_solicitacao", id=id)
        arq = request.FILES.get("arquivo")
        tid = request.POST.get("tipo_documento")
        if not arq or not tid:
            messages.error(request, "Informe o PDF e o tipo do documento.")
        else:
            try:
                validar_pdf_upload(arq)
                tipo = get_object_or_404(TipoDocumento, pk=tid, ativo=True)
                DocumentoSolicitacao.objects.create(solicitacao=s, tipo_documento=tipo, descricao=request.POST.get("descricao", "").strip(), arquivo=arq)
                messages.success(request, "Documento anexado com sucesso.")
                return redirect("documentos_solicitacao", id=id)
            except Exception as e:
                messages.error(request, f"Documento rejeitado: {e}")
    return render(request, "gestao/documentos_solicitacao.html", {"solicitacao": s, "documentos": docs, "opos": opos, "tipos_documento": tipos, "pode_anexar": pode_anexar})


@login_required
def abrir_oficio_comandante_seguro(request, id):
    s = get_object_or_404(Solicitacao.objects.select_related("unidade"), pk=id)
    if not pode_ver_documentacao_solicitacao(request.user) or not pode_ver_solicitacao(request.user, s):
        messages.error(request, "Você não possui acesso a este documento.")
        return redirect("painel_gestao")
    if not hasattr(s, "oficio_comandante"):
        raise Http404("O Ofício ao Comandante deve estar registrado em Documentos da Solicitação.")
    arquivo_field = s.oficio_comandante
    arquivo = _abrir_pdf_seguro(arquivo_field)
    nome = Path(arquivo_field.name).name or "oficio_comandante.pdf"
    resposta = FileResponse(arquivo, content_type="application/pdf")
    resposta["Content-Disposition"] = f'inline; filename="{nome}"'
    resposta["X-Content-Type-Options"] = "nosniff"
    return resposta


@login_required
def abrir_documento_solicitacao_seguro(request, id, tipo="arquivo"):
    doc = get_object_or_404(DocumentoSolicitacao.objects.select_related("solicitacao__unidade"), pk=id)
    if tipo not in {"pdf", "arquivo", "documento", "oficio_comandante"}:
        raise Http404("Tipo de documento inválido.")
    if not pode_ver_documentacao_solicitacao(request.user) or not pode_ver_solicitacao(request.user, doc.solicitacao):
        messages.error(request, "Você não possui acesso a este documento.")
        return redirect("painel_gestao")
    arquivo = _abrir_pdf_seguro(doc.arquivo)
    vistos = set(request.session.get(f"documentos_conferidos_{doc.solicitacao_id}", []))
    vistos.add(str(doc.id))
    request.session[f"documentos_conferidos_{doc.solicitacao_id}"] = sorted(vistos)
    request.session.modified = True
    nome = Path(doc.arquivo.name).name or "documento.pdf"
    resposta = FileResponse(arquivo, content_type="application/pdf")
    resposta["Content-Disposition"] = f'inline; filename="{nome}"'
    resposta["X-Content-Type-Options"] = "nosniff"
    return resposta


@login_required
def abrir_opo_gestao_seguro(request, anexo_id):
    anexo = get_object_or_404(AnexoOPO.objects.select_related("solicitacao", "solicitacao__unidade"), pk=anexo_id)
    solicitacao = anexo.solicitacao
    if eh_operador(request.user) or not pode_ver_solicitacao(request.user, solicitacao):
        messages.error(request, "Você não possui acesso a esta OPO.")
        return redirect("painel_gestao")
    arquivo = _abrir_pdf_seguro(anexo.arquivo)
    nome = Path(anexo.arquivo.name).name or f"OPO_{solicitacao.protocolo}.pdf"
    resposta = FileResponse(arquivo, content_type="application/pdf")
    resposta["Content-Disposition"] = f'inline; filename="{nome}"'
    resposta["X-Content-Type-Options"] = "nosniff"
    return resposta


@login_required
def opos_geradas_seguro(request):
    if eh_operador(request.user):
        messages.error(request, "Operadores só podem visualizar as OPOs liberadas em Eventos do Dia.")
        return redirect("eventos_dia")
    anexos = AnexoOPO.objects.select_related("solicitacao", "solicitacao__unidade", "solicitacao__municipio", "solicitacao__bairro").filter(solicitacao__unidade__in=escopo_unidades(request.user)).exclude(arquivo="").order_by("-criado_em")
    grupos = {}
    for a in anexos:
        if a.solicitacao.protocolo not in grupos:
            grupos[a.solicitacao.protocolo] = {"codigo": a.solicitacao.protocolo, "solicitacao": a.solicitacao, "arquivos": [], "documentos": list(DocumentoSolicitacao.objects.filter(solicitacao=a.solicitacao).select_related("tipo_documento"))}
        grupos[a.solicitacao.protocolo]["arquivos"].append(a)
    pode_apoio_base = eh_desenvolvedor(request.user) or eh_gestor(request.user)
    for protocolo in grupos.values():
        protocolo["pode_apoio"] = pode_apoio_base and not CumprimentoOPO.objects.filter(opo__solicitacao=protocolo["solicitacao"], respondido_em__isnull=False).exists()
    return render(request, "gestao/opos_geradas.html", {"protocolos": list(grupos.values()), "pode_apoio": pode_apoio_base})


@login_required
def detalhe_opo_seguro(request, id):
    if eh_operador(request.user):
        messages.error(request, "Operadores só podem visualizar as OPOs liberadas em Eventos do Dia.")
        return redirect("eventos_dia")
    s = get_object_or_404(Solicitacao.objects.select_related("municipio", "bairro", "unidade", "tipo_evento"), pk=id)
    if not pode_ver_solicitacao(request.user, s):
        messages.error(request, "Você não possui acesso a esta OPO.")
        return redirect("painel_gestao")
    anexos = AnexoOPO.objects.filter(solicitacao=s).exclude(arquivo="").order_by("-criado_em")
    documentos = DocumentoSolicitacao.objects.filter(solicitacao=s).select_related("tipo_documento")
    a = getattr(request.user, "acesso_institucional", None)
    pode_apoio = bool(anexos.exists() and (eh_desenvolvedor(request.user) or (a and a.ativo and request.user.is_active and a.funcao == "GESTOR" and a.perfil in {"COPPM", "CPR", "UNIDADE"} and (a.perfil in {"COPPM", "CPR"} or a.unidade_id == s.unidade_id))) and not CumprimentoOPO.objects.filter(opo__solicitacao=s, respondido_em__isnull=False).exists())
    pode_editar_remover = _pode_editar_remover_opo(request, s) and not CumprimentoOPO.objects.filter(opo__solicitacao=s, respondido_em__isnull=False).exists() and not s.apoios.exists()
    return render(request, "gestao/detalhe_opo.html", {"solicitacao": s, "anexos": anexos, "documentos": documentos, "pode_apoio": pode_apoio, "pode_editar_remover": pode_editar_remover})


def _pode_editar_remover_opo(request, solicitacao):
    if eh_desenvolvedor(request.user):
        return True
    acesso = getattr(request.user, "acesso_institucional", None)
    return bool(
        acesso and acesso.ativo and request.user.is_active
        and acesso.funcao in {"GESTOR", "MEMBRO"}
        and acesso.perfil == "UNIDADE"
        and acesso.unidade_id == solicitacao.unidade_id
    )


def _opo_principal_queryset(solicitacao):
    return AnexoOPO.objects.filter(solicitacao=solicitacao).exclude(arquivo="")


@login_required
def editar_opo_seguro(request, id):
    solicitacao = get_object_or_404(
        Solicitacao.objects.select_related("municipio", "bairro", "unidade", "tipo_evento"),
        pk=id,
    )
    if not _pode_editar_remover_opo(request, solicitacao):
        messages.error(request, "Somente Gestor ou Membro da Unidade responsável pode editar esta OPO.")
        return redirect("painel_gestao")

    if CumprimentoOPO.objects.filter(opo__solicitacao=solicitacao, respondido_em__isnull=False).exists():
        messages.error(request, "Esta OPO já possui atendimento registrado e não pode mais ser editada.")
        return redirect("detalhe_opo", id=id)

    if solicitacao.apoios.exists():
        messages.error(request, "Esta OPO já foi compartilhada para apoio e não pode ser editada. Faça os ajustes antes de compartilhar.")
        return redirect("detalhe_opo", id=id)

    if request.method == "POST":
        form = EditarOPOForm(request.POST, instance=solicitacao)
        if form.is_valid():
            try:
                with transaction.atomic():
                    antigos = list(_opo_principal_queryset(solicitacao).values_list("id", "arquivo"))
                    nomes_arquivos_antigos = [nome for _, nome in antigos if nome]
                    evento_extra = any(
                        "EVENTO EXTRA: SIM" in (descricao or "").upper()
                        for descricao in AnexoOPO.objects.filter(
                            solicitacao=solicitacao
                        ).values_list("descricao", flat=True)
                    )
                    obj = form.save(commit=False)
                    obj.save(update_fields=[
                        "local", "bairro", "data_evento", "hora_inicio", "hora_fim",
                        "observacoes", "opo_permanente", "opo_permanente_data_fim",
                        "opo_permanente_indeterminado", "atualizado_em",
                    ])

                    conteudo = _gerar_pdf_opo(
                        request,
                        obj,
                        evento_extra=evento_extra,
                        unidade_executor=(
                            getattr(getattr(request.user, "acesso_institucional", None), "unidade", None)
                            or obj.unidade
                        ),
                    )

                    antigos_queryset = list(_opo_principal_queryset(obj))
                    for anexo_antigo in antigos_queryset:
                        anexo_antigo.delete()

                    anexo = AnexoOPO(
                        solicitacao=obj,
                        descricao=(
                            "OPO atualizada pelo SiEv — Evento extra: "
                            f"{'SIM' if evento_extra else 'NÃO'}"
                        ),
                    )
                    anexo.arquivo.save(
                        f"OPO_{obj.protocolo}.pdf",
                        ContentFile(conteudo),
                        save=True,
                    )
                    novo_arquivo = anexo.arquivo.name

                    if nomes_arquivos_antigos:
                        transaction.on_commit(
                            lambda nomes=nomes_arquivos_antigos, novo=novo_arquivo: [
                                default_storage.delete(nome)
                                for nome in nomes
                                if nome and nome != novo
                            ]
                        )
                    HistoricoSolicitacao.objects.create(
                        solicitacao=obj,
                        usuario=request.user,
                        acao="OPO EDITADA",
                        status=obj.status,
                        observacao=(
                            "OPO editada após a geração. "
                            "Local, data/horários, observações e/ou vigência foram atualizados. "
                            f"Arquivos anteriores substituídos: {len(antigos)}."
                        ),
                    )
                messages.success(request, f"OPO {obj.protocolo} atualizada e regenerada com sucesso.")
                return redirect("detalhe_opo", id=obj.id)
            except Exception as exc:
                messages.error(request, f"Não foi possível atualizar a OPO: {exc}")
    else:
        form = EditarOPOForm(instance=solicitacao)

    return render(
        request,
        "gestao/editar_opo.html",
        {"form": form, "solicitacao": solicitacao},
    )


@login_required
def remover_opo_seguro(request, id):
    if request.method != "POST":
        messages.error(request, "A remoção da OPO deve ser confirmada pelo botão Remover OPO.")
        return redirect("detalhe_opo", id=id)

    solicitacao = get_object_or_404(Solicitacao, pk=id)
    if not _pode_editar_remover_opo(request, solicitacao):
        messages.error(request, "Somente Gestor ou Membro da Unidade responsável pode remover esta OPO.")
        return redirect("painel_gestao")

    if CumprimentoOPO.objects.filter(opo__solicitacao=solicitacao, respondido_em__isnull=False).exists():
        messages.error(request, "Esta OPO já possui atendimento registrado e não pode ser removida.")
        return redirect("detalhe_opo", id=id)

    if solicitacao.apoios.exists():
        messages.error(request, "Esta OPO já foi compartilhada para apoio e não pode ser removida.")
        return redirect("detalhe_opo", id=id)

    try:
        with transaction.atomic():
            arquivos_remover = [
                anexo.arquivo.name
                for anexo in _opo_principal_queryset(solicitacao)
                if anexo.arquivo and anexo.arquivo.name
            ]
            quantidade = _opo_principal_queryset(solicitacao).count()
            _opo_principal_queryset(solicitacao).delete()
            if arquivos_remover:
                transaction.on_commit(
                    lambda nomes=arquivos_remover: [
                        default_storage.delete(nome)
                        for nome in nomes
                    ]
                )

            era_permanente = solicitacao.opo_permanente
            if era_permanente:
                solicitacao.opo_permanente = False
                solicitacao.opo_permanente_data_fim = None
                solicitacao.opo_permanente_indeterminado = False
                solicitacao.save(update_fields=[
                    "opo_permanente",
                    "opo_permanente_data_fim",
                    "opo_permanente_indeterminado",
                    "atualizado_em",
                ])

            HistoricoSolicitacao.objects.create(
                solicitacao=solicitacao,
                usuario=request.user,
                acao="OPO REMOVIDA",
                status=solicitacao.status,
                observacao=(
                    f"{quantidade} OPO(s) removida(s). "
                    + (
                        "A OPO permanente foi extinta e não permanece recorrente."
                        if era_permanente
                        else "O protocolo foi preservado."
                    )
                ),
            )
        messages.success(
            request,
            f"OPO {solicitacao.protocolo} removida. "
            + (
                "A recorrência da OPO permanente também foi encerrada."
                if era_permanente
                else "O protocolo permanece preservado."
            )
        )
    except Exception as exc:
        messages.error(request, f"Não foi possível remover a OPO: {exc}")

    return redirect("opos_geradas")


@login_required
def gerar_opo_seguro(request, id):
    s = get_object_or_404(Solicitacao, pk=id)
    if not pode_gerar_opo(request.user, s):
        messages.error(request, "Você não possui permissão para gerar esta OPO.")
        return redirect("painel_gestao")
    return gerar_opo_com_evento_extra(request, id)


def _eventos_mapa_territorial(request):
    """Retorna os eventos do mapa conforme o território efetivo do perfil.

    Para CPR, o território é definido pelo município do evento, não pela
    unidade que gerou a OPO. Assim, uma OPO da CIPE ou de uma unidade de
    outro CPR aparece no mapa quando o município pertence ao CPR logado.
    Para Unidade, permanece o escopo restrito à própria unidade.
    """
    acesso = getattr(request.user, "acesso_institucional", None)
    base = Solicitacao.objects.select_related(
        "municipio", "municipio__unidade_responsavel", "municipio__unidade_responsavel__cpr", "bairro", "unidade"
    )
    if acesso and acesso.perfil == "CPR" and acesso.cpr_id:
        return base.filter(municipio__unidade_responsavel__cpr_id=acesso.cpr_id).order_by("data_evento", "hora_inicio")
    return base.filter(unidade__in=escopo_unidades(request.user)).order_by("data_evento", "hora_inicio")


@login_required
def mapa_eventos_seguro(request):
    if not pode_ver_mapa_eventos(request.user):
        messages.error(request, "O mapa de eventos está disponível para gestores de CPR e Unidade.")
        return redirect("painel_gestao")
    eventos = _eventos_mapa_territorial(request)
    data_inicio = (request.GET.get("data_inicio") or "").strip()
    data_fim = (request.GET.get("data_fim") or "").strip()
    if data_inicio:
        try: eventos = eventos.filter(data_evento__gte=datetime.strptime(data_inicio, "%Y-%m-%d").date())
        except ValueError: data_inicio = ""
    if data_fim:
        try: eventos = eventos.filter(data_evento__lte=datetime.strptime(data_fim, "%Y-%m-%d").date())
        except ValueError: data_fim = ""
    return render(request, "gestao/mapa_eventos.html", {"eventos": eventos, "data_inicio": data_inicio, "data_fim": data_fim})


def _tipo_opo_mapa(solicitacao):
    anexo = AnexoOPO.objects.filter(solicitacao=solicitacao).exclude(arquivo="").order_by("-criado_em").first()
    if not anexo: return "ORDINÁRIO"
    descricao = (anexo.descricao or "").upper()
    if "EVENTO EXTRA: SIM" in descricao: return "EXTRAORDINÁRIO"
    if "EVENTO EXTRA: NÃO" in descricao or "EVENTO EXTRA: NAO" in descricao: return "ORDINÁRIO"
    return "ORDINÁRIO"


@login_required
def gerar_mapa_eventos_pdf_seguro(request):
    if not pode_ver_mapa_eventos(request.user):
        messages.error(request, "O mapa de eventos está disponível para gestores de CPR e Unidade.")
        return redirect("painel_gestao")
    eventos = _eventos_mapa_territorial(request)
    data_inicio = (request.GET.get("data_inicio") or "").strip(); data_fim = (request.GET.get("data_fim") or "").strip()
    if data_inicio:
        try: eventos = eventos.filter(data_evento__gte=datetime.strptime(data_inicio, "%Y-%m-%d").date())
        except ValueError: data_inicio = ""
    if data_fim:
        try: eventos = eventos.filter(data_evento__lte=datetime.strptime(data_fim, "%Y-%m-%d").date())
        except ValueError: data_fim = ""
    response = HttpResponse(content_type="application/pdf")
    inicio_nome=data_inicio or "inicio"; fim_nome=data_fim or "fim"; response["Content-Disposition"]=f'inline; filename="mapa_eventos_{inicio_nome}_{fim_nome}.pdf"'
    pagina=landscape(A4); doc=SimpleDocTemplate(response,pagesize=pagina,rightMargin=12*mm,leftMargin=12*mm,topMargin=12*mm,bottomMargin=12*mm)
    styles=getSampleStyleSheet(); titulo=ParagraphStyle("TituloMapa",parent=styles["Title"],fontName="Helvetica-Bold",fontSize=18,leading=21,alignment=TA_CENTER,spaceAfter=3); subtitulo=ParagraphStyle("SubtituloMapa",parent=styles["Normal"],fontName="Helvetica-Bold",fontSize=12,leading=15,alignment=TA_CENTER,spaceAfter=3); periodo=ParagraphStyle("PeriodoMapa",parent=styles["Normal"],fontSize=8.5,alignment=TA_CENTER,textColor=colors.HexColor("#444444"),spaceAfter=10); celula=ParagraphStyle("CelulaMapa",parent=styles["Normal"],fontSize=7.5,leading=9); cabecalho=ParagraphStyle("CabecalhoMapa",parent=celula,fontName="Helvetica-Bold",textColor=colors.white,alignment=TA_CENTER)
    story=[]; logo_path=finders.find("logos/logo_pmba.png")
    if logo_path:
        logo=Image(logo_path,width=22*mm,height=22*mm); logo.hAlign="CENTER"; story.append(logo); story.append(Spacer(1,2*mm))
    story.append(Paragraph("POLÍCIA MILITAR DA BAHIA",titulo)); unidades_titulo=[]
    for evento in eventos:
        if evento.unidade and evento.unidade.nome not in unidades_titulo: unidades_titulo.append(evento.unidade.nome)
    unidade_titulo=unidades_titulo[0] if len(unidades_titulo)==1 else (" / ".join(unidades_titulo) if unidades_titulo else "UNIDADE RESPONSÁVEL"); story.append(Paragraph(f"MAPA DE EVENTO - {unidade_titulo}",subtitulo))
    if data_inicio and data_fim: periodo_texto=f"Período: {datetime.strptime(data_inicio,'%Y-%m-%d').strftime('%d/%m/%Y')} a {datetime.strptime(data_fim,'%Y-%m-%d').strftime('%d/%m/%Y')}"
    elif data_inicio: periodo_texto=f"A partir de {datetime.strptime(data_inicio,'%Y-%m-%d').strftime('%d/%m/%Y')}"
    elif data_fim: periodo_texto=f"Até {datetime.strptime(data_fim,'%Y-%m-%d').strftime('%d/%m/%Y')}"
    else: periodo_texto="Todos os eventos do âmbito institucional"
    story.append(Paragraph(periodo_texto,periodo))
    dados=[[Paragraph("DATA",cabecalho),Paragraph("HORA",cabecalho),Paragraph("EVENTO",cabecalho),Paragraph("MUNICÍPIO",cabecalho),Paragraph("UNIDADE QUE GEROU",cabecalho),Paragraph("TIPO",cabecalho)]]
    for evento in eventos:
        unidade=evento.unidade.nome if evento.unidade else "Não definida"; dados.append([Paragraph(evento.data_evento.strftime("%d/%m/%Y"),celula),Paragraph(evento.hora_inicio.strftime("%H:%M") if evento.hora_inicio else "-",celula),Paragraph(evento.nome_evento or "-",celula),Paragraph(evento.municipio.nome if evento.municipio else "-",celula),Paragraph(unidade,celula),Paragraph(_tipo_opo_mapa(evento),celula)])
    tabela=Table(dados,repeatRows=1,colWidths=[22*mm,18*mm,50*mm,38*mm,72*mm,30*mm]); tabela.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,0),colors.HexColor("#6b7280")),("TEXTCOLOR",(0,0),(-1,0),colors.white),("GRID",(0,0),(-1,-1),0.4,colors.HexColor("#9ca3af")),("VALIGN",(0,0),(-1,-1),"MIDDLE"),("ALIGN",(0,0),(1,-1),"CENTER"),("ALIGN",(5,1),(5,-1),"CENTER"),("ROWBACKGROUNDS",(0,1),(-1,-1),[colors.white,colors.HexColor("#f3f4f6")]),("TOPPADDING",(0,0),(-1,-1),5),("BOTTOMPADDING",(0,0),(-1,-1),5)])); story.append(tabela)
    if not eventos.exists(): story.append(Spacer(1,8*mm)); story.append(Paragraph("Nenhum evento encontrado para o período selecionado.",celula))
    doc.build(story); return response
