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
        let selectedDescriptors = [];
        if (hiddenField?.value) {
            try {
                const parsed = JSON.parse(hiddenField.value);
                selectedDescriptors = Array.isArray(parsed) ? parsed : [];
            } catch (_e) {
                selectedDescriptors = [];
            }
        }

        // Collect all known options so we can preserve unknown descriptors (e.g.
        // free-text values saved before this UI existed) instead of silently dropping them.
        const allKnownOptions = Object.values(FLAVOR_CATEGORIES).flat();
        const unknownDescriptors = selectedDescriptors.filter(
            (d) => !allKnownOptions.includes(d)
        );

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

            // Merge checkbox-backed selections with any descriptors unknown to
            // FLAVOR_CATEGORIES so they are never silently dropped on save.
            const all = [...checked, ...unknownDescriptors];
            hiddenField.value = JSON.stringify(all);

            // Clear and rebuild using safe DOM methods
            selectedDisplay.innerHTML = "";
            all.forEach((descriptor) => {
                const tag = document.createElement("div");
                tag.className = "tasting-wheel__selected-tag";

                const text = document.createElement("span");
                text.textContent = descriptor;
                tag.appendChild(text);

                const removeBtn = document.createElement("button");
                removeBtn.type = "button";
                removeBtn.className = "tasting-wheel__remove-tag";
                removeBtn.textContent = "×";
                removeBtn.dataset.descriptor = descriptor;
                removeBtn.addEventListener("click", (e) => {
                    e.preventDefault();
                    const checkbox = container.querySelector(`input[value="${descriptor}"]`);
                    if (checkbox) {
                        checkbox.checked = false;
                    } else {
                        // Unknown descriptor — remove from the preserved list
                        const idx = unknownDescriptors.indexOf(descriptor);
                        if (idx !== -1) unknownDescriptors.splice(idx, 1);
                    }
                    updateSelectedDisplay();
                });
                tag.appendChild(removeBtn);

                selectedDisplay.appendChild(tag);
            });
        }

        checkboxes.forEach((checkbox) => {
            checkbox.addEventListener("change", updateSelectedDisplay);
        });

        updateSelectedDisplay();
    }

    initTastingWheel();
});
