import React, { useState, useEffect } from 'react'
import { GeoJSON, Tooltip } from 'react-leaflet'

/**
 * A choropleth layer that shades countries with wines in green.
 *
 * @param {object} props
 * @param {string[]} props.countriesWithWines - Array of ISO alpha-2 country codes
 */
const CountryChoroplethLayer = ({ countriesWithWines }) => {
  const [boundaries, setBoundaries] = useState(null)

  useEffect(() => {
    fetch('/static/maps/countries-boundaries.json')
      .then(response => response.json())
      .then(data => setBoundaries(data))
      .catch(err => console.error('Failed to load country boundaries:', err))
  }, [])

  if (!boundaries) {
    return null
  }

  const countriesSet = new Set(countriesWithWines || [])

  const style = (feature) => {
    const hasWine = countriesSet.has(feature.id)
    return {
      fillColor: hasWine ? '#4CAF50' : 'transparent',
      fillOpacity: hasWine ? 0.3 : 0,
      weight: hasWine ? 1 : 0,
      color: hasWine ? '#388E3C' : 'transparent',
      opacity: hasWine ? 0.5 : 0,
    }
  }

  const onEachFeature = (feature, layer) => {
    if (countriesSet.has(feature.id)) {
      layer.bindTooltip(feature.properties.name, {
        sticky: true,
        className: 'country-tooltip'
      })
    }
  }

  return (
    <GeoJSON
      data={boundaries}
      style={style}
      onEachFeature={onEachFeature}
    />
  )
}

export default CountryChoroplethLayer
