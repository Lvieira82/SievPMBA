import re
from datetime import datetime
from io import BytesIO

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.shortcuts import redirect, render
from django.utils import timezone

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer

from apps.solicitacoes.models import HistoricoSolicitacao, Unidade
from apps.solicitacoes.permissoes import perfil_gestor

MARCADOR_ENVIO = "PESQUISA DE SATISFAÇÃO ENVIADA"
MARCADOR_RESPOSTA = "PESQUISA RESPONDIDA"


def _extrair_resposta(observacao):
    texto = observacao or ""
    nota = None
    comentario = ""
    match = re.search(r"Nota:\s*(\d+)\s*/\s*5", texto, re.I)
    if match:
        valor = int(match.group(1))
        if 1 <= valor <= 5:
            nota = valor
    match = re.search(r"Comentário:\s*(.*)$", texto, re.I | re.S)
    if match:
        comentario = match.group(1).strip()
        if comentario.lower() == "sem comentário.":
            comentario = ""
    return nota, comentario


def _ranking(registros, chave):
    grupos = {}
    for item in registros:
        if not item["respondida"] or item["nota"] is None:
            continue
        entidade = chave(item["solicitacao"])
        if entidade is None:
            continue
        key = entidade.id
        g = grupos.setdefault(key, {"entidade": entidade, "notas": [], "respondidas": 0})
        g["notas"].append(item["nota"])
        g["respondidas"] += 1
    resultado = []
    for g in grupos.values():
        media = sum(g["notas"]) / len(g["notas"]) if g["notas"] else 0
        resultado.append({
            "entidade": g["entidade"],
            "respondidas": g["respondidas"],
            "media": round(media, 2),
            "satisfacao": round(media / 5 * 100, 1) if media else 0,
        })
    return sorted(resultado, key=lambda x: (-x["media"], -x["respondidas"], str(x["entidade"])))


def _pdf_ranking(request, ranking_cpr, ranking_unidade):
    response = HttpResponse(content_type="application/pdf")
    response["Content-Disposition"] = 'attachment; filename="ranking_pesquisas_satisfacao.pdf"'
    doc = SimpleDocTemplate(response, pagesize=landscape(A4), rightMargin=10*mm, leftMargin=10*mm, topMargin=12*mm, bottomMargin=12*mm)
    styles = getSampleStyleSheet()
    titulo = ParagraphStyle("titulo", parent=styles["Title"], fontName="Helvetica-Bold", fontSize=16, alignment=TA_CENTER, textColor=colors.HexColor("#4b5563"))
    sub = ParagraphStyle("sub", parent=styles["Normal"], fontName="Helvetica-Bold", fontSize=10, alignment=TA_CENTER, textColor=colors.HexColor("#4b5563"), spaceAfter=4)
    cel = ParagraphStyle("cel", parent=styles["Normal"], fontSize=8)
    cab = ParagraphStyle("cab", parent=cel, fontName="Helvetica-Bold", textColor=colors.white, alignment=TA_CENTER)
    story = [Paragraph("POLÍCIA MILITAR DA BAHIA", titulo), Paragraph("COMANDO DE OPERAÇÕES POLICIAIS MILITARES", sub), Paragraph("RANKING DE PESQUISAS DE SATISFAÇÃO", sub), Spacer(1, 4*mm)]
    def tabela(titulo_secao, ranking):
        rows = [[Paragraph("POS.", cab), Paragraph(titulo_secao, cab), Paragraph("RESPONDIDAS", cab), Paragraph("MÉDIA", cab), Paragraph("SATISFAÇÃO", cab)]]
        for pos, item in enumerate(ranking, 1):
            ent = item["entidade"]
            nome = getattr(ent, "nome", str(ent))
            sigla = getattr(ent, "sigla", "")
            exibicao = f"{sigla} — {nome}" if sigla else nome
            rows.append([Paragraph(str(pos), cel), Paragraph(exibicao, cel), Paragraph(str(item["respondidas"]), cel), Paragraph(f"{item['media']:.2f}/5", cel), Paragraph(f"{item['satisfacao']:.1f}%", cel)])
        if len(rows) == 1:
            rows.append([Paragraph("Nenhum dado", cel), "", "", "", ""])
        t = Table(rows, repeatRows=1, colWidths=[18*mm, 105*mm, 35*mm, 30*mm, 35*mm])
        t.setStyle(TableStyle([("BACKGROUND", (0,0), (-1,0), colors.HexColor("#4b5563")), ("GRID", (0,0), (-1,-1), .4, colors.HexColor("#9ca3af")), ("ROWBACKGROUNDS", (0,1), (-1,-1), [colors.white, colors.HexColor("#f3f4f6")]), ("VALIGN", (0,0), (-1,-1), "MIDDLE"), ("LEFTPADDING", (0,0), (-1,-1), 4), ("RIGHTPADDING", (0,0), (-1,-1), 4), ("TOPPADDING", (0,0), (-1,-1), 5), ("BOTTOMPADDING", (0,0), (-1,-1), 5)]))
        return t
    story.append(Paragraph("RANKING POR CPR", sub)); story.append(tabela("CPR", ranking_cpr)); story.append(Spacer(1, 6*mm)); story.append(Paragraph("RANKING POR UNIDADE", sub)); story.append(tabela("UNIDADE", ranking_unidade))
    doc.build(story)
    return response


