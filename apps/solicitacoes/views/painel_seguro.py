from datetime import timedelta
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect,render
from django.utils import timezone
from apps.solicitacoes.models import Solicitacao
from apps.solicitacoes.permissoes import eh_desenvolvedor,escopo_unidades

@login_required
def painel_gestao_seguro(request):
    hoje=timezone.localdate()
    if eh_desenvolvedor(request.user):
        base=Solicitacao.objects.all();nivel="DESENVOLVEDOR";titulo="Administração do Sistema"
    else:
        unidades=escopo_unidades(request.user)
        if not unidades.exists():messages.error(request,"Usuário sem escopo institucional válido.");return redirect("login_gestao")
        base=Solicitacao.objects.filter(unidade__in=unidades);a=request.user.acesso_institucional;nivel=a.perfil;titulo=(str(a.unidade) if a.unidade_id else str(a.cpr) if a.cpr_id else a.get_perfil_display())
    return render(request,"gestao/painel_gestao.html",{"perfil":getattr(request.user,"acesso_institucional",None),"nivel":nivel,"titulo_painel":titulo,"pendentes_opo":base.filter(status="PENDENTE").count(),"eventos_semana":base.filter(data_evento__range=[hoje,hoje+timedelta(days=7)]).count(),"eventos_mes":base.filter(data_evento__year=hoje.year,data_evento__month=hoje.month).count(),"proximos_eventos":base.filter(data_evento__gte=hoje).order_by("data_evento","hora_inicio")[:5],"usuarios":request.user.__class__.objects.count()})
