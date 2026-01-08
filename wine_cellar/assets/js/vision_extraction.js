/**
 * Vision extraction AJAX handler for wine creation form
 */

document.addEventListener('DOMContentLoaded', function() {
    const extractButton = document.querySelector('button[name="extract_vision"]');
    const form = document.querySelector('.wine-form');
    
    if (!extractButton || !form) return;
    
    // Store file references to prevent "file changed" errors
    const storedFiles = {};
    
    extractButton.addEventListener('click', function(e) {
        e.preventDefault();
        
        // Get uploaded image files
        const formData = new FormData();
        const imageFields = ['image_front_label', 'image_back_label', 'image_front', 'image_back'];
        let hasImages = false;
        
        imageFields.forEach(fieldName => {
            const input = form.querySelector(`input[name="${fieldName}"]`);
            if (input && input.files && input.files[0]) {
                // Clone the file to avoid "file changed" issues
                const file = input.files[0];
                formData.append(fieldName, file);
                // Store reference for later form submission
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
        fetch('/wine/extract-vision/', {
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
                    // Barcode match found - show special message
                    showMessage('barcode',
                        `Found existing wine via barcode (${data.matched_barcode}). ` +
                        `Filled ${data.extracted_fields.length} fields.`
                    );
                } else {
                    // AI vision extraction
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
            'wine_type': 'wine_type',
            'vintage': 'vintage',
            'country': 'country',
            'subregion': 'subregion',
            'grapes': 'grapes',
            'vineyard': 'vineyard',
            'abv': 'abv',
            'size': 'size',
            'category': 'category',
            'barcode': 'barcode',
        };
        
        Object.entries(fieldMap).forEach(([apiField, formField]) => {
            if (data[apiField] !== undefined) {
                const input = form.querySelector(`[name="${formField}"]`);
                
                if (input) {
                    if (input.tagName === 'SELECT') {
                        // Handle select fields
                        if (Array.isArray(data[apiField])) {
                            // Multi-select (like TomSelect)
                            if (input.tomselect) {
                                input.tomselect.setValue(data[apiField]);
                            } else {
                                data[apiField].forEach(val => {
                                    const option = Array.from(input.options).find(opt => opt.value === val);
                                    if (option) option.selected = true;
                                });
                            }
                        } else {
                            // Single select
                            input.value = data[apiField];
                            if (input.tomselect) {
                                input.tomselect.setValue(data[apiField]);
                            }
                        }
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
            // Special style for barcode match - blue/info with barcode icon
            messageDiv.style.backgroundColor = '#cce5ff';
            messageDiv.style.color = '#004085';
            messageDiv.style.borderLeft = '4px solid #007bff';
            messageDiv.innerHTML = '<i class="fa fa-barcode" style="margin-right: 8px;"></i>' + message;
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
