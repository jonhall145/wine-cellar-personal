/**
 * Vision extraction AJAX handler for whisky creation form
 */

document.addEventListener('DOMContentLoaded', function() {
    const extractButton = document.querySelector('button[name="extract_vision"]');
    const form = document.querySelector('.wine-form');

    if (!extractButton || !form) return;

    // Store file references to prevent "file changed" errors
    const storedFiles = {};

    // Initialize scanned image clear buttons
    initScannedImageHandlers();

    function initScannedImageHandlers() {
        // Handle "Clear" button clicks for scanned images
        document.querySelectorAll('.clear-scanned-image').forEach(button => {
            button.addEventListener('click', function() {
                const target = this.dataset.target; // 'front' or 'back'
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

        // Hide scanned image notice when user uploads their own image
        const frontInput = form.querySelector('input[name="image_front_label"]');
        const backInput = form.querySelector('input[name="image_back_label"]');

        if (frontInput) {
            frontInput.addEventListener('change', function() {
                if (this.files && this.files.length > 0) {
                    const notice = document.getElementById('scanned-front-notice');
                    const hiddenInput = document.getElementById('use_scanned_front');
                    if (notice) notice.classList.add('hidden');
                    if (hiddenInput) hiddenInput.value = '0';
                }
            });
        }

        if (backInput) {
            backInput.addEventListener('change', function() {
                if (this.files && this.files.length > 0) {
                    const notice = document.getElementById('scanned-back-notice');
                    const hiddenInput = document.getElementById('use_scanned_back');
                    if (notice) notice.classList.add('hidden');
                    if (hiddenInput) hiddenInput.value = '0';
                }
            });
        }
    }

    extractButton.addEventListener('click', function(e) {
        e.preventDefault();

        // Get uploaded image files
        const formData = new FormData();
        const imageFields = ['image_front_label', 'image_back_label', 'image_front', 'image_back'];
        let hasImages = false;

        imageFields.forEach(fieldName => {
            const input = form.querySelector(`input[name="${fieldName}"]`);
            if (input && input.files && input.files[0]) {
                const file = input.files[0];
                formData.append(fieldName, file);
                storedFiles[fieldName] = file;
                hasImages = true;
            }
        });

        if (!hasImages) {
            showMessage('warning', 'Please upload at least one image before using auto-fill.');
            return;
        }

        // Add CSRF token
        const csrfToken = document.querySelector('[name=csrfmiddlewaretoken]');
        if (csrfToken) {
            formData.append('csrfmiddlewaretoken', csrfToken.value);
        }

        // Show loading state
        extractButton.disabled = true;
        extractButton.innerHTML = '<i class="fa fa-spinner fa-spin"></i> Processing...';

        // Make AJAX request
        fetch('/whisky/extract-vision/', {
            method: 'POST',
            body: formData,
            headers: {
                'X-CSRFToken': csrfToken ? csrfToken.value : '',
            },
        })
        .then(response => {
            if (!response.ok) {
                throw new Error(`Server error: ${response.status} ${response.statusText}`);
            }
            return response.json();
        })
        .then(data => {
            if (data.success) {
                // Auto-fill form fields with extracted data
                fillFormFields(data.data);

                // Show success message based on match type
                if (data.match_type === 'barcode') {
                    showMessage('barcode',
                        `Found existing whisky via barcode (${data.matched_barcode}). ` +
                        `Filled ${data.extracted_fields.length} fields.`
                    );
                } else {
                    showMessage('success',
                        `Extracted ${data.extracted_fields.length} fields with ${data.confidence} confidence`
                    );
                }

                // Show any errors
                if (data.errors && data.errors.length > 0) {
                    showMessage('warning', data.errors.join(', '));
                }
            } else {
                showMessage('error', data.error || 'Extraction failed');
            }
        })
        .catch(error => {
            console.error('Vision extraction error:', error);
            showMessage('error', `An error occurred: ${error.message}`);
        })
        .finally(() => {
            // Restore button state
            extractButton.disabled = false;
            extractButton.innerHTML = '<i class="fa fa-magic"></i> Auto-fill from Images';
        });
    });

    function fillFormFields(data) {
        // Map of API field names to form field names
        const fieldMap = {
            'name': 'name',
            'whisky_type': 'whisky_type',
            'distillery': 'distillery',
            'region': 'region',
            'country': 'country',
            'age_statement': 'age_statement',
            'abv': 'abv',
            'peated_level': 'peated_level',
            'cask_type': 'cask_type',
            'size': 'size',
            'vintage_year': 'vintage_year',
            'bottled_year': 'bottled_year',
            'cask_number': 'cask_number',
            'batch_number': 'batch_number',
            'bottle_number': 'bottle_number',
            'bottler': 'bottler',
            'bottler_series': 'bottler_series',
            'barcode': 'barcode',
        };

        // Handle unresolved FK fields (server returns _name suffix when no DB match)
        const fkNameFields = {
            'distillery_name': 'distillery',
            'region_name': 'region',
            'bottler_name': 'bottler',
        };

        Object.entries(fkNameFields).forEach(([nameField, formField]) => {
            if (data[nameField]) {
                const input = form.querySelector(`[name="${formField}"]`);
                if (input) {
                    const setNewValue = (attempts = 0) => {
                        if (input.tomselect) {
                            const name = data[nameField];
                            input.tomselect.createItem(name);
                            console.log(`Created new ${formField}:`, name);
                        } else if (attempts < 5) {
                            setTimeout(() => setNewValue(attempts + 1), 100);
                        }
                    };
                    setNewValue();
                }
            }
        });

        Object.entries(fieldMap).forEach(([apiField, formField]) => {
            if (data[apiField] !== undefined) {
                const input = form.querySelector(`[name="${formField}"]`);

                if (input) {
                    if (input.tagName === 'SELECT') {
                        // Handle select fields
                        const value = data[apiField];

                        // Function to set TomSelect value with retry logic
                        const setSelectValue = (attempts = 0) => {
                            if (input.tomselect) {
                                // TomSelect is ready
                                if (Array.isArray(value)) {
                                    input.tomselect.setValue(value);
                                } else {
                                    input.tomselect.setValue(String(value));
                                }
                                console.log(`Set ${formField} to:`, value);
                            } else if (attempts < 5) {
                                // TomSelect not ready yet, retry after short delay
                                setTimeout(() => setSelectValue(attempts + 1), 100);
                            } else {
                                // Fallback to native select
                                if (Array.isArray(value)) {
                                    value.forEach(val => {
                                        const option = Array.from(input.options).find(opt => opt.value === val);
                                        if (option) option.selected = true;
                                    });
                                } else {
                                    input.value = value;
                                }
                                console.warn(`TomSelect not found for ${formField}, used native select`);
                            }
                        };

                        setSelectValue();
                    } else {
                        // Handle text/number inputs
                        input.value = data[apiField];
                    }

                    // Trigger change event for any listeners
                    input.dispatchEvent(new Event('change', { bubbles: true }));
                }
            }
        });
    }

    function showMessage(type, message) {
        // Create message element
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

        // Insert before form
        form.parentNode.insertBefore(messageDiv, form);

        // Remove after 5 seconds
        setTimeout(() => {
            messageDiv.remove();
        }, 5000);
    }
});
