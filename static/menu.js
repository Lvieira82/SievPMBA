document.addEventListener("DOMContentLoaded", function(){

    const sidebar = document.querySelector(".sidebar");

    const botao = document.getElementById("toggleSidebar");

    botao.addEventListener("click", function(){

        if(window.innerWidth <= 991){

            sidebar.classList.toggle("show");

        }

        else{

            sidebar.classList.toggle("collapsed");

        }

    });

});