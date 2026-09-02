from django.db import migrations
import unicodedata


DADOS_TERRITORIAIS = [('Feira de Santana', 'Queimadinha', '25º BPM'),
 ('Feira de Santana', 'São João', '25º BPM'),
 ('Feira de Santana', 'Jaiba', '25º BPM'),
 ('Feira de Santana', 'Matinha', '25º BPM'),
 ('Feira de Santana', 'CASEB', '25º BPM'),
 ('Feira de Santana', 'Lagoa Grande', '25º BPM'),
 ('Feira de Santana', 'Parque Getulio Vargas', '25º BPM'),
 ('Feira de Santana', 'Cidade Nova', '25º BPM'),
 ('Feira de Santana', 'Parque Ipê', '25º BPM'),
 ('Feira de Santana', 'Papagaio', '25º BPM'),
 ('Feira de Santana', 'Mantiba', '25º BPM'),
 ('Feira de Santana', 'Tiquaruçu', '25º BPM'),
 ('Feira de Santana', 'Mangabeira', '25º BPM'),
 ('Feira de Santana', 'Aeroporto', '25º BPM'),
 ('Feira de Santana', 'Conceição', '25º BPM'),
 ('Feira de Santana', 'Santo Antonio dos Prazeres', '25º BPM'),
 ('Feira de Santana', 'SIM', '25º BPM'),
 ('Feira de Santana', 'Registro', '25º BPM'),
 ('Feira de Santana', 'Lagoa Salgada', '25º BPM'),
 ('Feira de Santana', 'São Roque', '25º BPM'),
 ('Feira de Santana', 'Subaé', '25º BPM'),
 ('Feira de Santana', 'Santa Mônica II', '25º BPM'),
 ('Feira de Santana', 'Chaparral', '25º BPM'),
 ('Feira de Santana', 'Santa Mônica', '64ª CIPM'),
 ('Feira de Santana', 'Capuchinhos', '64ª CIPM'),
 ('Feira de Santana', 'Ponto Central', '64ª CIPM'),
 ('Feira de Santana', 'Centro', '64ª CIPM'),
 ('Feira de Santana', 'Rua Nova', '64ª CIPM'),
 ('Feira de Santana', 'Serraria Brasil', '64ª CIPM'),
 ('Feira de Santana', 'Cruzeiro', '64ª CIPM'),
 ('Feira de Santana', 'Tanque da Nação', '64ª CIPM'),
 ('Feira de Santana', 'Baraúnas', '65ª CIPM'),
 ('Feira de Santana', 'Sobradinho', '65ª CIPM'),
 ('Feira de Santana', 'Jardim Cruzeiro', '65ª CIPM'),
 ('Feira de Santana', 'Calumbi', '65ª CIPM'),
 ('Feira de Santana', 'Pedra do Descanso', '65ª CIPM'),
 ('Feira de Santana', 'Nova Esperança', '65ª CIPM'),
 ('Feira de Santana', 'Gabriela', '65ª CIPM'),
 ('Feira de Santana', 'Campo Limpo', '65ª CIPM'),
 ('Feira de Santana', 'George Americo', '65ª CIPM'),
 ('Feira de Santana', 'Campo do Gado Novo', '65ª CIPM'),
 ('Feira de Santana', 'Sítio Novo', '65ª CIPM'),
 ('Feira de Santana', 'Pampalona', '65ª CIPM'),
 ('Feira de Santana', 'Pedra Ferrada', '65ª CIPM'),
 ('Feira de Santana', 'Asa Branca', '65ª CIPM'),
 ('Feira de Santana', 'UEFS', '65ª CIPM'),
 ('Feira de Santana', 'Novo Horizonte', '65ª CIPM'),
 ('Feira de Santana', 'Maria Quitéria', '65ª CIPM'),
 ('Feira de Santana', 'São José', '65ª CIPM'),
 ('Feira de Santana', 'Feira VI', '65ª CIPM'),
 ('Feira de Santana', 'Tomba', '67ª CIPM'),
 ('Feira de Santana', 'CIS', '67ª CIPM'),
 ('Feira de Santana', 'Aviário', '67ª CIPM'),
 ('Feira de Santana', 'Parque Viver', '67ª CIPM'),
 ('Feira de Santana', 'Panorama', '67ª CIPM'),
 ('Feira de Santana', 'Fraternidade', '67ª CIPM'),
 ('Feira de Santana', '35º BI', '67ª CIPM'),
 ('Feira de Santana', 'Viveiros', '67ª CIPM'),
 ('Feira de Santana', 'Ipuaçu', '67ª CIPM'),
 ('Feira de Santana', 'Humildes', '67ª CIPM'),
 ('Feira de Santana', 'Limoeiro', '67ª CIPM'),
 ('Feira de Santana', 'Parque Tamnadari', '67ª CIPM'),
 ('Feira de Santana', 'Olhos D`água', '67ª CIPM'),
 ('Feira de Santana', 'Jardim Acácia', '67ª CIPM'),
 ('Feira de Santana', 'Sítio MAtias', '67ª CIPM'),
 ('Feira de Santana', 'Chácara São Cosme', '67ª CIPM'),
 ('Feira de Santana', 'Mochila', '67ª CIPM'),
 ('Feira de Santana', 'Feira X', '67ª CIPM'),
 ('Feira de Santana', 'Feira VII', '67ª CIPM'),
 ('Feira de Santana', 'Caboronga', '67ª CIPM'),
 ('Feira de Santana', 'Liberdade', '67ª CIPM'),
 ('Ilhéus', 'Boa Vista', '68ª CIPM'),
 ('Ilhéus', 'Centro', '68ª CIPM'),
 ('Ilhéus', 'Cidade Nova', '68ª CIPM'),
 ('Ilhéus', 'Conquista', '68ª CIPM'),
 ('Ilhéus', 'Malhado', '68ª CIPM'),
 ('Ilhéus', 'Teresópolis', '68ª CIPM'),
 ('Ilhéus', 'São Sebastião', '68ª CIPM'),
 ('Ilhéus', 'Tapera', '68ª CIPM'),
 ('Ilhéus', 'Hernani Sá', '69ª CIPM'),
 ('Ilhéus', 'Ilhéus II', '69ª CIPM'),
 ('Ilhéus', 'Jardim Atlântico', '69ª CIPM'),
 ('Ilhéus', 'Nelson Costa', '69ª CIPM'),
 ('Ilhéus', 'Nossa Sra da Vitória', '69ª CIPM'),
 ('Ilhéus', 'Pontal', '69ª CIPM'),
 ('Ilhéus', 'São Francisco', '69ª CIPM'),
 ('Ilhéus', 'Olivença', '69ª CIPM'),
 ('Ilhéus', 'Coutos', '69ª CIPM'),
 ('Ilhéus', 'Santo Antônio', '69ª CIPM'),
 ('Ilhéus', 'Sapucaeira', '69ª CIPM'),
 ('Ilhéus', 'Areia Branca', '69ª CIPM'),
 ('Ilhéus', 'Rio do Engenho', '69ª CIPM'),
 ('Ilhéus', 'Acuípe', '69ª CIPM'),
 ('Ilhéus', 'Búzios', '69ª CIPM'),
 ('Ilhéus', 'Banco da Vitória', '70ª CIPM'),
 ('Ilhéus', 'Barra do Itaípe', '70ª CIPM'),
 ('Ilhéus', 'Basílio', '70ª CIPM'),
 ('Ilhéus', 'Esperança', '70ª CIPM'),
 ('Ilhéus', 'Iguape', '70ª CIPM'),
 ('Ilhéus', 'Jardim Savóia', '70ª CIPM'),
 ('Ilhéus', 'Salobrinho', '70ª CIPM'),
 ('Ilhéus', 'São Domingos', '70ª CIPM'),
 ('Ilhéus', 'São Miguel', '70ª CIPM'),
 ('Ilhéus', 'Teotônio Vilela', '70ª CIPM'),
 ('Ilhéus', 'Vila Cachoeira', '70ª CIPM'),
 ('Ilhéus', 'Vila Nazaré', '70ª CIPM'),
 ('Ilhéus', 'Aritaguá', '70ª CIPM'),
 ('Ilhéus', 'Banco Central', '70ª CIPM'),
 ('Ilhéus', 'Banco do Pedro', '70ª CIPM'),
 ('Ilhéus', 'Castelo Novo', '70ª CIPM'),
 ('Ilhéus', 'Inema', '70ª CIPM'),
 ('Ilhéus', 'Japu', '70ª CIPM'),
 ('Ilhéus', 'Pimenteira', '70ª CIPM'),
 ('Ilhéus', 'Sambaituba', '70ª CIPM'),
 ('Vitoria da Conquista', 'Distrito Industrial', '92ª CIPM'),
 ('Vitoria da Conquista', 'Lagoa das Flores', '92ª CIPM'),
 ('Vitoria da Conquista', 'Bate Pé', '92ª CIPM'),
 ('Vitoria da Conquista', 'Cercadinho', '92ª CIPM'),
 ('Vitoria da Conquista', 'Cabeceira do Jibóia', '92ª CIPM'),
 ('Vitoria da Conquista', 'Dantelândia', '92ª CIPM'),
 ('Vitoria da Conquista', 'Iguá', '92ª CIPM'),
 ('Vitoria da Conquista', 'Inhobim', '92ª CIPM'),
 ('Vitoria da Conquista', 'José Gonçalves', '92ª CIPM'),
 ('Vitoria da Conquista', 'Matinha', '92ª CIPM'),
 ('Vitoria da Conquista', 'Pradoso', '92ª CIPM'),
 ('Vitoria da Conquista', 'São Sebastião', '92ª CIPM'),
 ('Vitoria da Conquista', 'Veredinha', '92ª CIPM'),
 ('Vitoria da Conquista', 'Abelhas', '92ª CIPM'),
 ('Vitoria da Conquista', 'Caiçara', '92ª CIPM'),
 ('Vitoria da Conquista', 'Itaipu', '92ª CIPM'),
 ('Vitoria da Conquista', 'Itapirema', '92ª CIPM'),
 ('Vitoria da Conquista', 'Lagoa de Melquíades', '92ª CIPM'),
 ('Vitoria da Conquista', 'Lagoa José Luis', '92ª CIPM'),
 ('Vitoria da Conquista', 'São João da Vitória', '92ª CIPM'),
 ('Vitoria da Conquista', 'Agrovila 2', '92ª CIPM'),
 ('Vitoria da Conquista', 'Água Verde', '92ª CIPM'),
 ('Vitoria da Conquista', 'Alto da Choca', '92ª CIPM'),
 ('Vitoria da Conquista', 'Cedro Agrovila I', '92ª CIPM'),
 ('Vitoria da Conquista', 'Cedro Agrovila II', '92ª CIPM'),
 ('Vitoria da Conquista', 'Cedro Agrovila III', '92ª CIPM'),
 ('Vitoria da Conquista', 'Assentamento Cipo', '92ª CIPM'),
 ('Vitoria da Conquista', 'Assentamento Etelvina Campos', '92ª CIPM'),
 ('Vitoria da Conquista', 'Assentamento Faz Amaralina', '92ª CIPM'),
 ('Vitoria da Conquista', 'Assentamento Olho Dágua', '92ª CIPM'),
 ('Vitoria da Conquista', 'Assentamento União e Força', '92ª CIPM'),
 ('Vitoria da Conquista', 'Baixa da Porteira', '92ª CIPM'),
 ('Vitoria da Conquista', 'Baixão de Inhobim', '92ª CIPM'),
 ('Vitoria da Conquista', 'Barreiros', '92ª CIPM'),
 ('Vitoria da Conquista', 'Brinco', '92ª CIPM'),
 ('Vitoria da Conquista', 'Cabeceira', '92ª CIPM'),
 ('Vitoria da Conquista', 'Caldeirão', '92ª CIPM'),
 ('Vitoria da Conquista', 'Campinhos', '92ª CIPM'),
 ('Vitoria da Conquista', 'Campo Formoso', '92ª CIPM'),
 ('Vitoria da Conquista', 'Capinal', '92ª CIPM'),
 ('Vitoria da Conquista', 'Capinal II', '92ª CIPM'),
 ('Vitoria da Conquista', 'Conquista do Rio Pardo', '92ª CIPM'),
 ('Vitoria da Conquista', 'Corta Lote', '92ª CIPM'),
 ('Vitoria da Conquista', 'Estiva', '92ª CIPM'),
 ('Vitoria da Conquista', 'Furadinho', '92ª CIPM'),
 ('Vitoria da Conquista', 'Furado da Roseira', '92ª CIPM'),
 ('Vitoria da Conquista', 'Gameleira', '92ª CIPM'),
 ('Vitoria da Conquista', 'Jobóia', '92ª CIPM'),
 ('Vitoria da Conquista', 'Juazeiro', '92ª CIPM'),
 ('Vitoria da Conquista', 'Jurema', '92ª CIPM'),
 ('Vitoria da Conquista', 'Lagoa do Boi', '92ª CIPM'),
 ('Vitoria da Conquista', 'Lagoa do Xavier', '92ª CIPM'),
 ('Vitoria da Conquista', 'Lagoa José Luiz', '92ª CIPM'),
 ('Vitoria da Conquista', 'Lamarão', '92ª CIPM'),
 ('Vitoria da Conquista', 'Laranjeiras', '92ª CIPM'),
 ('Vitoria da Conquista', 'Limeira', '92ª CIPM'),
 ('Vitoria da Conquista', 'Malhada', '92ª CIPM'),
 ('Vitoria da Conquista', 'Mamão', '92ª CIPM'),
 ('Vitoria da Conquista', 'Mutum', '92ª CIPM'),
 ('Vitoria da Conquista', 'Pé de Galinha', '92ª CIPM'),
 ('Vitoria da Conquista', 'Pedra Branca', '92ª CIPM'),
 ('Vitoria da Conquista', 'Perequito', '92ª CIPM'),
 ('Vitoria da Conquista', 'Poco Verde', '92ª CIPM'),
 ('Vitoria da Conquista', 'Queimadas', '92ª CIPM'),
 ('Vitoria da Conquista', 'Rancho Alegre', '92ª CIPM'),
 ('Vitoria da Conquista', 'São Joaquim', '92ª CIPM'),
 ('Vitoria da Conquista', 'São Joaquim Barrocas', '92ª CIPM'),
 ('Vitoria da Conquista', 'Saquinho', '92ª CIPM'),
 ('Vitoria da Conquista', 'Serra do Marçal', '92ª CIPM'),
 ('Vitoria da Conquista', 'Simão', '92ª CIPM'),
 ('Vitoria da Conquista', 'Sossego', '92ª CIPM'),
 ('Vitoria da Conquista', 'Tabocas Bahiana', '92ª CIPM'),
 ('Vitoria da Conquista', 'Taboleiro Bahiana', '92ª CIPM'),
 ('Vitoria da Conquista', 'Tigre', '92ª CIPM'),
 ('Vitoria da Conquista', 'Umburana', '92ª CIPM'),
 ('Vitoria da Conquista', 'Vereda Grande', '92ª CIPM'),
 ('Vitoria da Conquista', 'Vereda Progresso', '92ª CIPM'),
 ('Vitoria da Conquista', 'Centro', '77ª CIPM'),
 ('Vitoria da Conquista', 'Sumare', '77ª CIPM'),
 ('Vitoria da Conquista', 'Iracema', '77ª CIPM'),
 ('Vitoria da Conquista', 'Guarani', '77ª CIPM'),
 ('Vitoria da Conquista', 'Cruzeiro', '77ª CIPM'),
 ('Vitoria da Conquista', 'Recreio', '77ª CIPM'),
 ('Vitoria da Conquista', 'Alto Maron', '77ª CIPM'),
 ('Vitoria da Conquista', 'Flamengo', '77ª CIPM'),
 ('Vitoria da Conquista', 'Santa Cecília', '77ª CIPM'),
 ('Vitoria da Conquista', 'Pedrinhas', '77ª CIPM'),
 ('Vitoria da Conquista', 'Panorama', '77ª CIPM'),
 ('Vitoria da Conquista', 'Candeias', '77ª CIPM'),
 ('Vitoria da Conquista', 'URBIS I', '77ª CIPM'),
 ('Vitoria da Conquista', 'Primavera', '77ª CIPM'),
 ('Vitoria da Conquista', 'Morada do Bem Querer', '77ª CIPM'),
 ('Vitoria da Conquista', 'Loteamento Universidade', '77ª CIPM'),
 ('Vitoria da Conquista', 'Jurema', '77ª CIPM'),
 ('Vitoria da Conquista', 'Jardim Guanabara', '77ª CIPM'),
 ('Vitoria da Conquista', 'Bela Vista', '77ª CIPM'),
 ('Vitoria da Conquista', 'Morada dos Pássaros', '77ª CIPM'),
 ('Vitoria da Conquista', 'Alto da Boa Vista', '77ª CIPM'),
 ('Vitoria da Conquista', 'Vila América', '77ª CIPM'),
 ('Vitoria da Conquista', 'URBIS VI', '77ª CIPM'),
 ('Vitoria da Conquista', 'Morada Real', '77ª CIPM'),
 ('Vitoria da Conquista', 'Renato Magalhães', '77ª CIPM'),
 ('Vitoria da Conquista', 'Vila Elisa', '77ª CIPM'),
 ('Vitoria da Conquista', 'Espírito Santo', '77ª CIPM'),
 ('Vitoria da Conquista', 'São Vicente', '77ª CIPM'),
 ('Vitoria da Conquista', 'Vila Bonita', '77ª CIPM'),
 ('Vitoria da Conquista', 'Bosque dos Pássaros', '77ª CIPM'),
 ('Vitoria da Conquista', 'Esplanada do Parque', '77ª CIPM'),
 ('Vitoria da Conquista', 'Ibirapuera', '78ª CIPM'),
 ('Vitoria da Conquista', 'Bairro Brasil', '78ª CIPM'),
 ('Vitoria da Conquista', 'Senhora Aparecida', '78ª CIPM'),
 ('Vitoria da Conquista', 'Bruno Bacelar', '78ª CIPM'),
 ('Vitoria da Conquista', 'Nenzinha Santos', '78ª CIPM'),
 ('Vitoria da Conquista', 'Bairro Alegria', '78ª CIPM'),
 ('Vitoria da Conquista', 'Santa Cruz', '78ª CIPM'),
 ('Vitoria da Conquista', 'Urbis II', '78ª CIPM'),
 ('Vitoria da Conquista', 'Urbis III', '78ª CIPM'),
 ('Vitoria da Conquista', 'Urbis IV', '78ª CIPM'),
 ('Vitoria da Conquista', 'Urbis V', '78ª CIPM'),
 ('Vitoria da Conquista', 'Cidade Maravilhosa', '78ª CIPM'),
 ('Vitoria da Conquista', 'Vila Serrana', '78ª CIPM'),
 ('Vitoria da Conquista', 'Kadija', '78ª CIPM'),
 ('Vitoria da Conquista', 'Patagônia', '78ª CIPM'),
 ('Vitoria da Conquista', 'Ipanema', '78ª CIPM'),
 ('Vitoria da Conquista', 'Patagônia 2', '78ª CIPM'),
 ('Vitoria da Conquista', 'Campinho', '78ª CIPM'),
 ('Vitoria da Conquista', 'Santa Helena', '78ª CIPM'),
 ('Vitoria da Conquista', 'Loteamento Conquistense', '78ª CIPM'),
 ('Vitoria da Conquista', 'Senhorinha Cairo', '78ª CIPM'),
 ('Vitoria da Conquista', 'Conveima I', '78ª CIPM'),
 ('Vitoria da Conquista', 'Conveima II', '78ª CIPM'),
 ('Vitoria da Conquista', 'Conveima III', '78ª CIPM'),
 ('Vitoria da Conquista', 'Morada Nova', '78ª CIPM'),
 ('Vitoria da Conquista', 'Cidade Modelo', '78ª CIPM'),
 ('Vitoria da Conquista', 'Urbis V', '78ª CIPM'),
 ('Vitoria da Conquista', 'Ibirapuera', '78ª CIPM'),
 ('Vitoria da Conquista', 'Bairro Brasil', '78ª CIPM'),
 ('Vitoria da Conquista', 'Senhora Aparecida', '78ª CIPM'),
 ('Vitoria da Conquista', 'Bruno Bacelar', '78ª CIPM'),
 ('Vitoria da Conquista', 'Nenzinha Santos', '78ª CIPM'),
 ('Vitoria da Conquista', 'Bairro Alegria', '78ª CIPM'),
 ('Vitoria da Conquista', 'Santa Cruz', '78ª CIPM'),
 ('Vitoria da Conquista', 'Urbis II', '78ª CIPM'),
 ('Vitoria da Conquista', 'Urbis III', '78ª CIPM'),
 ('Vitoria da Conquista', 'Urbis IV', '78ª CIPM'),
 ('Vitoria da Conquista', 'Urbis V', '78ª CIPM'),
 ('Vitoria da Conquista', 'Cidade Maravilhosa', '78ª CIPM'),
 ('Vitoria da Conquista', 'Vila Serrana', '78ª CIPM'),
 ('Vitoria da Conquista', 'Kadija', '78ª CIPM'),
 ('Vitoria da Conquista', 'Patagônia', '78ª CIPM'),
 ('Vitoria da Conquista', 'Ipanema', '78ª CIPM'),
 ('Vitoria da Conquista', 'Patagônia 2', '78ª CIPM'),
 ('Vitoria da Conquista', 'Campinho', '78ª CIPM'),
 ('Vitoria da Conquista', 'Santa Helena', '78ª CIPM'),
 ('Vitoria da Conquista', 'Loteamento Conquistense', '78ª CIPM'),
 ('Vitoria da Conquista', 'Senhorinha Cairo', '78ª CIPM'),
 ('Vitoria da Conquista', 'Conveima I', '78ª CIPM'),
 ('Vitoria da Conquista', 'Conveima II', '78ª CIPM'),
 ('Vitoria da Conquista', 'Conveima III', '78ª CIPM'),
 ('Vitoria da Conquista', 'Morada Nova', '78ª CIPM'),
 ('Vitoria da Conquista', 'Cidade Modelo', '78ª CIPM'),
 ('Vitoria da Conquista', 'Alvorada', '78ª CIPM'),
 ('Vitoria da Conquista', 'Bateias', '78ª CIPM'),
 ('Vitoria da Conquista', 'Cidade Serrana', '78ª CIPM'),
 ('Vitoria da Conquista', 'Henrique Prates', '78ª CIPM')]


