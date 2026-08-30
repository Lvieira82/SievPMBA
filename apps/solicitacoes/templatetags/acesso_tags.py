from django import template

from apps.solicitacoes.models import CPR, Unidade

register = template.Library()


@register.simple_tag
def listar_cprs():
    return CPR.objects.all().order_by("sigla", "nome")


@register.simple_tag
def listar_unidades():
    return Unidade.objects.select_related("cpr").all().order_by("cpr__sigla", "sigla", "nome")
