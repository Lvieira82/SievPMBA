from django.db import migrations


UNIDADES = [
    ("25ª BPM/FEIRA DE SANTANA", "25ª BPM/FEIRA DE SANTANA", "BPM"),
    ("67ª CIPM/FEIRA DE SANTANA", "67ª CIPM/FEIRA DE SANTANA", "CIPM"),
    ("64ª CIPM/FEIRA DE SANTANA", "64ª CIPM/FEIRA DE SANTANA", "CIPM"),
    ("65ª CIPM/FEIRA DE SANTANA", "65ª CIPM/FEIRA DE SANTANA", "CIPM"),
]

BAIRROS = {
    "25ª BPM/FEIRA DE SANTANA": [
        "Queimadinha", "São João", "CASEB", "Lagoa Grande",
        "Parque Getulio Vargas", "Cidade Nova", "Parque Ipê", "Papagaio",
        "Mantiba", "Tiquaruçu", "Mangabeira", "Aeroporto", "Conceição",
        "Santo Antonio dos Prazeres", "SIM", "Registro", "Lagoa Salgada",
        "São Roque", "Subaé", "Santa Mônica II", "Chaparral",
    ],
    "67ª CIPM/FEIRA DE SANTANA": [
        "Tomba", "CIS", "Aviário", "Parque Viver", "Panorama", "Fraternidade",
        "35º BI", "Viveiros", "Ipuaçu", "Humildes", "Limoeiro", "Parque Tamandari",
        "Olhos D`água", "Jardim Acácia", "Sítio Matias", "Chácara São Cosme",
        "Mochila", "Feira X", "Feira VII", "Caboronga", "Liberdade",
    ],
    "64ª CIPM/FEIRA DE SANTANA": [
        "Santa Mônica", "Capuchinhos", "Ponto Central", "Centro", "Rua Nova",
        "Serraria Brasil", "Cruzeiro", "Tanque da Nação",
    ],
    "65ª CIPM/FEIRA DE SANTANA": [
        "Baraúnas", "Sobradinho", "Jardim Cruzeiro", "Calumbi", "Pedra do Descanso",
        "Nova Esperança", "Gabriela", "Campo Limpo", "George Americo",
        "Campo do Gado Novo", "Sítio Novo", "Pampalona", "Pedra Ferrada",
        "Asa Branca", "UEFS", "Novo Horizonte", "Maria Quitéria", "São José", "Feira VI",
    ],
}


def cadastrar(apps, schema_editor):
    COPPM = apps.get_model("solicitacoes", "COPPM")
    CPR = apps.get_model("solicitacoes", "CPR")
    Unidade = apps.get_model("solicitacoes", "Unidade")
    Municipio = apps.get_model("solicitacoes", "Municipio")
    Bairro = apps.get_model("solicitacoes", "Bairro")
    AreaResponsabilidade = apps.get_model("solicitacoes", "AreaResponsabilidade")

    coppm, _ = COPPM.objects.get_or_create(
        sigla="COPPM",
        defaults={"nome": "Comando de Operações Policiais Militares", "ativo": True},
    )

    cpr, _ = CPR.objects.get_or_create(
        sigla="CPR-L",
        defaults={"nome": "Comando de Policiamento Regional Leste", "coppm": coppm, "ativo": True},
    )

    # Garante o vínculo caso o CPR já existisse.
    if cpr.coppm_id != coppm.id:
        cpr.coppm_id = coppm.id
        cpr.save(update_fields=["coppm"])

    unidades = {}
    for nome, sigla, tipo in UNIDADES:
        unidade, _ = Unidade.objects.get_or_create(
            nome=nome,
            defaults={
                "cpr": cpr,
                "sigla": sigla,
                "tipo": tipo,
                "telefone": "",
                "email": "",
                "ativo": True,
            },
        )
        # Corrige registros existentes que possam estar incompletos.
        alterados = []
        if unidade.cpr_id != cpr.id:
            unidade.cpr_id = cpr.id
            alterados.append("cpr")
        if not unidade.ativo:
            unidade.ativo = True
            alterados.append("ativo")
        if alterados:
            unidade.save(update_fields=alterados)
        unidades[nome] = unidade

    municipio, _ = Municipio.objects.get_or_create(
        nome="Feira de Santana",
        defaults={"ibge": "2910800", "ativo": True},
    )
    if not municipio.ativo:
        municipio.ativo = True
        municipio.save(update_fields=["ativo"])

    # A responsabilidade municipal padrão fica no 25º BPM.
    bpm = unidades["25ª BPM/FEIRA DE SANTANA"]
    if municipio.unidade_responsavel_id is None:
        municipio.unidade_responsavel_id = bpm.id
        municipio.save(update_fields=["unidade_responsavel"])

    for nome_unidade, nomes_bairros in BAIRROS.items():
        unidade = unidades[nome_unidade]
        for nome_bairro in nomes_bairros:
            bairro, _ = Bairro.objects.get_or_create(
                municipio=municipio,
                nome=nome_bairro,
                defaults={"ativo": True},
            )
            if not bairro.ativo:
                bairro.ativo = True
                bairro.save(update_fields=["ativo"])
            AreaResponsabilidade.objects.get_or_create(
                bairro=bairro,
                unidade=unidade,
                defaults={"ativo": True},
            )


def remover(apps, schema_editor):
    # Esta migration é de correção/seed e não deve apagar dados existentes no rollback.
    pass


class Migration(migrations.Migration):
    dependencies = [
        ("solicitacoes", "0012_adicionar_perfil_operador"),
    ]

    operations = [
        migrations.RunPython(cadastrar, remover),
    ]
