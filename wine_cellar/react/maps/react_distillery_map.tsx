import React, { useState, useEffect } from 'react'
import { createRoot } from 'react-dom/client'
import BaseMap from './Map'
import GeoJsonMarker from './GeoJsonMarker'
import MarkerClusterLayer from './MarkerClusterLayer'
import { MapPopup } from './MapPopup'
// @ts-ignore
import django from 'django'

const translated = {
    region: django.gettext('Region'),
    status: django.gettext('Status'),
    founded: django.gettext('Founded'),
    bottles: django.gettext('Bottles'),
    loading: django.gettext('Loading map data...'),
    allRegions: django.gettext('All Regions'),
}

interface DistilleryData {
    id: number
    name: string
    region: string
    region_id: number
    latitude: number | null
    longitude: number | null
    status: string
    status_display: string
    founded_year: number | null
    bottle_count: number
    url: string | null
}

interface RegionOption {
    id: number
    name: string
}

const statusColors: Record<string, string> = {
    AC: '#2ecc71', // Active - green
    SI: '#f39c12', // Silent - orange
    CL: '#e74c3c', // Closed - red
    DE: '#95a5a6', // Demolished - grey
}

const DistilleryPopup: React.FC<{ distillery: DistilleryData }> = ({ distillery }) => (
    <div className="popup-content" style={{ minWidth: '180px' }}>
        {distillery.url ? (
            <a href={distillery.url} className="popup-title">{distillery.name}</a>
        ) : (
            <span className="popup-title">{distillery.name}</span>
        )}
        <div className="popup-details">
            <div className="popup-detail">
                <span className="popup-label">{translated.region}:</span>
                <span>{distillery.region}</span>
            </div>
            <div className="popup-detail">
                <span className="popup-label">{translated.status}:</span>
                <span style={{ color: statusColors[distillery.status] || '#333' }}>
                    {distillery.status_display}
                </span>
            </div>
            {distillery.founded_year && (
                <div className="popup-detail">
                    <span className="popup-label">{translated.founded}:</span>
                    <span>{distillery.founded_year}</span>
                </div>
            )}
            {distillery.bottle_count > 0 && (
                <div className="popup-detail">
                    <span className="popup-label">{translated.bottles}:</span>
                    <span>{distillery.bottle_count}</span>
                </div>
            )}
        </div>
    </div>
)

const DistilleryMap: React.FC<{ distilleries: DistilleryData[], baseUrl: string }> = ({ distilleries, baseUrl }) => {
    const [selectedRegion, setSelectedRegion] = useState<number | null>(null)

    // Build region options from distillery data
    const regions: RegionOption[] = []
    const seenRegions = new Set<number>()
    for (const d of distilleries) {
        if (d.region_id && !seenRegions.has(d.region_id)) {
            seenRegions.add(d.region_id)
            regions.push({ id: d.region_id, name: d.region })
        }
    }
    regions.sort((a, b) => a.name.localeCompare(b.name))

    const filtered = selectedRegion
        ? distilleries.filter(d => d.region_id === selectedRegion)
        : distilleries

    const mappable = filtered.filter(d => d.latitude && d.longitude)

    const markers = mappable.map((d, idx) => {
        const feature = {
            type: 'Feature' as const,
            geometry: {
                type: 'Point' as const,
                coordinates: [d.longitude!, d.latitude!],
            },
            properties: {
                name: d.name,
                color: statusColors[d.status] || '#333',
            },
        }

        return (
            <GeoJsonMarker key={d.id} feature={feature}>
                <MapPopup feature={feature}>
                    <DistilleryPopup distillery={d} />
                </MapPopup>
            </GeoJsonMarker>
        )
    })

    const mapAttribution = '<a href="https://openfreemap.org" target="_blank" rel="noopener noreferrer">OpenFreeMap</a> <a href="https://www.openmaptiles.org/" target="_blank" rel="noopener noreferrer">\u00a9 OpenMapTiles</a> Data from <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener noreferrer">OpenStreetMap</a>'

    // Fit map to actual distillery locations
    const boundsProps: Record<string, unknown> = {}
    if (mappable.length > 0) {
        const lats = mappable.map(d => d.latitude!)
        const lngs = mappable.map(d => d.longitude!)
        boundsProps.bounds = [
            [Math.min(...lats), Math.min(...lngs)],
            [Math.max(...lats), Math.max(...lngs)],
        ]
        boundsProps.boundsOptions = { padding: [30, 30] }
    } else {
        boundsProps.center = [50, 10] as [number, number]
        boundsProps.zoom = 4
    }

    return (
        <div>
            <div className="mb-12">
                <select
                    value={selectedRegion || ''}
                    onChange={e => setSelectedRegion(e.target.value ? Number(e.target.value) : null)}
                    className="pure-input"
                >
                    <option value="">{translated.allRegions}</option>
                    {regions.map(r => (
                        <option key={r.id} value={r.id}>{r.name}</option>
                    ))}
                </select>
            </div>

            <div id="distillery-map-container">
                <BaseMap baseUrl={baseUrl} attribution={mapAttribution} {...boundsProps}>
                    {markers.length > 1 ? (
                        <MarkerClusterLayer>{markers}</MarkerClusterLayer>
                    ) : (
                        markers
                    )}
                </BaseMap>
            </div>
        </div>
    )
}

function init() {
    const container = document.getElementById('distillery-map')
    if (container) {
        try {
            const distilleries: DistilleryData[] = JSON.parse(
                container.getAttribute('data-distilleries') || '[]'
            )
            const baseUrl = container.getAttribute('data-base-url') || ''
            const root = createRoot(container)
            root.render(
                <React.StrictMode>
                    <DistilleryMap distilleries={distilleries} baseUrl={baseUrl} />
                </React.StrictMode>
            )
        } catch (e) {
            console.error('Failed to initialize distillery map:', e)
        }
    }
}

document.addEventListener('DOMContentLoaded', init, false)
