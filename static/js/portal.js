document.addEventListener("DOMContentLoaded", function () {

    const btnNova = document.getElementById("btnNovaInformacao");
    const area = document.getElementById("areaMunicipio");
    const pesquisa = document.getElementById("pesquisaMunicipio");
    const lista = document.getElementById("listaMunicipios");
    const municipioSelecionado = document.getElementById("municipioSelecionado");
    const btnContinuar = document.getElementById("btnContinuar");

    let municipioAtual = null;

    function normalizarTexto(texto) {
        return (texto || "")
            .normalize("NFD")
            .replace(/[\u0300-\u036f]/g, "")
            .trim()
            .toLowerCase();
    }

    btnNova.addEventListener("click", function () {
        area.style.display = "block";
        pesquisa.focus();
    });

    pesquisa.addEventListener("input", function () {
        const termo = pesquisa.value.trim();
        municipioAtual = null;
        municipioSelecionado.value = "";

        if (termo.length < 2) {
            lista.innerHTML = "";
            return;
        }

        fetch("/api/municipios/?q=" + encodeURIComponent(termo), {
            headers: { "Accept": "application/json" }
        })
            .then(response => {
                if (!response.ok) throw new Error("HTTP " + response.status);
                return response.json();
            })
            .then(dados => {
                lista.innerHTML = "";

                dados.forEach(function (item) {
                    const opcao = document.createElement("button");
                    opcao.type = "button";
                    opcao.className = "list-group-item list-group-item-action";
                    opcao.textContent = item.nome;

                    opcao.addEventListener("click", function () {
                        pesquisa.value = item.nome;
                        municipioSelecionado.value = item.id;
                        municipioAtual = item;
                        lista.innerHTML = "";
                    });

                    lista.appendChild(opcao);
                });

                if (!dados.length) {
                    const vazio = document.createElement("div");
                    vazio.className = "list-group-item text-muted";
                    vazio.textContent = "Nenhum município encontrado.";
                    lista.appendChild(vazio);
                }
            })
            .catch(error => {
                console.error("Erro ao pesquisar municípios:", error);
                lista.innerHTML = "";
            });
    });

    btnContinuar.addEventListener("click", function () {
        if (!municipioSelecionado.value) {
            alert("Selecione um município.");
            return;
        }

        // O bairro NÃO é definido nesta etapa. O destino territorial é
        // informado dentro do formulário da nova solicitação.
        let url = "/nova/?municipio=" + encodeURIComponent(municipioSelecionado.value);
        window.location.href = url;
    });

});
