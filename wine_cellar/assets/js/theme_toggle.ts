// Dark mode toggle functionality
const THEME_KEY = 'wine-cellar-theme'

function getStoredTheme(): string | null {
  return localStorage.getItem(THEME_KEY)
}

function setTheme(theme: 'light' | 'dark'): void {
  document.documentElement.setAttribute('data-theme', theme)
  localStorage.setItem(THEME_KEY, theme)
}

function getPreferredTheme(): 'light' | 'dark' {
  const stored = getStoredTheme()
  if (stored === 'light' || stored === 'dark') {
    return stored
  }
  return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'
}

function toggleTheme(): void {
  const current = document.documentElement.getAttribute('data-theme') || 'light'
  setTheme(current === 'dark' ? 'light' : 'dark')
}

function initTheme(): void {
  // Set initial theme
  setTheme(getPreferredTheme())

  // Listen for toggle clicks
  document.querySelectorAll('.theme-toggle').forEach((btn) => {
    btn.addEventListener('click', toggleTheme)
  })

  // Listen for system preference changes
  window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', (e) => {
    if (!getStoredTheme()) {
      setTheme(e.matches ? 'dark' : 'light')
    }
  })
}

document.addEventListener('DOMContentLoaded', initTheme)
