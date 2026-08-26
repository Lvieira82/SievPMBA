document.addEventListener("DOMContentLoaded", function () {
    const sidebar = document.getElementById("sidebar");
    const toggle = document.getElementById("toggleSidebar");

    if (!sidebar || !toggle) {
        return;
    }

    toggle.addEventListener("click", function () {
        if (window.innerWidth <= 991) {
            sidebar.classList.toggle("show");
        } else {
            sidebar.classList.toggle("collapsed");
        }
    });

    document.querySelectorAll(".sidebar .menu a").forEach(function (link) {
        link.addEventListener("click", function () {
            if (window.innerWidth <= 991) {
                sidebar.classList.remove("show");
            }
        });
    });
});
