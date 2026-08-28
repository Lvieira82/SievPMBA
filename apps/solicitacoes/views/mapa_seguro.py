from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.utils import timezone
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib import colors
from apps.solicitacoes.models import Solicitacao
from apps.solicitacoes.permissoes import escopo_unidades

@login_required
def gerar_mapa_eventos_pdf_seguro(request):
    eventos=Solicitacao.objects.filter(unidade__in=escopo_unidades(request.user),data_evento__gte=timezone.localdate()).select_related("municipio","unidade").order_by("data_evento","hora_inicio")
    response=HttpResponse(content_type="application/pdf"); response["Content-Disposition"]='inline; filename="mapa_eventos.pdf"'
    doc=SimpleDocTemplate(response,pagesize=A4); styles=getSampleStyleSheet(); rows=[["Data","Hora","Evento","Município","Unidade"]]
    for e in eventos: rows.append([e.data_evento.strftime("%d/%m/%Y"),e.hora_inicio.strftime("%H:%M"),e.nome_evento,e.municipio.nome,e.unidade.sigla if e.unidade else "-"])
    table=Table(rows,repeatRows=1); table.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,0),colors.HexColor("#907C64")),("TEXTCOLOR",(0,0),(-1,0),colors.white),("GRID",(0,0),(-1,-1),0.4,colors.grey),("FONTSIZE",(0,0),(-1,-1),8)]))
    doc.build([Paragraph("MAPA DE EVENTOS - SiEv",styles["Title"]),Spacer(1,12),table]); return response
