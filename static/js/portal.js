document.addEventListener("DOMContentLoaded", function () {

    const btnNova = document.getElementById("btnNovaInformacao");
    const area = document.getElementById("areaMunicipio");
    const pesquisa = document.getElementById("pesquisaMunicipio");
    const lista = document.getElementById("listaMunicipios");
    const municipioSelecionado = document.getElementById("municipioSelecionado");
    const areaBairro = document.getElementById("areaBairro");
    const bairroSelecionado = document.getElementById("bairroSelecionado");
    const btnContinuar = document.getElementById("btnContinuar");

    // Municípios que exigem escolha de bairro/distrito já no portal inicial.
    const municipiosComBairro = new Set([
        "feira de santana",
        "vitoria da conquista",
        "vitória da conquista",
        "juazeiro",
        "salvador",
        "ilheus",
        "ilhéus",
        "barreiras"
    ]);

    let municipioAtual = null;

    function normalizarTexto(texto) {
        return (texto || "")
            .normalize("NFD")
            .replace(/[\u0300-\u036f]/g, "")
            .trim()
            .toLowerCase();
    }

    function limparBairro() {
        bairroSelecionado.innerHTML = "";
        bairroSelecionado.disabled = true;
        areaBairro.style.display = "none";
    }

    function mostrarBairro() {
        areaBairro.style.display = "block";
        bairroSelecionado.disabled = false;
    }

    function carregarBairros(municipio) {
        limparBairro();

        fetch("/api/municipios/" + municipio.id + "/bairros/")
            .then(response => {
                if (!response.ok) {
                    throw new Error("Não foi possível carregar os bairros.");
                }
                return response.json();
            })
            .then(dados => {
                bairroSelecionado.innerHTML = "";

                const placeholder = document.createElement("option");
                placeholder.value = "";
                placeholder.textContent = "Selecione o bairro/distrito...";
                placeholder.disabled = true;
                placeholder.selected = true;
                bairroSelecionado.appendChild(placeholder);

                (dados.bairros || []).forEach(function (bairro) {
                    const opcao = document.createElement("option");
                    opcao.value = bairro.id;
                    opcao.textContent = bairro.nome;
                    bairroSelecionado.appendChild(opcao);
                });

                mostrarBairro();

                // Para os demais municípios, o padrão é Centro e o campo não aparece.
                if (!municipiosComBairro.has(normalizarTexto(municipio.nome))) {
                    const centro = (dados.bairros || []).find(
                        bairro => normalizarTexto(bairro.nome) === "centro"
                    );

                    if (centro) {
                        bairroSelecionado.value = centro.id;
                    } else {
                        bairroSelecionado.value = "";
                    }

                    areaBairro.style.display = "none";
                }
            })
            .catch(error => {
                console.error(error);
                limparBairro();
            });
    }

    // Mostrar a área de pesquisa
    btnNova.addEventListener("click", function () {
        area.style.display = "block";
        pesquisa.focus();
    });

    // Pesquisar municípios
    pesquisa.addEventListener("input", function () {

        const termo = pesquisa.value.trim();
        municipioAtual = null;
        municipioSelecionado.value = "";
        limparBairro();

        if (termo.length < 2) {
            lista.innerHTML = "";
            return;
        }

        fetch("/api/municipios/?q=" + encodeURIComponent(termo))
            .then(r => r.json())
            .then(dados => {

                lista.innerHTML = "";

                dados.forEach(function (item) {

                    const opcao = document.createElement("a");

                    opcao.href = "#";
                    opcao.className = "list-group-item list-group-item-action";
                    opcao.textContent = item.nome;

                    opcao.addEventListener("click", function (e) {

                        e.preventDefault();

                        pesquisa.value = item.nome;
                        municipioSelecionado.value = item.id;
                        municipioAtual = item;
                        lista.innerHTML = "";

                        carregarBairros(item);
                    });

                    lista.appendChild(opcao);
                });
            })
            .catch(error => {
                console.error("Erro ao pesquisar municípios:", error);
            });
    });

    // Continuar
    btnContinuar.addEventListener("click", function () {

        if (!municipioSelecionado.value) {
            alert("Selecione um município.");
            return;
        }

        const nomeMunicipio = municipioAtual ? municipioAtual.nome : pesquisa.value;
        const exigeBairro = municipiosComBairro.has(normalizarTexto(nomeMunicipio));
        const bairro = bairroSelecionado.value;

        if (exigeBairro && !bairro) {
            alert("Selecione o bairro ou distrito.");
            bairroSelecionado.focus();
            return;
        }

        let url = "/nova/?municipio=" + encodeURIComponent(municipioSelecionado.value);

        if (bairro) {
            url += "&bairro=" + encodeURIComponent(bairro);
        }

        window.location.href = url;
    });

});
