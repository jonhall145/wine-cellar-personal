import React from 'react'
import { createRoot } from 'react-dom/client'
import { MapWithMarkers, Map } from './WineMaps'
import ErrorBoundary from '../components/ErrorBoundary'

function init() {
  const container = document.getElementById('wine_map')
  if (container) {
    const props = JSON.parse(container.getAttribute('data-attributes') ?? "")
    const root = createRoot(container)
    root.render(
      <React.StrictMode>
        <ErrorBoundary>
          <MapWithMarkers
            {...props.map}
            wines={props.wines}
            id="display-point"
          />
        </ErrorBoundary>
      </React.StrictMode>
    )
  }
}

document.addEventListener('DOMContentLoaded', init, false)
