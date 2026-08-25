document.addEventListener("DOMContentLoaded", () => {
    const path = window.location.pathname;

    // O formulário de correção não deve alterar o direcionamento territorial.
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
        .then(dados => {
            montarDirecionamentoTerritorial(form, dados);
        })
        .catch(() => {
            console.warn("SiEv: falha ao carregar o direcionamento territorial.");
        });
});

function montarDirecionamentoTerritorial(form, dados) {
    const existente = document.getElementById("id_bairro");
    const bloco = document.createElement("div");
    bloco.className = "mb-3 siev-territorio";

    const titulo = document.createElement("label");
    titulo.className = "form-label fw-bold";
    titulo.textContent = "Município";

    const municipio = document.createElement("input");
    municipio.type = "text";
    municipio.className = "form-control";
    municipio.value = dados.municipio || "";
    municipio.readOnly = true;

    bloco.appendChild(titulo);
    bloco.appendChild(municipio);

    if (!dados.multiplas_unidades) {
        if (existente) {
            existente.closest(".mb-3, .form-group, .field-wrapper")?.remove();
        }
        form.prepend(bloco);
        return;
    }

    const label = document.createElement("label");
    label.className = "form-label fw-bold mt-3";
    label.setAttribute("for", "id_bairro");
    label.textContent = "Bairro";

    const select = existente || document.createElement("select");
    select.id = "id_bairro";
    select.name = "bairro";
    select.className = "form-select";
    select.required = true;

    const valorAnterior = select.value;
    select.innerHTML = "";

    const vazio = document.createElement("option");
    vazio.value = "";
    vazio.textContent = "Selecione o bairro...";
    select.appendChild(vazio);

    (dados.bairros || []).forEach(bairro => {
        const option = document.createElement("option");
        option.value = bairro.id;

        const unidades = (bairro.unidades || [])
            .map(item => item.nome)
            .join(" / ");

        option.textContent = unidades
            ? `${bairro.nome} — ${unidades}`
            : bairro.nome;

        if (String(bairro.id) === String(valorAnterior)) {
            option.selected = true;
        }

        select.appendChild(option);
    });

    bloco.appendChild(label);
    bloco.appendChild(select);

    if (existente) {
        existente.closest(".mb-3, .form-group, .field-wrapper")?.remove();
    }

    form.prepend(bloco);
}
