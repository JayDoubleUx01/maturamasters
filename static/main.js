document.addEventListener("DOMContentLoaded", () => {
    const typSelect = document.querySelector('select[name="typ_zadania"]');
    const answersSection = document.getElementById("answers-section");

    // ⛔ NIE JESTEŚMY NA STRONIE Z ZADANIAMI
    if (!typSelect || !answersSection) return;

    const answerInputs = answersSection.querySelectorAll("input");

    function updateAnswersVisibility() {
        if (typSelect.value === "otwarte") {
            answersSection.style.display = "none";
            answerInputs.forEach(input => input.value = "");
        } else {
            answersSection.style.display = "block";
        }
    }

    updateAnswersVisibility();
    typSelect.addEventListener("change", updateAnswersVisibility);
});

document.addEventListener("paste", (event) => {
    const items = event.clipboardData.items;

    for (let item of items) {
        if (item.type.startsWith("image")) {
            const file = item.getAsFile();
            const fileInput = document.getElementById("fileInput");

            const dataTransfer = new DataTransfer();
            dataTransfer.items.add(file);
            fileInput.files = dataTransfer.files;

            previewImage(file);
        }
    }
});

function previewImage(file) {
    const preview = document.getElementById("preview");
    preview.innerHTML = "";

    const img = document.createElement("img");
    img.src = URL.createObjectURL(file);
    preview.appendChild(img);
}

document.addEventListener("click", (e) => {
    const item = e.target.closest(".tree-item");
if (item) {
    item.classList.toggle("active");
}
});

// VIEW SWITCH
const switchButtons = document.querySelectorAll(".tasks-switch button");
const treeView = document.getElementById("treeView");
const listView = document.getElementById("listView");

switchButtons.forEach(btn => {
    btn.addEventListener("click", () => {
        switchButtons.forEach(b => b.classList.remove("active"));
        btn.classList.add("active");

        if (btn.dataset.view === "tree") {
            treeView.classList.add("view-active");
            listView.classList.remove("view-active");
        } else {
            listView.classList.add("view-active");
            treeView.classList.remove("view-active");
        }
    });
});