CPR_POR_UNIDADE = {
    "25º BPM": "CPR-L",
    "64ª CIPM": "CPR-L",
    "65ª CIPM": "CPR-L",
    "67ª CIPM": "CPR-L",
    "68ª CIPM": "CPR-S",
    "69ª CIPM": "CPR-S",
    "70ª CIPM": "CPR-S",
    "77ª CIPM": "CPR-SO",
    "78ª CIPM": "CPR-SO",
    "92ª CIPM": "CPR-SO",
}


def normalizar(valor):
    texto = str(valor or "").strip().upper()
    texto = unicodedata.normalize("NFKD", texto)
    return "".join(c for c in texto if not unicodedata.combining(c))


def chave_unidade(valor):
    return normalizar(valor).split("/", 1)[0].strip()


def executar(apps, schema_editor):
    COPPM = apps.get_model("solicitacoes", "COPPM")
    CPR = apps.get_model("solicitacoes", "CPR")
    Unidade = apps.get_model("solicitacoes", "Unidade")
    Municipio = apps.get_model("solicitacoes", "Municipio")
    Bairro = apps.get_model("solicitacoes", "Bairro")
    AreaResponsabilidade = apps.get_model("solicitacoes", "AreaResponsabilidade")

    coppm = COPPM.objects.filter(sigla__iexact="COPPM").first()
    if not coppm:
        coppm = COPPM.objects.create(
            sigla="COPPM",
            nome="Comando de Operações Policiais Militares",
            ativo=True,
        )

    municipios = {normalizar(m.nome): m for m in Municipio.objects.all()}

    unidades = {}
    for unidade in Unidade.objects.filter(ativo=True):
        for candidato in (
            unidade.sigla,
            unidade.nome,
            chave_unidade(unidade.sigla),
            chave_unidade(unidade.nome),
        ):
            chave = normalizar(candidato)
            if chave:
                unidades.setdefault(chave, unidade)

    for municipio_nome, bairro_nome, unidade_nome in DADOS_TERRITORIAIS:
        municipio = municipios.get(normalizar(municipio_nome))
        if not municipio:
            continue

        unidade = unidades.get(normalizar(unidade_nome))
        if not unidade:
            unidade = unidades.get(chave_unidade(unidade_nome))

        if not unidade:
            cpr_sigla = CPR_POR_UNIDADE.get(chave_unidade(unidade_nome))
            if not cpr_sigla:
                continue

            cpr = CPR.objects.filter(sigla__iexact=cpr_sigla).first()
            if not cpr:
                cpr = CPR.objects.create(
                    sigla=cpr_sigla,
                    nome=cpr_sigla,
                    coppm=coppm,
                    ativo=True,
                )

            unidade = Unidade.objects.create(
                cpr=cpr,
                nome=unidade_nome,
                sigla=unidade_nome,
                tipo="BPM" if "BPM" in unidade_nome.upper() else "CIPM",
                telefone="",
                email="",
                ativo=True,
            )

            for candidato in (
                unidade.sigla,
                unidade.nome,
                chave_unidade(unidade.sigla),
                chave_unidade(unidade.nome),
            ):
                chave = normalizar(candidato)
                if chave:
                    unidades.setdefault(chave, unidade)

        bairro, _ = Bairro.objects.get_or_create(
            municipio=municipio,
            nome=bairro_nome,
            defaults={"ativo": True},
        )

        AreaResponsabilidade.objects.get_or_create(
            bairro=bairro,
            unidade=unidade,
            defaults={"ativo": True},
        )


def desfazer(apps, schema_editor):
    pass


class Migration(migrations.Migration):
    dependencies = [
        ("solicitacoes", "0011_migrar_perfis_existentes_para_acesso"),
    ]

    operations = [
        migrations.RunPython(executar, desfazer),
    ]
