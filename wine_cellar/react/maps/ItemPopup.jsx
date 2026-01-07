import React from 'react'
import django from 'django'
import { MapPopup } from './MapPopup'

const translations = {
  country: django.pgettext('Singular', 'Country'),
  image_alt: django.gettext('Picture of a wine bottle.'),
  vintage: django.gettext('Vintage'),
}

/**
 * Safely derive a URL value from an untrusted input.
 *
 * Allows only http/https/relative URLs; returns undefined for anything else.
 *
 * @param {string} value
 * @returns {string|undefined}
 */
const sanitizeUrl = (value) => {
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

  try {
    // If value is absolute, check protocol explicitly.
    const url = new URL(trimmed, window.location.origin)
    if (url.protocol === 'http:' || url.protocol === 'https:') {
      return url.href
    }
    // For other protocols, do not use the value.
    return undefined
  } catch (e) {
    // If URL construction fails (e.g., malformed), do not use the value.
    return undefined
  }
}

/**
 * Renders a popup for an item feature on a map.
 *
 * @param {Object} props - The component props.
 * @param {Object} props.feature - The geojson feature.
 * @returns {JSX.Element} The JSX element representing the popup.
 */
export const ItemPopup = ({ feature }) => {
  const imageSrc = sanitizeUrl(feature?.properties?.image)
  const linkHref = sanitizeUrl(feature?.properties?.url)

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
            {feature.properties.name}
          </a>
        ) : (
          <span className="popup-title">
            {feature.properties.name}
          </span>
        )}
        <div className="popup-details">
          <div className="popup-detail">
            <span className="popup-label">{translations.country}:</span>
            <span className="country-info">
              {feature.properties.country_icon}{' '}
              {feature.properties.country_name}
            </span>
          </div>
          {feature.properties.vintage && (
            <div className="popup-detail">
              <span className="popup-label">{translations.vintage}:</span>
              <span>{feature.properties.vintage}</span>
            </div>
          )}
        </div>
      </div>
    </MapPopup>
  )
}
