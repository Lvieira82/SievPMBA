from collections import defaultdict
from io import BytesIO

from django.db.models import Q
from django.http import HttpResponse

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from apps.solicitacoes.models import Solicitacao
from apps.solicitacoes.permissoes import escopo_unidades, pode_ver_ranking
from apps.solicitacoes.views.analise import _grupos_unidades, _marcar_percentual_tempo, _media_percentuais, _chave_ranking


def _base(request):
    unidades = escopo_unidades(request.user).order_by("nome")
    qs = Solicitacao.objects.select_related("unidade", "municipio").filter(unidade__in=unidades)
    unidade_id = request.GET.get("unidade")
    origem = request.GET.get("origem")
    inicio = request.GET.get("inicio")
    fim = request.GET.get("fim")
    if unidade_id:
        qs = qs.filter(unidade_id=unidade_id)
    if origem in {"EXTERNA", "MANUAL", "TRANSFERIDA"}:
        qs = qs.filter(origem=origem)
    if inicio:
        qs = qs.filter(data_evento__gte=inicio)
    if fim:
        qs = qs.filter(data_evento__lte=fim)
    unidades_relatorio = list(unidades.filter(pk=unidade_id)) if unidade_id else list(unidades)
    return qs, unidades_relatorio


def _cpr_ranking(grupos):
    por_cpr = {}
    for item in grupos:
        cpr = item["unidade"].cpr
        if not cpr:
            continue
        r = por_cpr.setdefault(cpr.id, {"cpr": cpr, "cumpridas": 0, "opo_total": 0, "tempo_total_horas": 0, "tempo_registros": 0})
        r["cumpridas"] += item["cumpridas"]
        r["opo_total"] += item["cumprimento_total"]
        r["tempo_total_horas"] += item["tempo_total_horas"]
        r["tempo_registros"] += item["tempo_registros"]
    out=[]
    for r in por_cpr.values():
        r["percentual"] = round(r["cumpridas"]*100/r["opo_total"],1) if r["opo_total"] else None
        r["media_horas"] = round(r["tempo_total_horas"]/r["tempo_registros"],2) if r["tempo_registros"] else None
        r["media_minutos"] = round(r["media_horas"]*60,1) if r["media_horas"] is not None else None
        out.append(r)
    return sorted(out,key=_chave_ranking,reverse=True)


def _pdf_response(filename, titulo, headers, rows, widths):
    response=HttpResponse(content_type="application/pdf")
    response["Content-Disposition"]=f'attachment; filename="{filename}"'
    doc=SimpleDocTemplate(response,pagesize=landscape(A4),rightMargin=10*mm,leftMargin=10*mm,topMargin=12*mm,bottomMargin=12*mm)
    styles=getSampleStyleSheet()
    titulo_style=ParagraphStyle("titulo",parent=styles["Title"],fontName="Helvetica-Bold",fontSize=16,leading=19,alignment=TA_CENTER,textColor=colors.HexColor("#4b5563"),spaceAfter=3)
    sub=ParagraphStyle("sub",parent=styles["Normal"],fontName="Helvetica-Bold",fontSize=10,leading=12,alignment=TA_CENTER,textColor=colors.HexColor("#4b5563"),spaceAfter=2)
    cel=ParagraphStyle("cel",parent=styles["Normal"],fontSize=8,leading=10)
    cab=ParagraphStyle("cab",parent=cel,fontName="Helvetica-Bold",textColor=colors.white,alignment=TA_CENTER)
    story=[Paragraph("POLÍCIA MILITAR DA BAHIA",titulo_style),Paragraph("COMANDO DE OPERAÇÕES POLICIAIS MILITARES",sub),Paragraph(titulo,sub),Spacer(1,5*mm)]
    data=[[Paragraph(str(h),cab) for h in headers]]
    for row in rows:data.append([Paragraph(str(v if v is not None else "—"),cel) for v in row])
    if len(data)==1:data.append([Paragraph("Nenhum dado encontrado.",cel)]+["" for _ in headers[1:]])
    t=Table(data,repeatRows=1,colWidths=widths)
    t.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,0),colors.HexColor("#4b5563")),("GRID",(0,0),(-1,-1),.4,colors.HexColor("#9ca3af")),("ROWBACKGROUNDS",(0,1),(-1,-1),[colors.white,colors.HexColor("#f3f4f6")]),("VALIGN",(0,0),(-1,-1),"MIDDLE"),("LEFTPADDING",(0,0),(-1,-1),4),("RIGHTPADDING",(0,0),(-1,-1),4),("TOPPADDING",(0,0),(-1,-1),5),("BOTTOMPADDING",(0,0),(-1,-1),5)]))
    story.append(t);doc.build(story);return response


