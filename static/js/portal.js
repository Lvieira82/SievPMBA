document.addEventListener("DOMContentLoaded", function () {

    const btnNova = document.getElementById("btnNovaInformacao");
    const area = document.getElementById("areaMunicipio");
    const pesquisa = document.getElementById("pesquisaMunicipio");
    const lista = document.getElementById("listaMunicipios");
    const municipioSelecionado = document.getElementById("municipioSelecionado");
    const btnContinuar = document.getElementById("btnContinuar");

    // Mostrar a área de pesquisa
    btnNova.addEventListener("click", function () {
        area.style.display = "block";
        pesquisa.focus();
    });

    // Pesquisar municípios
    pesquisa.addEventListener("input", function () {

        const termo = pesquisa.value.trim();

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

                        console.log(item);

                        pesquisa.value = item.nome;
                        municipioSelecionado.value = item.id;

                        console.log("Município selecionado:", municipioSelecionado.value);

                        lista.innerHTML = "";

                    });

                    lista.appendChild(opcao);

                });

            });

    });

    // Continuar
    btnContinuar.addEventListener("click", function () {

        console.log("Valor:", municipioSelecionado.value);

        if (!municipioSelecionado.value) {
            alert("Selecione um município.");
            return;
        }

        window.location.href =
            "/nova/?municipio=" + municipioSelecionado.value;

    });

});
