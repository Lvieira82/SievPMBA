from django.db import migrations


UNIDADES = [
    ("25º BPM/FEIRA DE SANTANA", "25º BPM/FEIRA DE SANTANA", "BPM"),
    ("64ª CIPM/FEIRA DE SANTANA", "64ª CIPM/FEIRA DE SANTANA", "CIPM"),
    ("65ª CIPM/FEIRA DE SANTANA", "65ª CIPM/FEIRA DE SANTANA", "CIPM"),
    ("67ª CIPM/FEIRA DE SANTANA", "67ª CIPM/FEIRA DE SANTANA", "CIPM"),
]


BAIRROS = [
    ("Queimadinha", "25º BPM/FEIRA DE SANTANA"),
    ("São João", "25º BPM/FEIRA DE SANTANA"),
    ("CASEB", "25º BPM/FEIRA DE SANTANA"),
    ("Lagoa Grande", "25º BPM/FEIRA DE SANTANA"),
    ("Parque Getulio Vargas", "25º BPM/FEIRA DE SANTANA"),
    ("Cidade Nova", "25º BPM/FEIRA DE SANTANA"),
    ("Parque Ipê", "25º BPM/FEIRA DE SANTANA"),
    ("Papagaio", "25º BPM/FEIRA DE SANTANA"),
    ("Mantiba", "25º BPM/FEIRA DE SANTANA"),
    ("Tiquaruçu", "25º BPM/FEIRA DE SANTANA"),
    ("Mangabeira", "25º BPM/FEIRA DE SANTANA"),
    ("Aeroporto", "25º BPM/FEIRA DE SANTANA"),
    ("Conceição", "25º BPM/FEIRA DE SANTANA"),
    ("Santo Antonio dos Prazeres", "25º BPM/FEIRA DE SANTANA"),
    ("SIM", "25º BPM/FEIRA DE SANTANA"),
    ("Registro", "25º BPM/FEIRA DE SANTANA"),
    ("Lagoa Salgada", "25º BPM/FEIRA DE SANTANA"),
    ("São Roque", "25º BPM/FEIRA DE SANTANA"),
    ("Subaé", "25º BPM/FEIRA DE SANTANA"),
    ("Santa Mônica II", "25º BPM/FEIRA DE SANTANA"),
    ("Chaparral", "25º BPM/FEIRA DE SANTANA"),
    ("Tomba", "67ª CIPM/FEIRA DE SANTANA"),
    ("CIS", "67ª CIPM/FEIRA DE SANTANA"),
    ("Aviário", "67ª CIPM/FEIRA DE SANTANA"),
    ("Parque Viver", "67ª CIPM/FEIRA DE SANTANA"),
    ("Panorama", "67ª CIPM/FEIRA DE SANTANA"),
    ("Fraternidade", "67ª CIPM/FEIRA DE SANTANA"),
    ("35º BI", "67ª CIPM/FEIRA DE SANTANA"),
    ("Viveiros", "67ª CIPM/FEIRA DE SANTANA"),
    ("Ipuaçu", "67ª CIPM/FEIRA DE SANTANA"),
    ("Humildes", "67ª CIPM/FEIRA DE SANTANA"),
    ("Limoeiro", "67ª CIPM/FEIRA DE SANTANA"),
    ("Parque Tamadari", "67ª CIPM/FEIRA DE SANTANA"),
    ("Olhos D`água", "67ª CIPM/FEIRA DE SANTANA"),
    ("Jardim Acácia", "67ª CIPM/FEIRA DE SANTANA"),
    ("Sítio Matias", "67ª CIPM/FEIRA DE SANTANA"),
    ("Chácara São Cosme", "67ª CIPM/FEIRA DE SANTANA"),
    ("Mochila", "67ª CIPM/FEIRA DE SANTANA"),
    ("Feira X", "67ª CIPM/FEIRA DE SANTANA"),
    ("Feira VII", "67ª CIPM/FEIRA DE SANTANA"),
    ("Caboronga", "67ª CIPM/FEIRA DE SANTANA"),
    ("Liberdade", "67ª CIPM/FEIRA DE SANTANA"),
    ("Santa Mônica", "64ª CIPM/FEIRA DE SANTANA"),
    ("Capuchinhos", "64ª CIPM/FEIRA DE SANTANA"),
    ("Ponto Central", "64ª CIPM/FEIRA DE SANTANA"),
    ("Centro", "64ª CIPM/FEIRA DE SANTANA"),
    ("Rua Nova", "64ª CIPM/FEIRA DE SANTANA"),
    ("Serraria Brasil", "64ª CIPM/FEIRA DE SANTANA"),
    ("Cruzeiro", "64ª CIPM/FEIRA DE SANTANA"),
    ("Tanque da Nação", "64ª CIPM/FEIRA DE SANTANA"),
    ("Baraúnas", "65ª CIPM/FEIRA DE SANTANA"),
    ("Sobradinho", "65ª CIPM/FEIRA DE SANTANA"),
    ("Jardim Cruzeiro", "65ª CIPM/FEIRA DE SANTANA"),
    ("Calumbi", "65ª CIPM/FEIRA DE SANTANA"),
    ("Pedra do Descanso", "65ª CIPM/FEIRA DE SANTANA"),
    ("Nova Esperança", "65ª CIPM/FEIRA DE SANTANA"),
    ("Gabriela", "65ª CIPM/FEIRA DE SANTANA"),
    ("Campo Limpo", "65ª CIPM/FEIRA DE SANTANA"),
    ("George Americo", "65ª CIPM/FEIRA DE SANTANA"),
    ("Campo do Gado Novo", "65ª CIPM/FEIRA DE SANTANA"),
    ("Sítio Novo", "65ª CIPM/FEIRA DE SANTANA"),
    ("Pampalona", "65ª CIPM/FEIRA DE SANTANA"),
    ("Pedra Ferrada", "65ª CIPM/FEIRA DE SANTANA"),
    ("Asa Branca", "65ª CIPM/FEIRA DE SANTANA"),
    ("UEFS", "65ª CIPM/FEIRA DE SANTANA"),
    ("Novo Horizonte", "65ª CIPM/FEIRA DE SANTANA"),
    ("Maria Quitéria", "65ª CIPM/FEIRA DE SANTANA"),
    ("São José", "65ª CIPM/FEIRA DE SANTANA"),
    ("Feira VI", "65ª CIPM/FEIRA DE SANTANA"),
]


