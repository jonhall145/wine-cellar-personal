import React, { ReactNode, Ref, useImperativeHandle } from 'react'
import { MapContainer, useMap } from 'react-leaflet'
import MaplibreGlLayer from './MaplibreGlLayer'
import type { Map as LeafletMap } from 'leaflet'

interface MapProps {
  attribution?: string
  baseUrl?: string
  polygon?: unknown
  omtToken?: string
  children?: ReactNode
  [key: string]: unknown
}

const Map = React.forwardRef(function Map(
  { attribution, baseUrl, children, ...rest }: MapProps,
  ref: Ref<LeafletMap>
) {
  const MapLayers = () => {
    const map = useMap()
    useImperativeHandle(ref, () => map)
    return (
      <>
        <MaplibreGlLayer attribution={attribution} baseUrl={baseUrl} />
      </>
    )
  }

  return (
    <MapContainer
      style={{ minHeight: "60vh" }}
      zoom={2}
      maxZoom={18}
      {...rest}
      center={[52.520008, 13.404954]}
    >
      <MapLayers />
      {children}
    </MapContainer>
  )
})

export default Map
