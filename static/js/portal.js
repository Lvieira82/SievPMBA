document.addEventListener("DOMContentLoaded", function () {

    const btnNova = document.getElementById("btnNovaInformacao");
    const area = document.getElementById("areaMunicipio");
    const pesquisa = document.getElementById("pesquisaMunicipio");
    const lista = document.getElementById("listaMunicipios");
    const municipioSelecionado = document.getElementById("municipioSelecionado");

    const areaBairro = document.getElementById("areaBairro");
    const pesquisaBairro = document.getElementById("pesquisaBairro");
    const bairroSelecionado = document.getElementById("bairroSelecionado");
    const listaBairros = document.getElementById("listaBairros");
    const bairroStatus = document.getElementById("bairroStatus");

    const btnContinuar = document.getElementById("btnContinuar");

    const municipiosComBairro = new Set([
        "feira de santana",
        "vitoria da conquista",
        "juazeiro",
        "salvador",
        "ilheus",
        "barreiras"
    ]);

    let municipioAtual = null;
    let bairrosAtuais = [];

    function normalizarTexto(texto) {
        return (texto || "")
            .normalize("NFD")
            .replace(/[\u0300-\u036f]/g, "")
            .trim()
            .toLowerCase();
    }

    function limparBairro() {
        bairrosAtuais = [];
        pesquisaBairro.value = "";
        bairroSelecionado.value = "";
        listaBairros.innerHTML = "";
        bairroStatus.textContent = "";
        bairroStatus.style.display = "none";
        areaBairro.style.display = "none";
    }

    function mostrarStatus(texto) {
        bairroStatus.textContent = texto;
        bairroStatus.style.display = texto ? "block" : "none";
    }

    function renderizarBairros(termo = "") {
        const filtro = normalizarTexto(termo);

        const bairrosFiltrados = filtro
            ? bairrosAtuais.filter(b => normalizarTexto(b.nome).includes(filtro))
            : bairrosAtuais;

        listaBairros.innerHTML = "";

        bairrosFiltrados.forEach(function (bairro) {
            const opcao = document.createElement("button");
            opcao.type = "button";
            opcao.className = "list-group-item list-group-item-action";
            opcao.textContent = bairro.nome;

            opcao.addEventListener("click", function () {
                pesquisaBairro.value = bairro.nome;
                bairroSelecionado.value = bairro.id;
                listaBairros.innerHTML = "";
            });

            listaBairros.appendChild(opcao);
        });

        if (filtro && bairrosFiltrados.length === 0) {
            const vazio = document.createElement("div");
            vazio.className = "list-group-item text-muted";
            vazio.textContent = "Nenhum bairro encontrado.";
            listaBairros.appendChild(vazio);
        }
    }

    function mostrarBairro() {
        areaBairro.style.display = "block";
        renderizarBairros();

        if (bairrosAtuais.length === 0) {
            mostrarStatus("Nenhum bairro/distrito está cadastrado para este município.");
        } else {
            mostrarStatus("Digite para filtrar ou role a lista para escolher.");
        }
    }

    function carregarBairros(municipio) {
        limparBairro();

        fetch("/api/municipios/" + municipio.id + "/bairros/", {
            headers: { "Accept": "application/json" }
        })
            .then(response => {
                if (!response.ok) {
                    throw new Error("HTTP " + response.status);
                }
                return response.json();
            })
            .then(dados => {
                bairrosAtuais = Array.isArray(dados.bairros) ? dados.bairros : [];

                const exigeBairro = municipiosComBairro.has(
                    normalizarTexto(municipio.nome)
                );

                if (exigeBairro) {
                    mostrarBairro();
                    pesquisaBairro.focus();
                } else {
                    const centro = bairrosAtuais.find(
                        bairro => normalizarTexto(bairro.nome) === "centro"
                    );

                    if (centro) {
                        bairroSelecionado.value = centro.id;
                        pesquisaBairro.value = centro.nome;
                    }

                    areaBairro.style.display = "none";
                }
            })
            .catch(error => {
                console.error("Erro ao carregar bairros:", error);

                const exigeBairro = municipiosComBairro.has(
                    normalizarTexto(municipio.nome)
                );

                if (exigeBairro) {
                    areaBairro.style.display = "block";
                    mostrarStatus("Não foi possível carregar os bairros. Verifique a API / banco de dados.");
                } else {
                    limparBairro();
                }
            });
    }

    btnNova.addEventListener("click", function () {
        area.style.display = "block";
        pesquisa.focus();
    });

    pesquisa.addEventListener("input", function () {
        const termo = pesquisa.value.trim();

        municipioAtual = null;
        municipioSelecionado.value = "";
        limparBairro();

        if (termo.length < 2) {
            lista.innerHTML = "";
            return;
        }

        fetch("/api/municipios/?q=" + encodeURIComponent(termo), {
            headers: { "Accept": "application/json" }
        })
            .then(r => {
                if (!r.ok) throw new Error("HTTP " + r.status);
                return r.json();
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
                        carregarBairros(item);
                    });

                    lista.appendChild(opcao);
                });
            })
            .catch(error => console.error("Erro ao pesquisar municípios:", error));
    });

    pesquisaBairro.addEventListener("focus", function () {
        renderizarBairros(pesquisaBairro.value);
    });

    pesquisaBairro.addEventListener("input", function () {
        bairroSelecionado.value = "";
        renderizarBairros(pesquisaBairro.value);
    });

    document.addEventListener("click", function (event) {
        if (!event.target.closest(".bairro-autocomplete")) {
            listaBairros.innerHTML = "";
        }
    });

    btnContinuar.addEventListener("click", function () {
        if (!municipioSelecionado.value) {
            alert("Selecione um município.");
            return;
        }

        const nomeMunicipio = municipioAtual ? municipioAtual.nome : pesquisa.value;
        const exigeBairro = municipiosComBairro.has(normalizarTexto(nomeMunicipio));
        const bairro = bairroSelecionado.value;

        if (exigeBairro && !bairro) {
            alert("Selecione um bairro ou distrito da lista.");
            pesquisaBairro.focus();
            renderizarBairros(pesquisaBairro.value);
            return;
        }

        let url = "/nova/?municipio=" + encodeURIComponent(municipioSelecionado.value);

        if (bairro) {
            url += "&bairro=" + encodeURIComponent(bairro);
        }

        window.location.href = url;
    });

});
