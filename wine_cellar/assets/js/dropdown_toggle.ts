/**
 * Mobile Dropdown Toggle
 * Handles dropdown menu behavior for touch devices.
 */
;(function (): void {
  function initDropdownToggle(): void {
    // Mobile dropdown toggle for touch devices
    document.querySelectorAll<HTMLElement>('.pure-menu-has-children').forEach((dropdown) => {
      dropdown.addEventListener('click', (e: Event) => {
        if (window.innerWidth < 768) {
          const link = dropdown.querySelector<HTMLElement>(':scope > .pure-menu-link')
          const target = e.target as Node
          if (link && (target === link || link.contains(target))) {
            e.preventDefault()
            dropdown.classList.toggle('menu-open')
          }
        }
      })
    })

    // Close dropdown when clicking outside
    document.addEventListener('click', (e: Event) => {
      if (window.innerWidth < 768) {
        const target = e.target as Node
        document.querySelectorAll<HTMLElement>('.pure-menu-has-children.menu-open').forEach((dropdown) => {
          if (!dropdown.contains(target)) {
            dropdown.classList.remove('menu-open')
          }
        })
      }
    })
  }

  // Initialize when DOM is ready
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initDropdownToggle)
  } else {
    initDropdownToggle()
  }
})()