def reparar_localizacao(apps, schema_editor):
    CPR = apps.get_model("solicitacoes", "CPR")
    Unidade = apps.get_model("solicitacoes", "Unidade")
    Municipio = apps.get_model("solicitacoes", "Municipio")
    Bairro = apps.get_model("solicitacoes", "Bairro")
    AreaResponsabilidade = apps.get_model("solicitacoes", "AreaResponsabilidade")

    cpr = CPR.objects.filter(sigla="CPR-L", ativo=True).first()
    if not cpr:
        return

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
        unidades[nome] = unidade

    unidade_municipio = unidades.get("64ª CIPM/FEIRA DE SANTANA")
    municipio, _ = Municipio.objects.get_or_create(
        nome="Feira de Santana",
        defaults={
            "ativo": True,
            "unidade_responsavel": unidade_municipio,
        },
    )

    for nome_bairro, nome_unidade in BAIRROS:
        unidade = unidades.get(nome_unidade)
        if not unidade:
            continue

        bairro, _ = Bairro.objects.get_or_create(
            municipio=municipio,
            nome=nome_bairro,
            defaults={"ativo": True},
        )

        AreaResponsabilidade.objects.get_or_create(
            bairro=bairro,
            unidade=unidade,
            defaults={"ativo": True},
        )


def desfazer_localizacao(apps, schema_editor):
    # Migration de reparo: não remove dados existentes no rollback.
    pass


class Migration(migrations.Migration):
    dependencies = [
        ("solicitacoes", "0012_adicionar_perfil_operador"),
    ]

    operations = [
        migrations.RunPython(reparar_localizacao, desfazer_localizacao),
    ]
