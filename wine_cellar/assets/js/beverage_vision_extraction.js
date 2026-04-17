/**
 * Vision extraction AJAX handler for beverage creation forms.
 */

document.addEventListener('DOMContentLoaded', function () {
    const configElement = document.getElementById('vision-extraction-config');
    const extractButton = document.querySelector('button[name="extract_vision"]');
    const form = document.querySelector('.wine-form');

    if (!configElement || !extractButton || !form) return;

    let config;
    try {
        config = JSON.parse(configElement.textContent);
    } catch (error) {
        console.error('Vision extraction config error:', error);
        return;
    }

    const originalButtonHtml = extractButton.innerHTML;
    const createFields = config.createFields || [];
    const fkNameFields = config.fkNameFields || {};
    const fieldMap = config.fieldMap || {};
    const confidenceFieldMap = config.confidenceFieldMap || {};

    initScannedImageHandlers();

    extractButton.addEventListener('click', function (event) {
        event.preventDefault();

        const formData = new FormData();
        const imageFields = ['image_front_label', 'image_back_label', 'image_front', 'image_back'];
        let hasImages = false;

        imageFields.forEach((fieldName) => {
            const input = form.querySelector(`input[name="${fieldName}"]`);
            if (input && input.files && input.files[0]) {
                formData.append(fieldName, input.files[0]);
                hasImages = true;
            }
        });

        if (!hasImages) {
            showMessage('warning', 'Please upload at least one image before using auto-fill.');
            return;
        }

        const csrfToken = document.querySelector('[name=csrfmiddlewaretoken]');
        if (csrfToken) {
            formData.append('csrfmiddlewaretoken', csrfToken.value);
        }

        extractButton.disabled = true;
        extractButton.innerHTML = '<i class="fa fa-spinner fa-spin"></i> Processing...';

        fetch(config.endpointUrl, {
            method: 'POST',
            body: formData,
            headers: {
                'X-CSRFToken': csrfToken ? csrfToken.value : '',
            },
        })
            .then((response) => {
                if (!response.ok) {
                    throw new Error(`Server error: ${response.status} ${response.statusText}`);
                }
                return response.json();
            })
            .then((data) => {
                if (!data.success) {
                    showMessage('error', data.error || 'Extraction failed');
                    return;
                }

                if (data.match_type === 'barcode' && data.multiple_matches) {
                    showMessage(
                        'warning',
                        data.message ||
                            `Found multiple matching ${config.beverageLabel}s for this barcode.`
                    );
                    return;
                }

                const extractedFields = data.extracted_fields || [];

                fillFormFields(data.data || {});

                if (data.field_confidence) {
                    showFieldConfidence(data.field_confidence);
                }

                if (data.match_type === 'barcode') {
                    showMessage(
                        'barcode',
                        `Found existing ${config.beverageLabel} via barcode (${data.matched_barcode}). Filled ${extractedFields.length} fields.`
                    );
                } else {
                    showMessage(
                        'success',
                        `Extracted ${extractedFields.length} fields with ${data.confidence} confidence`
                    );
                }

                if (data.errors && data.errors.length > 0) {
                    showMessage('warning', data.errors.join(', '));
                }
            })
            .catch((error) => {
                console.error('Vision extraction error:', error);
                showMessage('error', `An error occurred: ${error.message}`);
            })
            .finally(() => {
                extractButton.disabled = false;
                extractButton.innerHTML = originalButtonHtml;
            });
    });

    const confidenceDataEl = document.getElementById('field-confidence-data');
    if (confidenceDataEl) {
        try {
            const fieldConfidence = JSON.parse(confidenceDataEl.textContent);
            showFieldConfidence(fieldConfidence);
        } catch (_error) {
            // Ignore malformed session data.
        }
    }

    function initScannedImageHandlers() {
        document.querySelectorAll('.clear-scanned-image').forEach((button) => {
            button.addEventListener('click', function () {
                const target = this.dataset.target;
                const notice = document.getElementById(`scanned-${target}-notice`);
                const hiddenInput = document.getElementById(`use_scanned_${target}`);

                if (notice) {
                    notice.classList.add('hidden');
                }
                if (hiddenInput) {
                    hiddenInput.value = '0';
                }
            });
        });

        ['front', 'back'].forEach((target) => {
            const input = form.querySelector(`input[name="image_${target}_label"]`);
            if (!input) return;

            input.addEventListener('change', function () {
                if (!this.files || this.files.length === 0) return;

                const notice = document.getElementById(`scanned-${target}-notice`);
                const hiddenInput = document.getElementById(`use_scanned_${target}`);
                if (notice) {
                    notice.classList.add('hidden');
                }
                if (hiddenInput) {
                    hiddenInput.value = '0';
                }
            });
        });
    }

    function fillFormFields(data) {
        Object.entries(fkNameFields).forEach(([nameField, formField]) => {
            const value = data[nameField];
            if (!value) return;

            const input = form.querySelector(`[name="${formField}"]`);
            if (!input) return;

            const setCreatedValue = (attempts = 0) => {
                if (input.tomselect) {
                    input.tomselect.createItem(value);
                    input.dispatchEvent(new Event('change', { bubbles: true }));
                } else if (attempts < 5) {
                    setTimeout(() => setCreatedValue(attempts + 1), 100);
                }
            };

            setCreatedValue();
        });

        Object.entries(fieldMap).forEach(([apiField, formField]) => {
            if (data[apiField] === undefined) return;

            const input = form.querySelector(`[name="${formField}"]`);
            if (!input) return;

            const value = data[apiField];
            if (input.tagName === 'SELECT') {
                setSelectValue(input, formField, value);
            } else {
                input.value = value;
                input.dispatchEvent(new Event('change', { bubbles: true }));
            }
        });
    }

    function setSelectValue(input, formField, value, attempts = 0) {
        if (input.tomselect) {
            if (createFields.includes(formField)) {
                addCreatableItems(input, value);
            } else if (Array.isArray(value)) {
                input.tomselect.setValue(value.map(String));
            } else {
                input.tomselect.setValue(String(value));
            }
            input.dispatchEvent(new Event('change', { bubbles: true }));
            return;
        }

        if (attempts < 5) {
            setTimeout(() => setSelectValue(input, formField, value, attempts + 1), 100);
            return;
        }

        if (Array.isArray(value)) {
            value.map(String).forEach((item) => {
                const option = Array.from(input.options).find((opt) => opt.value === item);
                if (option) {
                    option.selected = true;
                }
            });
        } else {
            input.value = String(value);
        }

        input.dispatchEvent(new Event('change', { bubbles: true }));
    }

    function addCreatableItems(input, value) {
        input.tomselect.clear();
        const names = Array.isArray(value) ? value : [value];
        const skip = ['not found', 'unknown', 'n/a', 'none', ''];

        names.forEach((name) => {
            const trimmedName = String(name).trim();
            if (!trimmedName || skip.includes(trimmedName.toLowerCase())) return;

            const optionValue = `tom_new_opt${trimmedName}`;
            input.tomselect.addOption({ value: optionValue, text: trimmedName });
            input.tomselect.addItem(optionValue);
        });
    }

    function showFieldConfidence(fieldConfidence) {
        document.querySelectorAll('.field-confidence').forEach((element) => element.remove());

        Object.entries(fieldConfidence).forEach(([field, level]) => {
            const formField = confidenceFieldMap[field] || field;
            const input = form.querySelector(`[name="${formField}"]`);
            if (!input) return;

            const wrapper = input.closest('.form-group') || input.parentElement;
            const label = wrapper ? wrapper.querySelector('label') : null;
            if (!label) return;

            const dot = document.createElement('span');
            dot.className = `field-confidence field-confidence--${level}`;
            dot.title = `AI confidence: ${level}`;
            dot.setAttribute('role', 'img');
            dot.setAttribute('aria-label', `AI confidence: ${level}`);

            const srText = document.createElement('span');
            srText.className = 'sr-only';
            srText.textContent = `AI confidence: ${level}`;
            dot.appendChild(srText);

            label.appendChild(dot);
        });
    }

    function showMessage(type, message) {
        const messageDiv = document.createElement('div');
        messageDiv.className = `alert alert-${type}`;
        messageDiv.style.cssText = 'padding: 12px; margin: 12px 0; border-radius: 4px;';

        if (type === 'barcode') {
            messageDiv.style.backgroundColor = '#cce5ff';
            messageDiv.style.color = '#004085';
            messageDiv.style.borderLeft = '4px solid #007bff';
            const icon = document.createElement('i');
            icon.className = 'fa fa-barcode';
            icon.style.marginRight = '8px';
            messageDiv.appendChild(icon);
            messageDiv.appendChild(document.createTextNode(message));
        } else if (type === 'success') {
            messageDiv.style.backgroundColor = '#d4edda';
            messageDiv.style.color = '#155724';
            messageDiv.style.borderLeft = '4px solid #28a745';
            messageDiv.textContent = message;
        } else if (type === 'warning') {
            messageDiv.style.backgroundColor = '#fff3cd';
            messageDiv.style.color = '#856404';
            messageDiv.style.borderLeft = '4px solid #ffc107';
            messageDiv.textContent = message;
        } else if (type === 'error') {
            messageDiv.style.backgroundColor = '#f8d7da';
            messageDiv.style.color = '#721c24';
            messageDiv.style.borderLeft = '4px solid #dc3545';
            messageDiv.textContent = message;
        } else {
            messageDiv.textContent = message;
        }

        form.parentNode.insertBefore(messageDiv, form);

        setTimeout(() => {
            messageDiv.remove();
        }, 5000);
    }
});
