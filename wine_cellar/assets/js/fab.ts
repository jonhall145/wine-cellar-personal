// Floating Action Button (FAB) functionality for mobile
function initFab(): void {
  const fabContainer = document.querySelector('.fab-container')
  const fabMain = document.querySelector('.fab--main')

  if (!fabContainer || !fabMain) return

  fabMain.addEventListener('click', () => {
    fabContainer.classList.toggle('active')
  })

  // Close FAB when clicking outside
  document.addEventListener('click', (e) => {
    const target = e.target as HTMLElement
    if (!fabContainer.contains(target)) {
      fabContainer.classList.remove('active')
    }
  })
}

document.addEventListener('DOMContentLoaded', initFab)