def exportar_ranking(request, tipo):
    if not pode_ver_ranking(request.user):
        return HttpResponse("Acesso não autorizado.",status=403)
    qs, unidades = _base(request)
    grupos=_grupos_unidades(qs,unidades)
    if tipo == "cumprimento_unidades":
        grupos=sorted(grupos,key=_chave_ranking,reverse=True)
        rows=[[i,g["unidade"].sigla,g["unidade"].nome,g["cumprimento_total"],g["cumpridas"],f'{g["percentual"]:.1f}%' if g["percentual"] is not None else "—"] for i,g in enumerate(grupos,1)]
        return _pdf_response("ranking_opos_cumpridas_unidades.pdf","RANKING DE OPOs CUMPRIDAS POR UNIDADE",["POS.","SIGLA","UNIDADE","OPOs","CUMPRIDAS","PERCENTUAL"],rows,[16*mm,25*mm,85*mm,25*mm,30*mm,35*mm])
    if tipo == "tempo_unidades":
        grupos=[g for g in grupos if g["media_horas"] is not None];grupos=sorted(grupos,key=lambda g:g["media_horas"])
        rows=[[i,g["unidade"].sigla,g["unidade"].nome,f'{g["media_minutos"]} min',f'{g["media_horas"]} h',g["tempo_registros"]] for i,g in enumerate(grupos,1)]
        return _pdf_response("ranking_tempo_resposta_unidades.pdf","RANKING DE TEMPO MÉDIO DE RESPOSTA POR UNIDADE",["POS.","SIGLA","UNIDADE","MÉDIA MIN.","MÉDIA H.","RESPOSTAS"],rows,[16*mm,25*mm,85*mm,35*mm,30*mm,30*mm])
    ranking=_cpr_ranking(grupos)
    if tipo == "cumprimento_cpr":
        rows=[[i,g["cpr"].sigla,g["cpr"].nome,g["opo_total"],g["cumpridas"],f'{g["percentual"]:.1f}%' if g["percentual"] is not None else "—"] for i,g in enumerate(ranking,1)]
        return _pdf_response("ranking_opos_cumpridas_cpr.pdf","RANKING DE OPOs CUMPRIDAS POR CPR",["POS.","SIGLA","CPR","OPOs","CUMPRIDAS","PERCENTUAL"],rows,[16*mm,25*mm,85*mm,25*mm,30*mm,35*mm])
    ranking=[g for g in ranking if g["media_horas"] is not None];ranking=sorted(ranking,key=lambda g:g["media_horas"])
    rows=[[i,g["cpr"].sigla,g["cpr"].nome,f'{g["media_minutos"]} min',f'{g["media_horas"]} h',g["tempo_registros"]] for i,g in enumerate(ranking,1)]
    return _pdf_response("ranking_tempo_resposta_cpr.pdf","RANKING DE TEMPO MÉDIO DE RESPOSTA POR CPR",["POS.","SIGLA","CPR","MÉDIA MIN.","MÉDIA H.","RESPOSTAS"],rows,[16*mm,25*mm,85*mm,35*mm,30*mm,30*mm])
