from django.db import migrations


COMANDOS = (
    ("CPE", "COMANDO DE POLICIAMENTO ESPECIALIZADO"),
    ("CPME", "COMANDO DE POLICIAMENTO EM MISSÕES ESPECIAIS"),
    ("CPRV", "COMANDO ESPECIALIZADO DE POLICIAMENTO RODOVIÁRIO"),
    ("CPAP", "COMANDO DE POLICIAMENTO DE APOIO OPERACIONAL"),
)


def incluir_comandos(apps, schema_editor):
    COPPM = apps.get_model("solicitacoes", "COPPM")
    CPR = apps.get_model("solicitacoes", "CPR")

    coppm = COPPM.objects.filter(ativo=True).order_by("id").first()
    if not coppm:
        coppm = COPPM.objects.order_by("id").first()
    if not coppm:
        coppm = COPPM.objects.create(
            nome="Comando de Operações da Polícia Militar",
            sigla="COPPM",
            ativo=True,
        )
    elif not coppm.ativo:
        coppm.ativo = True
        coppm.save(update_fields=["ativo"])

    for sigla, nome in COMANDOS:
        existente = CPR.objects.filter(sigla__iexact=sigla).first()
        if existente:
            if not existente.ativo:
                existente.ativo = True
                existente.save(update_fields=["ativo"])
            continue
        CPR.objects.create(coppm=coppm, sigla=sigla, nome=nome, ativo=True)


def manter_comandos(apps, schema_editor):
    # Não remove comandos na reversão para preservar eventual cadastro
    # de unidades, usuários e solicitações que tenha sido feito depois.
    pass


class Migration(migrations.Migration):
    dependencies = [
        ("solicitacoes", "0021_seed_tipos_evento_manual"),
    ]

    operations = [
        migrations.RunPython(incluir_comandos, manter_comandos),
    ]
