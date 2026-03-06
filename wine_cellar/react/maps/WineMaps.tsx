import React, { ReactNode, Ref } from 'react'
import BaseMap from './Map'
import MarkerClusterLayer from './MarkerClusterLayer'
import GeoJsonMarker from './GeoJsonMarker'
import { ItemPopup } from './ItemPopup'
import countries from './country.json'
import type { Map as LeafletMap } from 'leaflet'

interface WineAppellation {
  lat?: number
  lng?: number
}

interface WinePoint {
  country: string
  appellation?: WineAppellation
  [key: string]: unknown
}

interface MapProps {
  id: string
  title?: string
  [key: string]: unknown
}

const countriesMap = countries as Record<string, GeoJSON.Feature>

export const Map = React.forwardRef(function Map(
  { id, title, ...props }: MapProps,
  ref: Ref<LeafletMap>
) {
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

interface MapWithMarkersProps {
  wines: WinePoint[]
  withoutPopup?: boolean
  children?: ReactNode
  [key: string]: unknown
}

export const MapWithMarkers = ({ wines, withoutPopup, children, ...props }: MapWithMarkersProps) => {
  const markers = wines.map((wine, index) => {
    if (!countriesMap[wine.country]) {
      return null
    }
    const feature = { ...countriesMap[wine.country] }
    feature.properties = { ...feature.properties, ...wine }

    // Use appellation coordinates when available, otherwise fall back to country center
    if (wine.appellation && wine.appellation.lat && wine.appellation.lng) {
      feature.geometry = {
        ...feature.geometry,
        coordinates: [wine.appellation.lng, wine.appellation.lat]
      } as GeoJSON.Geometry
    }

    return (
      <GeoJsonMarker key={index} feature={feature}>
          {!withoutPopup && <ItemPopup feature={feature} />}
      </GeoJsonMarker>
    )
  })
  const validMarkers = markers.filter(Boolean)
  return (
    <Map {...props}>
      {validMarkers.length > 1 ? (
        <MarkerClusterLayer>{validMarkers}</MarkerClusterLayer>
      ) : (
        validMarkers
      )}
      {children}
    </Map>
  )
}
