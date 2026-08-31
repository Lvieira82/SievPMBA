import csv
import io
from datetime import timedelta
from io import BytesIO
from xml.sax.saxutils import escape

import openpyxl
from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.conf import settings
from django.core.files.base import ContentFile
from django.http import FileResponse, Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.contrib.staticfiles import finders

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import Image, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from apps.solicitacoes.forms import SolicitacaoManualForm
from apps.solicitacoes.models import (
    AnexoOPO,
    Bairro,
    DocumentoSolicitacao,
    HistoricoSolicitacao,
    MatriculaAutorizada,
    Municipio,
    PerfilUsuario,
    Solicitacao,
    TipoDocumento,
    TipoEvento,
    Unidade,
)
from apps.solicitacoes.pdf_security import validar_pdf_upload


class GestaoManualForm(SolicitacaoManualForm):
    """Formulário manual com os dados territoriais definidos pelo operador."""

    def __init__(self, *args, perfil=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.perfil_gestor = perfil

        self.fields["municipio"] = forms.ModelChoiceField(
            queryset=Municipio.objects.filter(ativo=True).order_by("nome"),
            required=True,
            label="Município",
            widget=forms.Select(attrs={"class": "form-select"}),
        )
        self.fields["bairro"] = forms.ModelChoiceField(
            queryset=Bairro.objects.none(),
            required=False,
            label="Bairro / Distrito",
            widget=forms.Select(attrs={"class": "form-select"}),
        )
        self.fields["tipo_evento"] = forms.ModelChoiceField(
            queryset=TipoEvento.objects.filter(ativo=True).order_by("nome"),
            required=False,
            label="Tipo de evento",
            widget=forms.Select(attrs={"class": "form-select"}),
        )

        if perfil and perfil.unidade_id:
            unidades = Unidade.objects.filter(pk=perfil.unidade_id, ativo=True)
        elif perfil and perfil.cpr_id:
            unidades = Unidade.objects.filter(cpr_id=perfil.cpr_id, ativo=True).order_by("nome")
        else:
            unidades = Unidade.objects.filter(ativo=True).order_by("nome")

        self.fields["unidade"] = forms.ModelChoiceField(
            queryset=unidades,
            required=True,
            label="Unidade responsável",
            widget=forms.Select(attrs={"class": "form-select"}),
        )

        if self.instance and self.instance.pk:
            self.fields["municipio"].initial = self.instance.municipio_id
            self.fields["bairro"].initial = self.instance.bairro_id
            self.fields["tipo_evento"].initial = self.instance.tipo_evento_id
            self.fields["unidade"].initial = self.instance.unidade_id

    def clean_bairro(self):
        bairro = self.cleaned_data.get("bairro")
        municipio = self.cleaned_data.get("municipio")
        if bairro and municipio and bairro.municipio_id != municipio.id:
            raise forms.ValidationError("O bairro selecionado não pertence ao município.")
        return bairro


@login_required
def lancamento_manual(request):
    perfil = getattr(request.user, "perfil_siev", None)
    protocolo = request.GET.get("protocolo_origem", "").strip().upper()
    original = Solicitacao.objects.filter(protocolo=protocolo).first() if protocolo else None

    if protocolo and not original:
        messages.error(request, "Protocolo não encontrado.")

    if request.method == "POST":
        protocolo = request.POST.get("protocolo_origem", "").strip().upper()
        original = Solicitacao.objects.filter(protocolo=protocolo).first() if protocolo else None
        form = GestaoManualForm(request.POST, request.FILES, instance=original, perfil=perfil)

        if form.is_valid():
            obj = form.save(commit=False)
            obj.usuario = request.user
            obj.municipio = form.cleaned_data["municipio"]
            obj.bairro = form.cleaned_data.get("bairro")
            obj.tipo_evento = form.cleaned_data.get("tipo_evento")
            obj.unidade = form.cleaned_data["unidade"]
            obj.origem = "MANUAL"
            obj.status = "PENDENTE"
            obj.save()

            HistoricoSolicitacao.objects.create(
                solicitacao=obj,
                usuario=request.user,
                acao="LANÇAMENTO MANUAL",
                observacao="Solicitação criada/atualizada pelo módulo de lançamento manual.",
            )

            messages.success(request, f"Informação salva com o protocolo {obj.protocolo}.")
            return redirect("documentos_solicitacao", id=obj.id)
    else:
        form = GestaoManualForm(instance=original, perfil=perfil)

    return render(request, "gestao/lancamento_manual.html", {
        "form": form,
        "solicitacao_original": original,
        "protocolo_origem": protocolo,
    })


@login_required
def documentos_solicitacao(request, id):
    solicitacao = get_object_or_404(
        Solicitacao.objects.select_related("municipio", "bairro", "unidade"), pk=id
    )
    documentos = DocumentoSolicitacao.objects.filter(solicitacao=solicitacao).select_related("tipo_documento")
    tipos = TipoDocumento.objects.filter(ativo=True).order_by("nome")

    if request.method == "POST":
        arquivo = request.FILES.get("arquivo")
        tipo_id = request.POST.get("tipo_documento")
        descricao = request.POST.get("descricao", "").strip()
        if not arquivo or not tipo_id:
            messages.error(request, "Informe o PDF e o tipo do documento.")
        else:
            try:
                validar_pdf_upload(arquivo)
                tipo = get_object_or_404(TipoDocumento, pk=tipo_id, ativo=True)
                DocumentoSolicitacao.objects.create(
                    solicitacao=solicitacao, tipo_documento=tipo,
                    descricao=descricao, arquivo=arquivo,
                )
                messages.success(request, "Documento anexado com sucesso.")
                return redirect("documentos_solicitacao", id=id)
            except Exception as exc:
                messages.error(request, f"Documento rejeitado: {exc}")

    return render(request, "gestao/documentos_solicitacao.html", {
        "solicitacao": solicitacao, "documentos": documentos, "tipos_documento": tipos,
    })


@login_required
def abrir_documento_solicitacao(request, id, tipo):
    documento = get_object_or_404(DocumentoSolicitacao, pk=id)
    if tipo not in {"pdf", "arquivo"}:
        raise Http404("Tipo de documento inválido.")
    if not documento.arquivo:
        raise Http404("Arquivo não encontrado.")
    return FileResponse(documento.arquivo.open("rb"), content_type="application/pdf")


@login_required
def opos_geradas(request):
    anexos = (
        AnexoOPO.objects
        .select_related("solicitacao", "solicitacao__unidade", "solicitacao__municipio", "solicitacao__bairro")
        .order_by("-criado_em")
    )
    agrupados = {}
    for anexo in anexos:
        codigo = anexo.solicitacao.protocolo
        agrupados.setdefault(codigo, {"codigo": codigo, "solicitacao": anexo.solicitacao, "arquivos": []})
        agrupados[codigo]["arquivos"].append(anexo)
    return render(request, "gestao/opos_geradas.html", {"protocolos": list(agrupados.values())})


@login_required
def detalhe_opo(request, id):
    solicitacao = get_object_or_404(
        Solicitacao.objects.select_related("municipio", "bairro", "unidade", "tipo_evento"), pk=id
    )
    anexos = AnexoOPO.objects.filter(solicitacao=solicitacao).order_by("-criado_em")
    return render(request, "gestao/detalhe_opo.html", {"solicitacao": solicitacao, "anexos": anexos})


def _texto(valor, padrao=""):
    if valor is None:
        return padrao
    return str(valor).strip() or padrao


def _gerar_pdf_opo(request, solicitacao):
    """Gera a OPO diretamente com ReportLab, sem depender do WeasyPrint."""
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=1.8 * cm,
        leftMargin=1.8 * cm,
        topMargin=1.2 * cm,
        bottomMargin=1.2 * cm,
        title=f"OPO {solicitacao.protocolo}",
        author="SiEv - Polícia Militar da Bahia",
    )

    styles = getSampleStyleSheet()
    titulo = ParagraphStyle("OpoTitulo", parent=styles["Normal"], fontName="Helvetica-Bold", fontSize=15, leading=17, alignment=TA_CENTER, spaceAfter=3)
    subtitulo = ParagraphStyle("OpoSubtitulo", parent=styles["Normal"], fontName="Helvetica-Bold", fontSize=11, leading=13, alignment=TA_CENTER, spaceAfter=2)
    pequeno_centro = ParagraphStyle("OpoCentro", parent=styles["Normal"], fontName="Helvetica-Bold", fontSize=10, leading=12, alignment=TA_CENTER)
    numero = ParagraphStyle("OpoNumero", parent=styles["Normal"], fontName="Helvetica-Bold", fontSize=10, leading=12, alignment=TA_CENTER, spaceBefore=10, spaceAfter=13)
    intro = ParagraphStyle("OpoIntro", parent=styles["Normal"], fontName="Helvetica-Bold", fontSize=10, leading=12, alignment=TA_CENTER, spaceAfter=13)
    rotulo = ParagraphStyle("OpoRotulo", parent=styles["Normal"], fontName="Helvetica-Bold", fontSize=9.5, leading=11)
    valor = ParagraphStyle("OpoValor", parent=styles["Normal"], fontName="Helvetica", fontSize=9.5, leading=11)
    observacao = ParagraphStyle("OpoObservacao", parent=valor, spaceBefore=2, spaceAfter=5)
    rodape = ParagraphStyle("OpoRodape", parent=styles["Normal"], fontName="Helvetica", fontSize=8.5, leading=10, alignment=TA_CENTER, spaceBefore=12)

    story = []
    logo_path = finders.find("logos/logo_pmba.png")
    if logo_path:
        logo = Image(logo_path)
        logo.drawHeight = 1.8 * cm
        logo.drawWidth = 1.8 * cm
        logo.hAlign = "CENTER"
        story.extend([logo, Spacer(1, 0.15 * cm)])

    unidade = getattr(solicitacao, "unidade", None)
    unidade_nome = _texto(getattr(unidade, "sigla", None) or getattr(unidade, "nome", None), "UNIDADE NÃO DEFINIDA")
    municipio = _texto(getattr(getattr(solicitacao, "municipio", None), "nome", None), "")

    story.append(Paragraph("POLÍCIA MILITAR DA BAHIA", titulo))
    story.append(Paragraph("COMANDO DE OPERAÇÕES POLICIAIS MILITARES", subtitulo))
    story.append(Paragraph(escape(unidade_nome) + (f" - {escape(municipio)}" if municipio else ""), pequeno_centro))

    data_geracao = timezone.localtime()
    story.append(Paragraph(f"OPO Nº {escape(_texto(solicitacao.protocolo))} - {data_geracao.strftime('%d/%m/%Y')}", numero))
    story.append(Paragraph("RECOMENDO EXECUTARDES A SEGUINTE OPO:", intro))

    def P(texto, style=valor):
        return Paragraph(escape(_texto(texto, "-")), style)

    evento = _texto(solicitacao.nome_evento)
    local = _texto(solicitacao.local)
    data_evento = solicitacao.data_evento.strftime("%d/%m/%Y") if solicitacao.data_evento else "-"
    horario = "-"
    if solicitacao.hora_inicio and solicitacao.hora_fim:
        horario = f"{solicitacao.hora_inicio.strftime('%H:%M')} - {solicitacao.hora_fim.strftime('%H:%M')}"

    dados = [
        [P("EVENTO:", rotulo), P(evento)],
        [P("LOCAL:", rotulo), P(local)],
        [P("DATA:", rotulo), P(data_evento)],
        [P("HORÁRIO:", rotulo), P(horario)],
        [P("EFETIVO:", rotulo), P("01 (uma) Guarnição a critério do Coordenador de Área. Modalidade: Patrulhamento. Processo: Motorizado.")],
        [P("UNIFORME E ARMAMENTO:", rotulo), P("O de Dotação desta UOPM")],
        [P("SOLICITANTE:", rotulo), P(f"{_texto(solicitacao.solicitante)} {_texto(solicitacao.telefone)}".strip())],
    ]
    tabela = Table(dados, colWidths=[4.0 * cm, 12.8 * cm], hAlign="CENTER")
    tabela.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 3),
        ("TOPPADDING", (0, 0), (-1, -1), 2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    story.append(tabela)

    story.append(Spacer(1, 0.25 * cm))
    story.append(Paragraph("OBSERVAÇÕES:", rotulo))
    story.append(Paragraph("• O organizador do evento está ciente que caso haja perturbação do sossego, aglomeração ou outro tipo de infração, a guarnição adotará as medidas cabíveis.", observacao))
    story.append(Paragraph("• A viatura deve realizar Alfa 16 e no local, durante o evento.", observacao))
    story.append(Paragraph("• Constar o desenvolvimento desta OPO no relatório de serviço.", observacao))

    if _texto(solicitacao.observacoes):
        story.append(Paragraph("OBSERVAÇÃO DA SOLICITAÇÃO:", rotulo))
        story.append(Paragraph(escape(_texto(solicitacao.observacoes)).replace("\n", "<br/>"), observacao))

    story.append(Paragraph("Ordem de policiamento gerada pelo SiEv.", rodape))
    doc.build(story)
    return buffer.getvalue()


@login_required
def gerar_opo(request, id):
    solicitacao = get_object_or_404(Solicitacao, pk=id)
    if solicitacao.status not in {"APROVADA", "CONCLUIDA"}:
        messages.error(request, "A OPO somente pode ser gerada após a aprovação da solicitação.")
        return redirect("listar_pendentes_opo")

    conteudo = _gerar_pdf_opo(request, solicitacao)
    nome = f"OPO_{solicitacao.protocolo}.pdf"
    anexo = AnexoOPO(solicitacao=solicitacao, descricao="OPO gerada pelo SiEv")
    anexo.arquivo.save(nome, ContentFile(conteudo), save=True)

    HistoricoSolicitacao.objects.create(
        solicitacao=solicitacao,
        usuario=request.user,
        acao="OPO GERADA",
        observacao=f"Arquivo {nome} gerado pelo sistema.",
    )
    messages.success(request, "OPO gerada e arquivada no protocolo.")
    return redirect("detalhe_opo", id=id)


@login_required
def validar_matricula_opo_publica(request, id):
    solicitacao = get_object_or_404(Solicitacao, pk=id)
    if request.method == "POST":
        matricula = "".join((request.POST.get("matricula") or "").split())
        autorizado = MatriculaAutorizada.objects.filter(matricula=matricula, ativo=True).first()
        if autorizado:
            request.session[f"opo_autorizada_{id}"] = True
            return redirect("detalhe_opo_publica", id=id)
        messages.error(request, "Matrícula não autorizada para consulta desta OPO.")
    return render(request, "gestao/validar_matricula_opo.html", {"solicitacao": solicitacao})


def detalhe_opo_publica(request, id):
    if not request.session.get(f"opo_autorizada_{id}"):
        return redirect("validar_matricula_opo_publica", id=id)
    solicitacao = get_object_or_404(Solicitacao, pk=id)
    anexos = AnexoOPO.objects.filter(solicitacao=solicitacao).order_by("-criado_em")
    return render(request, "gestao/detalhe_opo_publica.html", {"solicitacao": solicitacao, "anexos": anexos})


@login_required
def importar_matriculas_painel(request):
    if request.method == "POST":
        arquivo = request.FILES.get("arquivo")
        if not arquivo:
            messages.error(request, "Selecione uma planilha Excel.")
            return redirect("importar_matriculas_painel")
        if arquivo.size > 5 * 1024 * 1024:
            messages.error(request, "A planilha deve ter no máximo 5 MB.")
            return redirect("importar_matriculas_painel")
        try:
            workbook = openpyxl.load_workbook(arquivo, read_only=True, data_only=True)
            sheet = workbook.active
            linhas = list(sheet.iter_rows(values_only=True))
            if not linhas:
                raise ValueError("A planilha está vazia.")
            def normalizar(valor):
                return "".join(ch for ch in str(valor or "").strip().lower() if ch.isalnum())
            cabecalho = {normalizar(v): i for i, v in enumerate(linhas[0])}
            mapa = {
                "matricula": ["matricula", "matrícula"],
                "nome": ["nome"],
                "posto": ["posto", "postograduacao", "posto/graduação"],
                "unidade": ["unidade", "sigla"],
            }
            indices = {}
            for campo, alternativas in mapa.items():
                for alternativa in alternativas:
                    chave = normalizar(alternativa)
                    if chave in cabecalho:
                        indices[campo] = cabecalho[chave]
                        break
            if "matricula" not in indices or "nome" not in indices:
                raise ValueError("A planilha precisa conter as colunas Matrícula e Nome.")
            inseridos = atualizados = 0
            for linha in linhas[1:]:
                matricula = str(linha[indices["matricula"]] or "").strip()
                nome = str(linha[indices["nome"]] or "").strip()
                if not matricula or not nome:
                    continue
                posto = str(linha[indices["posto"]] or "").strip() if "posto" in indices else ""
                unidade = str(linha[indices["unidade"]] or "").strip() if "unidade" in indices else ""
                obj, criado = MatriculaAutorizada.objects.update_or_create(
                    matricula=matricula,
                    defaults={"nome": nome, "posto": posto, "unidade": unidade, "ativo": True},
                )
                if criado:
                    inseridos += 1
                else:
                    atualizados += 1
            workbook.close()
            messages.success(request, f"Importação concluída: {inseridos} novas e {atualizados} atualizadas.")
        except Exception as exc:
            messages.error(request, f"Não foi possível importar a planilha: {exc}")
        return redirect("importar_matriculas_painel")
    total = MatriculaAutorizada.objects.filter(ativo=True).count()
    return render(request, "gestao/importar_matriculas.html", {"total_matriculas": total})


@login_required
def verificar_autenticidade(request, protocolo):
    solicitacao = get_object_or_404(Solicitacao, protocolo=protocolo)
    return render(request, "gestao/verificar_autenticidade.html", {"solicitacao": solicitacao})


@login_required
def alterar_status(request, id, status):
    solicitacao = get_object_or_404(Solicitacao, pk=id)
    permitidos = {"PENDENTE", "EM_ANALISE", "CORRECAO", "APROVADA", "REJEITADA", "CONCLUIDA"}
    if status not in permitidos:
        messages.error(request, "Status inválido.")
        return redirect("painel_gestao")
    solicitacao.status = status
    if status in {"APROVADA", "REJEITADA", "CONCLUIDA"}:
        solicitacao.data_aprovacao = timezone.now()
    solicitacao.save()
    HistoricoSolicitacao.objects.create(
        solicitacao=solicitacao,
        usuario=request.user,
        acao=f"STATUS: {status}",
        observacao="Alteração realizada pelo painel institucional.",
    )
    messages.success(request, "Status atualizado.")
    return redirect("painel_gestao")


@login_required
def mapa_eventos(request):
    eventos = (
        Solicitacao.objects
        .filter(data_evento__gte=timezone.localdate())
        .select_related("municipio", "bairro", "unidade")
        .order_by("data_evento", "hora_inicio")
    )
    return render(request, "gestao/mapa_eventos.html", {"eventos": eventos})


@login_required
def gerar_mapa_eventos_pdf(request):
    eventos = Solicitacao.objects.filter(data_evento__gte=timezone.localdate()).select_related("municipio", "bairro", "unidade").order_by("data_evento", "hora_inicio")
    response = HttpResponse(content_type="application/pdf")
    response["Content-Disposition"] = 'inline; filename="mapa_eventos.pdf"'
    doc = SimpleDocTemplate(response, pagesize=A4)
    styles = getSampleStyleSheet()
    rows = [["Data", "Hora", "Evento", "Município", "Unidade"]]
    for evento in eventos:
        rows.append([
            evento.data_evento.strftime("%d/%m/%Y"), evento.hora_inicio.strftime("%H:%M"),
            evento.nome_evento, evento.municipio.nome, evento.unidade.sigla if evento.unidade else "-",
        ])
    table = Table(rows, repeatRows=1)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#907C64")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.grey),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
    ]))
    doc.build([Paragraph("MAPA DE EVENTOS - SiEv", styles["Title"]), Spacer(1, 12), table])
    return response


@login_required
def importar_municipios(request):
    if request.method != "POST":
        return render(request, "gestao/importar_municipios.html")
    arquivo = request.FILES.get("arquivo")
    if not arquivo or arquivo.size > 5 * 1024 * 1024:
        messages.error(request, "Selecione um CSV de até 5 MB.")
        return redirect("importar_municipios")
    try:
        texto = arquivo.read().decode("utf-8-sig")
        leitor = csv.DictReader(io.StringIO(texto))
        total = 0
        for linha in leitor:
            nome = (linha.get("municipio") or linha.get("Município") or linha.get("nome") or "").strip()
            if nome:
                Municipio.objects.get_or_create(nome=nome, defaults={"ativo": True})
                total += 1
        messages.success(request, f"{total} municípios processados.")
    except Exception as exc:
        messages.error(request, f"Importação não realizada: {exc}")
    return redirect("importar_municipios")
