interface FreeCells {
    [storageId: string]: {
        [rows: string]: number[]
    }
}

function showWarning() {
    const warning = document.getElementById('storage__error-full')
    warning?.classList.remove('hidden')
}

function hideWarning() {
    const warning = document.getElementById('storage__error-full')
    warning?.classList.add('hidden')
}

function updateStorageCells() {
    const storageSelect = document.getElementById('id_storage') as HTMLSelectElement
    const rowSelect = document.getElementById('id_row') as HTMLSelectElement
    const columnSelect = document.getElementById('id_column') as HTMLSelectElement
    const submitButton = document.getElementById('submit_button') as HTMLButtonElement

    const storageData = document.getElementById('storage-data')!
    const freeCells: FreeCells = JSON.parse(storageData.dataset.attributes || '{}')
    
    // Store initial values from Django form
    const initialRow = rowSelect?.dataset.initialValue || rowSelect?.value || ''
    const initialColumn = columnSelect?.dataset.initialValue || columnSelect?.value || ''

    if (storageSelect) {
        storageSelect.addEventListener('change', () => updateRows())
    }
    if (rowSelect) {
        rowSelect.addEventListener('change', () => updateColumns())
    }
    if (columnSelect) {
        columnSelect.addEventListener('change', updateSubmit)
    }

    function toggleFields(disable: boolean, submit: boolean = false) {
        rowSelect.disabled = disable
        columnSelect.disabled = disable
        if (disable) {
            // @ts-ignore
            rowSelect.tomselect?.disable()
            // @ts-ignore
            columnSelect.tomselect?.disable()
        } else {
            // @ts-ignore
            rowSelect.tomselect?.enable()
            // @ts-ignore
            columnSelect.tomselect?.enable()
        }
        if (submitButton) {
            submitButton.disabled = !submit
        }
    }

    function populateSelect(select: HTMLSelectElement, options: number[], selectedValue?: string) {
        // Determine value to pre-select in the native element.
        // Auto-select the first option when no restoreValue is given so that
        // iOS TomSelect can open the dropdown (it won't open with an empty control).
        const valToSet = selectedValue && options.includes(Number(selectedValue))
            ? selectedValue
            : options.length > 0 ? String(options[0]) : null

        select.innerHTML = ''
        options.forEach(function (val) {
            const opt = document.createElement('option')
            opt.value = String(val)
            opt.textContent = String(val)
            if (valToSet && String(val) === valToSet) {
                opt.selected = true
            }
            select.appendChild(opt)
        })
        // @ts-ignore
        if (select.tomselect) {
            // Clear current TomSelect state then re-sync from the native <select>.
            // Using sync() rather than addOption() ensures TomSelect's internal
            // caches (options map, sifter index, rendered items) are fully rebuilt,
            // which fixes iOS Safari not opening the dropdown after a programmatic
            // option swap.
            // @ts-ignore
            select.tomselect.clear(true)
            // @ts-ignore
            select.tomselect.clearOptions()
            // @ts-ignore
            select.tomselect.sync()
            // @ts-ignore
            select.tomselect.refreshOptions(false)
        }
    }

    function updateSubmit() {
        if (submitButton) {
            submitButton.disabled = columnSelect.value === ''
        }
    }   

    function updateColumns(restoreValue?: string) {
        const storageId = storageSelect.value
        const rowId = rowSelect.value
        const storageCells = freeCells[storageId]
        if (!storageCells || !storageCells[rowId]) {
            populateSelect(columnSelect, [])
            toggleFields(false, false)
            return
        }
        const columns = storageCells[rowId]
        if (columns.length > 0) {
            populateSelect(columnSelect, columns, restoreValue)
            hideWarning()
        } else {
            showWarning()
            populateSelect(columnSelect, [])
        }
        toggleFields(false, columnSelect.value !== '')
    }

    function updateRows(restoreRow?: string, restoreColumn?: string) {
        const storageId = storageSelect.value
        const rows = freeCells[storageId]
        const unlimitedShelf = !rows || Object.keys(rows).length === 0
        if (!unlimitedShelf) {
            const rowKeys = Object.keys(rows).map(Number)
            populateSelect(rowSelect, rowKeys, restoreRow)
            // After populating rows, update columns with restored value
            if (rowSelect.value) {
                updateColumns(restoreColumn)
            } else {
                populateSelect(columnSelect, [])
                toggleFields(false, false)
            }
        } else {
            populateSelect(rowSelect, [])
            populateSelect(columnSelect, [])
            toggleFields(true, true)
        }
    }

    // Initialize rows if storage is already selected, restoring initial values
    if (storageSelect && storageSelect.value) {
        updateRows(initialRow, initialColumn)
    }
}


function setupStorageSuggestions() {
    const suggestionButtons = document.querySelectorAll('.storage-suggestion__btn')
    const storageSelect = document.getElementById('id_storage') as HTMLSelectElement

    suggestionButtons.forEach((btn) => {
        btn.addEventListener('click', () => {
            const storageId = (btn as HTMLElement).dataset.storageId
            if (storageId && storageSelect) {
                // Set the value on the native select
                storageSelect.value = storageId
                // If TomSelect is attached, update it
                // @ts-ignore
                if (storageSelect.tomselect) {
                    // @ts-ignore
                    storageSelect.tomselect.setValue(storageId, true)
                }
                // Trigger change event to update rows/columns
                storageSelect.dispatchEvent(new Event('change'))
            }
        })
    })
}

document.addEventListener('DOMContentLoaded', () => {
    updateStorageCells()
    setupStorageSuggestions()
})