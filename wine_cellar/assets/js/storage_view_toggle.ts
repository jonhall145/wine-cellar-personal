/**
 * Storage View Toggle
 * Handles switching between list and grid views on the storage detail page.
 */

declare global {
  interface Window {
    toggleView: (view: 'list' | 'grid') => void
  }
}

function toggleView(view: 'list' | 'grid'): void {
  const listView = document.getElementById('list-view')
  const gridView = document.getElementById('grid-view')
  const btnList = document.getElementById('btn-list-view')
  const btnGrid = document.getElementById('btn-grid-view')

  if (!listView || !gridView) return

  if (view === 'list') {
    listView.classList.remove('storage-view--hidden')
    gridView.classList.add('storage-view--hidden')
    btnList?.classList.add('storage-view-toggle__btn--active')
    btnGrid?.classList.remove('storage-view-toggle__btn--active')
  } else {
    listView.classList.add('storage-view--hidden')
    gridView.classList.remove('storage-view--hidden')
    btnList?.classList.remove('storage-view-toggle__btn--active')
    btnGrid?.classList.add('storage-view-toggle__btn--active')
  }
}

// Export for use in global context
window.toggleView = toggleView

export { toggleView }
