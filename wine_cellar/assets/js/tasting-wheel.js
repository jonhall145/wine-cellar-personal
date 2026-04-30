document.addEventListener("DOMContentLoaded", function () {
    const FLAVOR_CATEGORIES = {
        fruit: ["Apple", "Citrus", "Berries", "Tropical", "Stone fruit", "Dried fruit"],
        floral: ["Floral", "Rose", "Violet", "Honeysuckle"],
        herbaceous: ["Herbaceous", "Grass", "Hay", "Mint", "Vegetal"],
        spice: ["Pepper", "Clove", "Cinnamon", "Nutmeg", "Licorice"],
        oak_earth: ["Oak", "Cedar", "Tobacco", "Leather", "Earthy", "Mineral"],
        body: ["Light", "Medium", "Full"],
        finish: ["Short", "Medium", "Long"],
    };

    const CATEGORY_LABELS = {
        fruit: "Fruit Notes",
        floral: "Floral Notes",
        herbaceous: "Herbaceous Notes",
        spice: "Spice Notes",
        oak_earth: "Oak, Earth & Leather",
        body: "Body",
        finish: "Finish Length",
    };

    function initTastingWheel() {
        const container = document.getElementById("taste-wheel-container");
        if (!container) return;

        const hiddenField = document.querySelector('input[name="taste_descriptors"]');
        const selectedDescriptors = hiddenField?.value ? JSON.parse(hiddenField.value) : [];

        // Build the wheel HTML
        let html = '<div class="tasting-wheel">';
        html += '<div class="tasting-wheel__categories">';

        Object.entries(FLAVOR_CATEGORIES).forEach(([categoryKey, options]) => {
            html += `<div class="tasting-wheel__category">`;
            html += `<label class="tasting-wheel__category-title">${CATEGORY_LABELS[categoryKey]}</label>`;
            html += `<div class="tasting-wheel__options">`;

            options.forEach((option) => {
                const id = `wheel-${categoryKey}-${option.toLowerCase().replace(/\s+/g, "-")}`;
                const isSelected = selectedDescriptors.includes(option);
                html += `<div class="tasting-wheel__option">`;
                html += `<input type="checkbox" id="${id}" value="${option}" ${isSelected ? "checked" : ""}>`;
                html += `<label for="${id}" class="tasting-wheel__option-label">${option}</label>`;
                html += `</div>`;
            });

            html += `</div></div>`;
        });

        html += "</div>";
        html += `<div class="tasting-wheel__selected-label" style="font-size: 0.9rem; color: #666; margin-bottom: 0.5rem;">Selected flavors:</div>`;
        html += '<div class="tasting-wheel__selected" id="taste-wheel-selected"></div>';
        html += "</div>";

        container.innerHTML = html;

        const checkboxes = container.querySelectorAll('input[type="checkbox"]');
        const selectedDisplay = document.getElementById("taste-wheel-selected");

        function updateSelectedDisplay() {
            const checked = Array.from(checkboxes)
                .filter((cb) => cb.checked)
                .map((cb) => cb.value);

            hiddenField.value = JSON.stringify(checked);

            selectedDisplay.innerHTML = checked
                .map(
                    (descriptor) =>
                        `<div class="tasting-wheel__selected-tag">
                         ${descriptor}
                         <button type="button" data-descriptor="${descriptor}" class="tasting-wheel__remove-tag">×</button>
                       </div>`
                )
                .join("");

            // Attach remove handlers
            selectedDisplay.querySelectorAll(".tasting-wheel__remove-tag").forEach((btn) => {
                btn.addEventListener("click", (e) => {
                    e.preventDefault();
                    const descriptor = btn.dataset.descriptor;
                    const checkbox = container.querySelector(`input[value="${descriptor}"]`);
                    if (checkbox) {
                        checkbox.checked = false;
                        updateSelectedDisplay();
                    }
                });
            });
        }

        checkboxes.forEach((checkbox) => {
            checkbox.addEventListener("change", updateSelectedDisplay);
        });

        updateSelectedDisplay();
    }

    initTastingWheel();
});
