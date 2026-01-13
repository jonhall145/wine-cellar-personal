/**
 * Form loading state utilities
 * Adds visual feedback when forms are submitted
 */

document.addEventListener('DOMContentLoaded', () => {
  // Add loading state to forms with data-loading attribute
  document.querySelectorAll('form[data-loading]').forEach((form) => {
    form.addEventListener('submit', (e) => {
      const submitBtn = form.querySelector('button[type="submit"], input[type="submit"]') as HTMLButtonElement | null
      if (submitBtn && !submitBtn.disabled) {
        // Disable button to prevent double submission
        submitBtn.disabled = true
        submitBtn.classList.add('button--loading')
        
        // Add spinner if not already present
        if (!submitBtn.querySelector('.spinner')) {
          const spinner = document.createElement('span')
          spinner.className = 'spinner spinner--sm'
          spinner.setAttribute('aria-hidden', 'true')
          submitBtn.insertBefore(spinner, submitBtn.firstChild)
        }
      }
    })
  })

  // Also handle any button with data-loading-btn attribute
  document.querySelectorAll('button[data-loading-btn], a[data-loading-btn]').forEach((btn) => {
    btn.addEventListener('click', () => {
      const button = btn as HTMLButtonElement
      if (!button.disabled && !button.classList.contains('button--loading')) {
        button.classList.add('button--loading')
        
        if (!button.querySelector('.spinner')) {
          const spinner = document.createElement('span')
          spinner.className = 'spinner spinner--sm'
          spinner.setAttribute('aria-hidden', 'true')
          button.insertBefore(spinner, button.firstChild)
        }
      }
    })
  })
})

export {}
