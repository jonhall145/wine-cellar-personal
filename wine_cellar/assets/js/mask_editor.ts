/**
 * Mask Editor - Visual click-to-toggle grid editor for custom storage shapes.
 * Renders a grid below rows/columns inputs where users can click cells to
 * toggle them active/inactive, creating irregular storage shapes.
 */

const CELL_SIZE = 30;

interface MaskEditorState {
  rows: number;
  columns: number;
  activeCells: Set<string>;
}

function cellKey(row: number, col: number): string {
  return `${row},${col}`;
}

function parseCellKey(key: string): [number, number] {
  const parts = key.split(',');
  return [parseInt(parts[0], 10), parseInt(parts[1], 10)];
}

function initMaskEditor(): void {
  const rowsInput = document.getElementById('id_rows') as HTMLInputElement | null;
  const columnsInput = document.getElementById('id_columns') as HTMLInputElement | null;
  const maskInput = document.getElementById('id_cell_mask') as HTMLInputElement | null;
  const container = document.getElementById('mask-editor-container');

  if (!rowsInput || !columnsInput || !maskInput || !container) return;

  const state: MaskEditorState = {
    rows: parseInt(rowsInput.value, 10) || 0,
    columns: parseInt(columnsInput.value, 10) || 0,
    activeCells: new Set<string>(),
  };

  // Initialize from existing mask data
  const initialMask = maskInput.value;
  if (initialMask) {
    try {
      const parsed = JSON.parse(initialMask) as number[][];
      for (const [r, c] of parsed) {
        state.activeCells.add(cellKey(r, c));
      }
    } catch {
      // Invalid JSON, start with all active
      initAllActive(state);
    }
  } else {
    initAllActive(state);
  }

  function initAllActive(s: MaskEditorState): void {
    s.activeCells.clear();
    for (let r = 1; r <= s.rows; r++) {
      for (let c = 1; c <= s.columns; c++) {
        s.activeCells.add(cellKey(r, c));
      }
    }
  }

  function isAllActive(): boolean {
    return state.activeCells.size === state.rows * state.columns;
  }

  function serializeMask(): void {
    if (state.rows === 0 || state.columns === 0 || isAllActive()) {
      maskInput!.value = '';
      return;
    }
    const cells: number[][] = [];
    for (const key of state.activeCells) {
      cells.push(parseCellKey(key));
    }
    cells.sort((a, b) => a[0] - b[0] || a[1] - b[1]);
    maskInput!.value = JSON.stringify(cells);
  }

  function render(): void {
    container!.innerHTML = '';

    if (state.rows === 0 || state.columns === 0) {
      return;
    }

    const wrapper = document.createElement('div');
    wrapper.className = 'mask-editor';

    // Header with label and buttons
    const header = document.createElement('div');
    header.className = 'mask-editor__header';

    const label = document.createElement('span');
    label.className = 'mask-editor__label';
    label.textContent = gettext('Cell Layout');
    header.appendChild(label);

    const btnGroup = document.createElement('div');
    btnGroup.className = 'mask-editor__buttons';

    const selectAllBtn = document.createElement('button');
    selectAllBtn.type = 'button';
    selectAllBtn.className = 'mask-editor__btn';
    selectAllBtn.textContent = gettext('Select All');
    selectAllBtn.addEventListener('click', () => {
      initAllActive(state);
      serializeMask();
      render();
    });

    const clearAllBtn = document.createElement('button');
    clearAllBtn.type = 'button';
    clearAllBtn.className = 'mask-editor__btn';
    clearAllBtn.textContent = gettext('Clear All');
    clearAllBtn.addEventListener('click', () => {
      state.activeCells.clear();
      serializeMask();
      render();
    });

    btnGroup.appendChild(selectAllBtn);
    btnGroup.appendChild(clearAllBtn);
    header.appendChild(btnGroup);
    wrapper.appendChild(header);

    // Grid (inside scrollable wrapper)
    const gridWrapper = document.createElement('div');
    gridWrapper.className = 'mask-editor__grid-wrapper';
    const grid = document.createElement('div');
    grid.className = 'mask-editor__grid';
    grid.style.gridTemplateColumns = `repeat(${state.columns}, ${CELL_SIZE}px)`;

    for (let r = 1; r <= state.rows; r++) {
      for (let c = 1; c <= state.columns; c++) {
        const cell = document.createElement('div');
        const key = cellKey(r, c);
        const active = state.activeCells.has(key);
        cell.className = `mask-editor__cell${active ? ' mask-editor__cell--active' : ''}`;
        cell.dataset.row = String(r);
        cell.dataset.col = String(c);
        const titleTemplate = gettext('Row %s, Col %s');
        cell.title = titleTemplate.replace('%s', String(r)).replace('%s', String(c));

        cell.addEventListener('click', () => {
          if (state.activeCells.has(key)) {
            state.activeCells.delete(key);
          } else {
            state.activeCells.add(key);
          }
          serializeMask();
          // Toggle class directly instead of re-rendering entire grid
          cell.classList.toggle('mask-editor__cell--active');
        });

        grid.appendChild(cell);
      }
    }

    gridWrapper.appendChild(grid);
    wrapper.appendChild(gridWrapper);

    const hint = document.createElement('div');
    hint.className = 'mask-editor__hint';
    hint.textContent = gettext('Click cells to toggle active/inactive. Inactive cells cannot hold bottles.');
    wrapper.appendChild(hint);

    container!.appendChild(wrapper);
  }

  function handleDimensionChange(): void {
    const newRows = parseInt(rowsInput!.value, 10) || 0;
    const newCols = parseInt(columnsInput!.value, 10) || 0;

    if (newRows === state.rows && newCols === state.columns) return;

    const oldRows = state.rows;
    const oldCols = state.columns;
    const oldActive = new Set(state.activeCells);

    state.rows = newRows;
    state.columns = newCols;
    state.activeCells.clear();

    for (let r = 1; r <= newRows; r++) {
      for (let c = 1; c <= newCols; c++) {
        const key = cellKey(r, c);
        const wasInOldBounds = r <= oldRows && c <= oldCols;
        if (wasInOldBounds) {
          // Preserve old state
          if (oldActive.has(key)) {
            state.activeCells.add(key);
          }
        } else {
          // New cell - default to active
          state.activeCells.add(key);
        }
      }
    }

    // If there was no previous mask (oldActive had all cells), keep all active
    if (oldActive.size === oldRows * oldCols && oldRows > 0 && oldCols > 0) {
      for (let r = 1; r <= newRows; r++) {
        for (let c = 1; c <= newCols; c++) {
          state.activeCells.add(cellKey(r, c));
        }
      }
    }

    serializeMask();
    render();
  }

  rowsInput.addEventListener('input', handleDimensionChange);
  columnsInput.addEventListener('input', handleDimensionChange);

  // Initial render
  render();
  serializeMask();
}

document.addEventListener('DOMContentLoaded', initMaskEditor, false);
