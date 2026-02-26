import React from 'react'
import BaseMap from './Map'
import MarkerClusterLayer from './MarkerClusterLayer'
import GeoJsonMarker from './GeoJsonMarker'
import { ItemPopup } from './ItemPopup'
import countries from './country.json'

/**
 * Creates a Map component.
 *
 * @param {object} props - The properties for the Map component.
 * @param {string} props.id - The unique identifier for the Map component.
 * @param {string} props.title - The title for the Map component.
 * @returns {React.Element} - The rendered Map component.
 * @throws {Error} - If id is not defined.
 */
export const Map = React.forwardRef(function Map({ id, title, ...props }, ref) {
  if (!id) {
    throw new Error('id must be defined when using Map')
  }

  return (
    <div id={id}>
      {title && <h2 className="title">{title}</h2>}
        <div>
          <BaseMap {...props} ref={ref} />
        </div>
    </div>
  )
})

/**
 * Represents a map component with markers.
 *
 * @param {object} props - The properties to pass to the Map component.
 * @param {Array<object>} points - The array of points to create markers from.
 * @param {boolean} withoutPopup - Indicates whether to exclude the popup for each marker.
 * @param {ReactNode} children - Any additional controls etc. to be added to the map
 * @returns {JSX.Element} - The rendered map component with markers.
 */
export const MapWithMarkers = ({ wines, withoutPopup, children, ...props }) => {
  const markers = wines.map((wine, index) => {
    if (!countries[wine.country]) {
      return null
    }
    const feature = { ...countries[wine.country] }
    feature.properties = { ...feature.properties, ...wine }

    // Use appellation coordinates when available, otherwise fall back to country center
    if (wine.appellation && wine.appellation.lat && wine.appellation.lng) {
      feature.geometry = {
        ...feature.geometry,
        coordinates: [wine.appellation.lng, wine.appellation.lat]
      }
    }

    return (
      <GeoJsonMarker key={index} feature={feature}>
          {!withoutPopup && <ItemPopup feature={feature} />}
      </GeoJsonMarker>
    )
  })
  return (
    <Map {...props}>
      {markers.length > 1 ? (
        <MarkerClusterLayer>{markers}</MarkerClusterLayer>
      ) : (
        markers
      )}
      {children}
    </Map>
  )
}
