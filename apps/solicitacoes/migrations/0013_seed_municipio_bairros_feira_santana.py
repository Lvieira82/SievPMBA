from django.db import migrations


BAIRROS = [
    ("Queimadinha", "25º BPM"),
    ("São João", "25º BPM"),
    ("CASEB", "25º BPM"),
    ("Lagoa Grande", "25º BPM"),
    ("Parque Getulio Vargas", "25º BPM"),
    ("Cidade Nova", "25º BPM"),
    ("Parque Ipê", "25º BPM"),
    ("Papagaio", "25º BPM"),
    ("Mantiba", "25º BPM"),
    ("Tiquaruçu", "25º BPM"),
    ("Mangabeira", "25º BPM"),
    ("Aeroporto", "25º BPM"),
    ("Conceição", "25º BPM"),
    ("Santo Antonio dos Prazeres", "25º BPM"),
    ("SIM", "25º BPM"),
    ("Registro", "25º BPM"),
    ("Lagoa Salgada", "25º BPM"),
    ("São Roque", "25º BPM"),
    ("Subaé", "25º BPM"),
    ("Santa Mônica II", "25º BPM"),
    ("Chaparral", "25º BPM"),
    ("Tomba", "67ª CIPM"),
    ("CIS", "67ª CIPM"),
    ("Aviário", "67ª CIPM"),
    ("Parque Viver", "67ª CIPM"),
    ("Panorama", "67ª CIPM"),
    ("Fraternidade", "67ª CIPM"),
    ("35º BI", "67ª CIPM"),
    ("Viveiros", "67ª CIPM"),
    ("Ipuaçu", "67ª CIPM"),
    ("Humildes", "67ª CIPM"),
    ("Limoeiro", "67ª CIPM"),
    ("Parque Tamandari", "67ª CIPM"),
    ("Olhos D'Água", "67ª CIPM"),
    ("Jardim Acácia", "67ª CIPM"),
    ("Sítio Matias", "67ª CIPM"),
    ("Chácara São Cosme", "67ª CIPM"),
    ("Mochila", "67ª CIPM"),
    ("Feira X", "67ª CIPM"),
    ("Feira VII", "67ª CIPM"),
    ("Caboronga", "67ª CIPM"),
    ("Liberdade", "67ª CIPM"),
    ("Santa Mônica", "64ª CIPM"),
    ("Capuchinhos", "64ª CIPM"),
    ("Ponto Central", "64ª CIPM"),
    ("Centro", "64ª CIPM"),
    ("Rua Nova", "64ª CIPM"),
    ("Serraria Brasil", "64ª CIPM"),
    ("Cruzeiro", "64ª CIPM"),
    ("Tanque da Nação", "64ª CIPM"),
    ("Baraúnas", "65ª CIPM"),
    ("Sobradinho", "65ª CIPM"),
    ("Jardim Cruzeiro", "65ª CIPM"),
    ("Calumbi", "65ª CIPM"),
    ("Pedra do Descanso", "65ª CIPM"),
    ("Nova Esperança", "65ª CIPM"),
    ("Gabriela", "65ª CIPM"),
    ("Campo Limpo", "65ª CIPM"),
    ("George Américo", "65ª CIPM"),
    ("Campo do Gado Novo", "65ª CIPM"),
    ("Sítio Novo", "65ª CIPM"),
    ("Pampalona", "65ª CIPM"),
    ("Pedra Ferrada", "65ª CIPM"),
    ("Asa Branca", "65ª CIPM"),
    ("UEFS", "65ª CIPM"),
    ("Novo Horizonte", "65ª CIPM"),
    ("Maria Quitéria", "65ª CIPM"),
    ("São José", "65ª CIPM"),
    ("Feira VI", "65ª CIPM"),
]


def cadastrar(apps, schema_editor):
    Municipio = apps.get_model("solicitacoes", "Municipio")
    Bairro = apps.get_model("solicitacoes", "Bairro")
    Unidade = apps.get_model("solicitacoes", "Unidade")
    AreaResponsabilidade = apps.get_model("solicitacoes", "AreaResponsabilidade")

    municipio, _ = Municipio.objects.get_or_create(
        nome="Feira de Santana",
        defaults={"ativo": True},
    )

    for nome_bairro, prefixo in BAIRROS:
        unidade = Unidade.objects.filter(
            nome__startswith=prefixo,
            ativo=True,
        ).first()
        if unidade is None:
            unidade = Unidade.objects.filter(
                sigla__startswith=prefixo,
                ativo=True,
            ).first()
        if unidade is None:
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


def remover(apps, schema_editor):
    Municipio = apps.get_model("solicitacoes", "Municipio")
    Bairro = apps.get_model("solicitacoes", "Bairro")
    AreaResponsabilidade = apps.get_model("solicitacoes", "AreaResponsabilidade")

    municipio = Municipio.objects.filter(nome="Feira de Santana").first()
    if not municipio:
        return

    nomes = [nome for nome, _ in BAIRROS]
    bairros = Bairro.objects.filter(municipio=municipio, nome__in=nomes)
    AreaResponsabilidade.objects.filter(bairro__in=bairros).delete()
    bairros.delete()
    if not municipio.bairros.exists():
        municipio.delete()


class Migration(migrations.Migration):
    dependencies = [
        ("solicitacoes", "0012_adicionar_perfil_operador"),
    ]

    operations = [
        migrations.RunPython(cadastrar, remover),
    ]
