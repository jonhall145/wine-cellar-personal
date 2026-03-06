import React, { ReactNode } from 'react'
import { Popup } from 'react-leaflet'

interface MapPopupProps {
  feature: GeoJSON.Feature
  className?: string
  children: ReactNode
}

export const MapPopup = ({ className, children, ...rest }: MapPopupProps) => {
  const _className = 'maps-popups ' + (className ?? '')
  return (
    <Popup {...rest} className={_className}>
      <div className="maps-popups-popup-text-content">
        {children}
      </div>
    </Popup>
  )
}
