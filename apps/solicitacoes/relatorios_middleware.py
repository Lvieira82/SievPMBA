from django.utils.deprecation import MiddlewareMixin


class RelatoriosRankingMiddleware(MiddlewareMixin):
    def process_request(self, request):
        if request.method != "GET":
            return None
        export = request.GET.get("export")
        if request.path == "/gestao/analise/" and export in {"cumprimento_unidades", "cumprimento_cpr", "tempo_unidades", "tempo_cpr"}:
            from apps.solicitacoes.relatorio_ranking import exportar_ranking
            return exportar_ranking(request, export)
        return None
