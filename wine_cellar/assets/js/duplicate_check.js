/**
 * Duplicate beverage detection for the add-wine / add-whisky forms.
 *
 * Looks for a hidden input with id="duplicate-check-url" that holds the
 * endpoint URL, then attaches a debounced listener to the name field
 * (id="id_name").  When the user pauses typing the handler calls the
 * endpoint and, if similar entries are found, reveals a warning banner
 * below the name field.
 */

document.addEventListener('DOMContentLoaded', function () {
    const urlInput = document.getElementById('duplicate-check-url');
    const nameField = document.getElementById('id_name');

    if (!urlInput || !nameField) return;

    const checkUrl = urlInput.value;
    let debounceTimer = null;

    // Create the warning container and insert it after the name field's parent
    const warning = document.createElement('div');
    warning.id = 'duplicate-warning';
    warning.className = 'duplicate-warning hidden';
    warning.setAttribute('role', 'alert');
    warning.setAttribute('aria-live', 'polite');

    // Insert after the name field wrapper (prefer a known form class, else direct parent)
    const nameWrapper = nameField.closest('.pure-control-group') || nameField.parentElement;
    nameWrapper.insertAdjacentElement('afterend', warning);

    function hideWarning() {
        warning.classList.add('hidden');
        warning.innerHTML = '';
    }

    function showWarning(items) {
        const links = items.map(function (item) {
            return '<a href="' + escapeHtml(item.url) + '" target="_blank" rel="noopener">' + escapeHtml(item.name) + '</a>';
        }).join(', ');

        warning.innerHTML =
            '<span class="duplicate-warning__icon"><i class="fa-solid fa-triangle-exclamation"></i></span> ' +
            '<span class="duplicate-warning__text">Similar ' + getBeverageLabel() + ' already ' +
            (items.length === 1 ? 'exists' : 'exist') + ': ' + links + '</span>';
        warning.classList.remove('hidden');
    }

    function getBeverageLabel() {
        return urlInput.dataset.beverageType || 'entry';
    }

    function escapeHtml(str) {
        return str
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;');
    }

    function checkDuplicates(name) {
        if (!name || name.length < 3) {
            hideWarning();
            return;
        }

        const url = checkUrl + '?name=' + encodeURIComponent(name);
        fetch(url, {
            method: 'GET',
            headers: { 'X-Requested-With': 'XMLHttpRequest' },
            credentials: 'same-origin',
        })
            .then(function (response) {
                if (!response.ok) {
                    throw new Error(response.status);
                }
                return response.json();
            })
            .then(function (data) {
                if (data.similar && data.similar.length > 0) {
                    showWarning(data.similar);
                } else {
                    hideWarning();
                }
            })
            .catch(function () {
                hideWarning();
            });
    }

    nameField.addEventListener('input', function () {
        clearTimeout(debounceTimer);
        const value = this.value.trim();
        debounceTimer = setTimeout(function () {
            checkDuplicates(value);
        }, 500);
    });
});
