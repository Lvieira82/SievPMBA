from django.contrib import messages
from django.shortcuts import redirect, render
from django.utils import timezone

from ..models import MatriculaAutorizada, PerfilUsuario, Solicitacao, Unidade


def eventos_dia(request):
    if request.method == "GET":
        return render(request, "solicitacoes/eventos_dia.html")

    matricula = request.POST.get("matricula", "").strip()

    if not matricula:
        return render(
            request,
            "solicitacoes/eventos_dia.html",
            {"erro": "Informe sua matrícula."},
        )

    matricula_autorizada = (
        MatriculaAutorizada.objects
        .filter(matricula=matricula, ativo=True)
        .first()
    )

    if not matricula_autorizada:
        return render(
            request,
            "solicitacoes/eventos_dia.html",
            {"erro": "Matrícula não autorizada."},
        )

    unidade = (
        Unidade.objects
        .filter(
            sigla=matricula_autorizada.unidade,
            ativo=True,
        )
        .select_related("cpr")
        .first()
    )

    if not unidade:
        return render(
            request,
            "solicitacoes/eventos_dia.html",
            {
                "erro": (
                    "A matrícula está cadastrada, mas a unidade vinculada "
                    "não foi localizada."
                )
            },
        )

    hoje = timezone.localdate()
    eventos = (
        Solicitacao.objects
        .filter(
            data_evento=hoje,
            status="APROVADA",
            unidade=unidade,
        )
        .select_related("municipio", "bairro", "unidade")
        .order_by("hora_inicio", "nome_evento")
    )

    request.session["eventos_matricula"] = matricula

    return render(
        request,
        "solicitacoes/eventos_dia_resultado.html",
        {
            "eventos": eventos,
            "matricula": matricula,
            "matricula_autorizada": matricula_autorizada,
            "unidade": unidade,
            "data": hoje,
        },
    )


def eventos_dia_resultado(request):
    matricula = request.session.get("eventos_matricula")

    if not matricula:
        return redirect("eventos_dia")

    perfil = (
        PerfilUsuario.objects
        .select_related("usuario", "unidade", "cpr")
        .filter(matricula=matricula, ativo=True)
        .first()
    )

    if not perfil:
        request.session.pop("eventos_matricula", None)
        messages.error(request, "Matrícula não autorizada.")
        return redirect("eventos_dia")

    hoje = timezone.localdate()
    eventos = (
        Solicitacao.objects
        .filter(data_evento=hoje, status="APROVADA")
        .select_related("municipio", "unidade", "bairro")
        .order_by("hora_inicio", "nome_evento")
    )

    if perfil.perfil == "UNIDADE":
        eventos = eventos.filter(unidade=perfil.unidade)
    elif perfil.perfil == "CPR":
        eventos = eventos.filter(unidade__cpr=perfil.cpr)
    elif perfil.perfil == "COPPM":
        pass
    else:
        eventos = eventos.none()

    return render(
        request,
        "solicitacoes/eventos_dia_resultado.html",
        {
            "eventos": eventos,
            "perfil": perfil,
            "data_eventos": hoje,
        },
    )
