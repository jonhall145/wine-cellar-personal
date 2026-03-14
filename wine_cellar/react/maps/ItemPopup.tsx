import React from 'react'
import { MapPopup } from './MapPopup'

const translations = {
  country: 'Country',
  image_alt: 'Picture of a wine bottle.',
  vintage: 'Vintage',
}

/**
 * Safely derive a URL value from an untrusted input.
 *
 * Allows only http/https absolute URLs and path-relative URLs (e.g., "/static/img.png").
 * Rejects protocol-relative URLs (e.g., "//evil.com") and dangerous schemes.
 * Returns undefined for anything else.
 */
const sanitizeUrl = (value: unknown): string | undefined => {
  if (!value || typeof value !== 'string') {
    return undefined
  }

  // Disallow obvious dangerous prefixes like "javascript:", "data:", "vbscript:", etc.
  const trimmed = value.trim()
  const lower = trimmed.toLowerCase()
  if (
    lower.startsWith('javascript:') ||
    lower.startsWith('data:') ||
    lower.startsWith('vbscript:')
  ) {
    return undefined
  }

  // Reject protocol-relative URLs like "//evil.com/image.jpg"
  // These can redirect to external domains and are not truly "relative"
  if (trimmed.startsWith('//')) {
    return undefined
  }

  try {
    // If value is absolute, check protocol explicitly.
    const url = new URL(trimmed, window.location.origin)
    if (url.protocol === 'http:' || url.protocol === 'https:') {
      return url.href
    }
    // For other protocols, do not use the value.
    return undefined
  } catch {
    // If URL construction fails (e.g., malformed), do not use the value.
    return undefined
  }
}

interface ItemPopupProps {
  feature: GeoJSON.Feature
}

export const ItemPopup = ({ feature }: ItemPopupProps) => {
  const props = feature?.properties ?? {}
  const imageSrc = sanitizeUrl(props.image)
  const linkHref = sanitizeUrl(props.url)

  return (
    <MapPopup feature={feature}>
      <div className="popup-image">
        {imageSrc && (
          <img
            src={imageSrc}
            alt={translations.image_alt}
            height="100"
          />
        )}
      </div>
      <div className="popup-content">
        {linkHref ? (
          <a href={linkHref} className="popup-title">
            {props.name}
          </a>
        ) : (
          <span className="popup-title">
            {props.name}
          </span>
        )}
        <div className="popup-details">
          <div className="popup-detail">
            <span className="popup-label">{translations.country}:</span>
            <span className="country-info">
              {props.country_icon}{' '}
              {props.country_name}
            </span>
          </div>
          {props.vintage && (
            <div className="popup-detail">
              <span className="popup-label">{translations.vintage}:</span>
              <span>{props.vintage}</span>
            </div>
          )}
        </div>
      </div>
    </MapPopup>
  )
}