@login_required
def painel_pesquisas(request):
    if not perfil_gestor(request.user, "COPPM"):
        messages.error(request, "Somente o Gestor COPPM pode acessar o painel de pesquisas.")
        return redirect("painel_gestao")

    inicio = request.GET.get("inicio", "")
    fim = request.GET.get("fim", "")
    unidade_id = request.GET.get("unidade", "")
    cpr_id = request.GET.get("cpr", "")

    base = HistoricoSolicitacao.objects.filter(acao__in=[MARCADOR_ENVIO, MARCADOR_RESPOSTA]).select_related("solicitacao", "solicitacao__unidade", "solicitacao__unidade__cpr")
    if inicio:
        try: base = base.filter(solicitacao__data_evento__gte=datetime.strptime(inicio, "%Y-%m-%d").date())
        except ValueError: inicio = ""
    if fim:
        try: base = base.filter(solicitacao__data_evento__lte=datetime.strptime(fim, "%Y-%m-%d").date())
        except ValueError: fim = ""
    if unidade_id:
        try: base = base.filter(solicitacao__unidade_id=int(unidade_id))
        except (TypeError, ValueError): unidade_id = ""
    if cpr_id:
        try: base = base.filter(solicitacao__unidade__cpr_id=int(cpr_id))
        except (TypeError, ValueError): cpr_id = ""

    envios = list(base.filter(acao=MARCADOR_ENVIO).order_by("-criado_em"))
    respostas = list(base.filter(acao=MARCADOR_RESPOSTA).order_by("-criado_em"))
    resposta_por_solicitacao = {}
    for item in respostas: resposta_por_solicitacao.setdefault(item.solicitacao_id, item)

    registros=[]; notas=[]; distribuicao={1:0,2:0,3:0,4:0,5:0}; comentarios=[]
    for envio in envios:
        resposta=resposta_por_solicitacao.get(envio.solicitacao_id); nota=comentario=None; respondida_em=None
        if resposta:
            nota,comentario=_extrair_resposta(resposta.observacao); respondida_em=resposta.criado_em
            if nota: notas.append(nota); distribuicao[nota]+=1
            if comentario: comentarios.append({"nome":resposta.solicitacao.solicitante,"evento":resposta.solicitacao.nome_evento,"comentario":comentario,"data":resposta.criado_em,"nota":nota})
        registros.append({"solicitacao":envio.solicitacao,"enviado_em":envio.criado_em,"respondida":bool(resposta),"nota":nota,"respondida_em":respondida_em})

    ranking_cpr=_ranking(registros,lambda s:getattr(s.unidade,"cpr",None)); ranking_unidade=_ranking(registros,lambda s:s.unidade)
    total_enviadas=len(envios); total_respondidas=sum(1 for envio in envios if envio.solicitacao_id in resposta_por_solicitacao); total_pendentes=max(0,total_enviadas-total_respondidas); total_avaliacoes=len(notas)
    participacao=(total_respondidas/total_enviadas*100) if total_enviadas else 0; media=(sum(notas)/total_avaliacoes) if total_avaliacoes else 0; satisfacao=(media/5*100) if media else 0

    if request.GET.get("export") == "pdf":
        return _pdf_ranking(request, ranking_cpr, ranking_unidade)

    return render(request,"gestao/pesquisas.html",{
        "total_enviadas":total_enviadas,"total_respondidas":total_respondidas,"total_pendentes":total_pendentes,"total_avaliacoes":total_avaliacoes,"participacao":round(participacao,1),"media":round(media,2),"satisfacao":round(satisfacao,1),"distribuicao":distribuicao,"comentarios":comentarios[:30],"registros":registros,"unidades":Unidade.objects.filter(ativo=True).select_related("cpr").order_by("sigla"),"cprs":sorted({u.cpr for u in Unidade.objects.filter(ativo=True).select_related("cpr") if u.cpr},key=lambda x:x.sigla),"ranking_cpr":ranking_cpr,"ranking_unidade":ranking_unidade,"inicio":inicio,"fim":fim,"unidade_id":unidade_id,"cpr_id":cpr_id,"ultima_atualizacao":timezone.localtime(),
    })
