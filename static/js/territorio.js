document.addEventListener("DOMContentLoaded", () => {
    const path = window.location.pathname;

    if (!path.startsWith("/nova/")) {
        return;
    }

    const params = new URLSearchParams(window.location.search);
    const municipioId = params.get("municipio");
    const form = document.querySelector("form");

    if (!municipioId || !form) {
        return;
    }

    const apiUrl = `/api/municipios/${encodeURIComponent(municipioId)}/bairros/`;

    fetch(apiUrl, {
        method: "GET",
        headers: {"Accept": "application/json"},
        credentials: "same-origin"
    })
        .then(response => {
            if (!response.ok) {
                throw new Error("Não foi possível carregar os bairros.");
            }
            return response.json();
        })
        .then(dados => montarDirecionamentoTerritorial(form, dados))
        .catch(() => {
            console.warn("SiEv: falha ao carregar o direcionamento territorial.");
        });
});

function montarDirecionamentoTerritorial(form, dados) {
    // Reaproveita o campo Bairro do formulário. Não cria um segundo seletor:
    // este é o campo submetido pelo Django e usado para carregar documentos da OPM.
    const existente = document.getElementById("id_bairro")
        || form.querySelector('select[name="bairro"]');

    // Atualiza o município visível, se já existir no template; caso contrário,
    // apenas adiciona o campo informativo, sem criar outro campo de bairro.
    let bloco = form.querySelector(".siev-territorio");
    if (!bloco) {
        bloco = document.createElement("div");
        bloco.className = "mb-3 siev-territorio";
        const titulo = document.createElement("label");
        titulo.className = "form-label fw-bold";
        titulo.textContent = "Município";
        const municipio = document.createElement("input");
        municipio.type = "text";
        municipio.className = "form-control";
        municipio.value = dados.municipio || "";
        municipio.readOnly = true;
        bloco.append(titulo, municipio);
        form.prepend(bloco);
    } else {
        const campoMunicipio = bloco.querySelector("input");
        if (campoMunicipio) campoMunicipio.value = dados.municipio || "";
    }

    if (!existente) {
        console.warn("SiEv: campo oficial de bairro não encontrado no formulário.");
        return;
    }

    // Remove opções antigas e preenche o mesmo campo com bairros válidos.
    const valorAnterior = existente.value;
    existente.replaceChildren();
    const vazio = document.createElement("option");
    vazio.value = "";
    vazio.textContent = "Selecione o bairro...";
    existente.appendChild(vazio);

    (dados.bairros || []).forEach(bairro => {
        const option = document.createElement("option");
        option.value = String(bairro.id);
        const unidades = (bairro.unidades || []).map(item => item.nome).join(" / ");
        option.textContent = unidades ? `${bairro.nome} — ${unidades}` : bairro.nome;
        existente.appendChild(option);
    });

    existente.required = Boolean(dados.multiplas_unidades);
    if (valorAnterior && Array.from(existente.options).some(option => option.value === valorAnterior)) {
        existente.value = valorAnterior;
    } else {
        existente.value = "";
    }
}
