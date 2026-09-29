from django.db import migrations


COMANDOS = (
    ("CPE", "COMANDO DE POLICIAMENTO ESPECIALIZADO"),
    ("CPME", "COMANDO DE POLICIAMENTO EM MISSÕES ESPECIAIS"),
    ("CEPRV", "COMANDO ESPECIALIZADO DE POLICIAMENTO RODOVIÁRIO"),
    ("CPAp", "COMANDO DE POLICIAMENTO DE APOIO OPERACIONAL"),
)


UNIDADES = {
    "CEPRV": (
        ("BPRV", "BTL. DE POLÍCIA RODOVIÁRIA"),
        ("CIPRV - ITABUNA", "COMPANHIA INDEPENDENTE DE POLÍCIA RODOVIÁRIA"),
        ("CIPRV - BRUMADO", "COMPANHIA INDEPENDENTE DE POLÍCIA RODOVIÁRIA"),
        ("CIPRV - BARREIRAS", "COMPANHIA INDEPENDENTE DE POLÍCIA RODOVIÁRIA"),
        ("CIPRV - JUAZEIRO", "COMPANHIA INDEPENDENTE DE POLÍCIA RODOVIÁRIA"),
    ),
    "CPAp": (
        ("BPPM", "BTL. DE POLICIAMENTO DE PROTEÇÃO À MULHER"),
        ("BPFRC", "BTL. DE POLICIAMENTO DE PREVENÇÃO A FURTOS E ROUBOS A COLETIVOS"),
        ("BPFRV", "BTL. DE POLICIAMENTO DE PREVENÇÃO A FURTOS E ROUBOS DE VEÍCULOS"),
        ("BPEO", "BTL. DE POLÍCIA DE PRONTO EMPREGO OPERACIONAL"),
        ("BPESC", "BTL. DE POLICIAMENTO ESCOLAR"),
        ("BPTUR", "BTL. DE POLICIAMENTO TURÍSTICO"),
        ("BPGD", "BTL. DE POLÍCIA DE GUARDAS"),
        ("ESQ MCL", "ESQUADRÃO DE MOTOCICLISTAS - ÁGUIA"),
        ("CIPFAZ", "COMPANHIA INDEPENDENTE DE POLÍCIA FAZENDÁRIA"),
        ("CIMCAU", "COMPANHIA INDEPENDENTE DE MEDIAÇÃO DE CONFLITOS AGRÁRIOS E URBANOS"),
    ),
    "CPE": (
        ("BEPE", "BTL. ESPECIALIZADO DE POLICIAMENTO DE EVENTOS"),
        ("ESQDMONT - SALVADOR", "ESQUADRÃO DE POLÍCIA MONTADA"),
        ("ESQDMONT - FEIRA DE SANTANA", "ESQUADRÃO DE POLÍCIA MONTADA"),
        ("ESQDMONT - ITABUNA", "ESQUADRÃO DE POLÍCIA MONTADA"),
        ("COPPA", "COMPANHIA INDEPENDENTE DE POLÍCIA AMBIENTAL"),
        ("CIPPA LENÇÓIS", "COMPANHIA INDEPENDENTE DE POLÍCIA DE PROTEÇÃO AMBIENTAL"),
        ("CIPPA PORTO SEGURO", "COMPANHIA INDEPENDENTE DE POLÍCIA DE PROTEÇÃO AMBIENTAL"),
        ("CIPE - LESTE", "CIPE - LESTE"),
        ("CIPE - CAATINGA", "CIPE - CAATINGA"),
        ("CIPE - CHAPADA", "CIPE - CHAPADA"),
        ("CIPE - CERRADO", "CIPE - CERRADO"),
        ("CIPE - MATA ATLÂNTICA", "CIPE - MATA ATLÂNTICA"),
        ("CIPE - SEMIÁRIDO", "CIPE - SEMIÁRIDO"),
        ("CIPE - SUDOESTE", "CIPE - SUDOESTE"),
        ("CIPE - LITORAL NORTE", "CIPE - LITORAL NORTE"),
        ("CIPE - CACAUEIRA", "CIPE - CACAUEIRA"),
        ("CIPE - POLO INDUSTRIAL", "CIPE - POLO INDUSTRIAL"),
        ("CIPE - CENTRAL", "CIPE - CENTRAL"),
        ("CIPE - NORDESTE", "CIPE - NORDESTE"),
        ("CIPE - RECÔNCAVO", "CIPE - RECÔNCAVO"),
    ),
    "CPME": (
        ("BPCHQ", "BTL. DE POLÍCIA DE CHOQUE"),
        ("BOPE", "BTL. DE OPERAÇÕES POLICIAIS ESPECIAIS"),
        ("BPATAMO", "BTL. DE PATRULHAMENTO TÁTICO MÓVEL"),
        ("GRAER", "GRUPAMENTO AÉREO"),
    ),
}


def incluir_unidades(apps, schema_editor):
    COPPM = apps.get_model("solicitacoes", "COPPM")
    CPR = apps.get_model("solicitacoes", "CPR")
    Unidade = apps.get_model("solicitacoes", "Unidade")

    coppm = COPPM.objects.filter(ativo=True).order_by("id").first()
    if not coppm:
        coppm = COPPM.objects.order_by("id").first()
    if not coppm:
        coppm = COPPM.objects.create(
            nome="Comando de Operações da Polícia Militar",
            sigla="COPPM",
            ativo=True,
        )

    for sigla, nome in COMANDOS:
        comando = CPR.objects.filter(coppm=coppm, sigla__iexact=sigla).first()

        # Corrige a nomenclatura dos comandos especializados já criados
        # pela migration 0022, mantendo os mesmos registros e vínculos.
        if not comando and sigla == "CEPRV":
            comando = CPR.objects.filter(coppm=coppm, sigla__iexact="CPRV").first()
        if not comando and sigla == "CPAp":
            comando = CPR.objects.filter(coppm=coppm, sigla__iexact="CPAP").first()

        if comando:
            comando.sigla = sigla
            comando.nome = nome
            comando.ativo = True
            comando.save(update_fields=["sigla", "nome", "ativo"])
        else:
            comando = CPR.objects.create(
                coppm=coppm,
                sigla=sigla,
                nome=nome,
                ativo=True,
            )

        for unidade_sigla, unidade_nome in UNIDADES.get(sigla, ()):
            Unidade.objects.update_or_create(
                cpr=comando,
                sigla=unidade_sigla,
                defaults={
                    "nome": unidade_nome,
                    "tipo": "ESPECIALIZADA",
                    "ativo": True,
                },
            )


def manter_unidades(apps, schema_editor):
    # Preserva os cadastros na reversão para não remover unidades já utilizadas.
    pass


class Migration(migrations.Migration):
    dependencies = [
        ("solicitacoes", "0025_efetivo_institucional"),
    ]

    operations = [
        migrations.RunPython(incluir_unidades, manter_unidades),
    ]
