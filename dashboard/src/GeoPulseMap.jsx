
import { useEffect } from 'react'
import {
  MapContainer,
  TileLayer,
  Circle,
  CircleMarker,
  Popup,
  useMap,
} from 'react-leaflet'
import 'leaflet/dist/leaflet.css'

function FitMap({ points }) {
  const map = useMap()

  useEffect(() => {
    if (points.length > 0) {
      map.fitBounds(points, { padding: [35, 35], maxZoom: 14 })
    }
  }, [map, points])

  return null
}

export default function GeoPulseMap({ summary, selectedLayer }) {
  const stores = summary?.stores || {}
  const storeA = stores.store_a
  const storeB = stores.store_b

  const valid = (store) =>
    store &&
    Number.isFinite(Number(store.latitude)) &&
    Number.isFinite(Number(store.longitude))

  const a = valid(storeA)
    ? [Number(storeA.latitude), Number(storeA.longitude)]
    : null

  const b = valid(storeB)
    ? [Number(storeB.latitude), Number(storeB.longitude)]
    : null

  const cells = summary?.density_grid?.cells || []

  const showDensity = selectedLayer === 'Footfall density'
  const showCatchments = selectedLayer === 'Store catchments'
  const showOverlap = selectedLayer === 'Visitor overlap'
  const showOpportunities = selectedLayer === 'Opportunity zones'

  // Calculate distance between two geographic coordinates.
  const getDistanceMeters = (lat1, lon1, lat2, lon2) => {
    const toRad = Math.PI / 180
    const dLat = (lat2 - lat1) * toRad
    const dLon = (lon2 - lon1) * toRad

    const value =
      Math.sin(dLat / 2) ** 2 +
      Math.cos(lat1 * toRad) *
        Math.cos(lat2 * toRad) *
        Math.sin(dLon / 2) ** 2

    return (
      2 *
      6371008.8 *
      Math.atan2(Math.sqrt(value), Math.sqrt(1 - value))
    )
  }

  // Identify grid cells outside both existing 500 m catchments.
  const opportunityCells =
    a && b
      ? cells
          .map((cell) => {
            const latitude = Number(cell.latitude)
            const longitude = Number(cell.longitude)

            const distanceA = getDistanceMeters(
              latitude,
              longitude,
              a[0],
              a[1],
            )

            const distanceB = getDistanceMeters(
              latitude,
              longitude,
              b[0],
              b[1],
            )
            return {
  ...cell,
  exactDistanceA: distanceA,
  exactDistanceB: distanceB,
  distanceA: Math.round(distanceA),
  distanceB: Math.round(distanceB),
  nearestDistance: Math.round(
    Math.min(distanceA, distanceB),
  ),
}
          })
          .filter(
  (cell) =>
    cell.exactDistanceA > 500 && cell.exactDistanceB > 500,
)
      : []
  

  // Display the 15 highest-activity opportunity cells.
  const topOpportunities = [...opportunityCells]
    .sort((x, y) => Number(y.pings) - Number(x.pings))
    .slice(0, 15)

  const points = [...(a ? [a] : []), ...(b ? [b] : [])]

  if (cells.length) {
    const step = Math.max(1, Math.floor(cells.length / 100))

    cells.forEach((cell, index) => {
      if (index % step === 0) {
        points.push([
          Number(cell.latitude),
          Number(cell.longitude),
        ])
      }
    })
  }

  const maxPings = Math.max(
    1,
    ...cells.map((cell) => Number(cell.pings) || 0),
  )

  return (
    <div className="real-map">
      <MapContainer
        center={a || [12.978973, 77.64527]}
        zoom={13}
        scrollWheelZoom
        className="leaflet-map"
      >
        <TileLayer
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        />

        <FitMap points={points} />

        {/* Existing GPS density layer */}
        {(showDensity || showOverlap) &&
          cells.map((cell, index) => {
            const pings = Number(cell.pings) || 0
            const intensity = pings / maxPings

            return (
              <CircleMarker
                key={`${cell.latitude}-${cell.longitude}-${index}`}
                center={[
                  Number(cell.latitude),
                  Number(cell.longitude),
                ]}
                radius={3 + intensity * 9}
                pathOptions={{
                  color: '#6d5bd0',
                  weight: 0,
                  fillColor: '#7968e8',
                  fillOpacity: 0.18 + intensity * 0.62,
                }}
              >
                <Popup>
                  <strong>Aggregated GPS density</strong>
                  <br />
                  {pings.toLocaleString()} pings
                  <br />
                  250 m grid cell
                </Popup>
              </CircleMarker>
            )
          })}

        {/* New opportunity zones layer */}
        {showOpportunities &&
          topOpportunities.map((cell, index) => (
            <CircleMarker
              key={`opportunity-${cell.latitude}-${cell.longitude}`}
              center={[
                Number(cell.latitude),
                Number(cell.longitude),
              ]}
              radius={7}
              pathOptions={{
                color: '#fff',
                weight: 1.5,
                fillColor: '#e6a23c',
                fillOpacity: 0.9,
              }}
            >
              <Popup>
                <strong>Opportunity Zone #{index + 1}</strong>
                <br />
                {Number(cell.pings).toLocaleString()} simulated GPS pings
                <br />
                Distance from Store A: {cell.distanceA.toLocaleString()} m
                <br />
                Distance from Store B: {cell.distanceB.toLocaleString()} m
                <br />
                Nearest store: {cell.nearestDistance.toLocaleString()} m
                <br />
                Outside both 500 m catchments
              </Popup>
            </CircleMarker>
          ))}

        {/* Existing Store A catchment */}
        {(showCatchments || showOverlap) && a && (
          <Circle
            center={a}
            radius={500}
            pathOptions={{
              color: '#168b70',
              weight: 2,
              fillColor: '#36b99a',
              fillOpacity: 0.13,
            }}
          >
            <Popup>Store A — configured 500 m catchment</Popup>
          </Circle>
        )}

        {/* Existing Store B catchment */}
        {(showCatchments || showOverlap) && b && (
          <Circle
            center={b}
            radius={500}
            pathOptions={{
              color: '#d58a2a',
              weight: 2,
              fillColor: '#f0b44e',
              fillOpacity: 0.13,
            }}
          >
            <Popup>Store B — configured 500 m catchment</Popup>
          </Circle>
        )}

        {/* Existing Store A marker */}
        {a && (
          <CircleMarker
            center={a}
            radius={8}
            pathOptions={{
              color: '#fff',
              weight: 2,
              fillColor: '#087f5b',
              fillOpacity: 1,
            }}
          >
            <Popup>{storeA?.label || 'Store A'}</Popup>
          </CircleMarker>
        )}

        {/* Existing Store B marker */}
        {b && (
          <CircleMarker
            center={b}
            radius={8}
            pathOptions={{
              color: '#fff',
              weight: 2,
              fillColor: '#d58a2a',
              fillOpacity: 1,
            }}
          >
            <Popup>{storeB?.label || 'Store B'}</Popup>
          </CircleMarker>
        )}
      </MapContainer>
    </div>
  )
}
