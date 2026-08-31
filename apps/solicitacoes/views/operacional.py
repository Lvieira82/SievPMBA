from io import BytesIO

# ...

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
        if codigo not in agrupados:
            agrupados[codigo] = {
                "codigo": codigo,
                "solicitacao": anexo.solicitacao,
                "opo_recente": anexo,
            }
    return render(request, "gestao/opos_geradas.html", {"protocolos": list(agrupados.values())})
