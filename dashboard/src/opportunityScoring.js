
const EARTH_RADIUS_METERS = 6371008.8

function getDistanceMeters(lat1, lon1, lat2, lon2) {
  const rad = Math.PI / 180
  const dLat = (lat2 - lat1) * rad
  const dLon = (lon2 - lon1) * rad

  const value =
    Math.sin(dLat / 2) ** 2 +
    Math.cos(lat1 * rad) *
      Math.cos(lat2 * rad) *
      Math.sin(dLon / 2) ** 2

  return (
    2 *
    EARTH_RADIUS_METERS *
    Math.atan2(Math.sqrt(value), Math.sqrt(1 - value))
  )
}

function normalize(value, min, max) {
  return max === min ? 0 : ((value - min) / (max - min)) * 100
}

export function rankOpportunityLocations(cells, storeA, storeB) {
  if (!storeA || !storeB) return []

  const eligible = (cells || [])
    .map((cell) => {
      const latitude = Number(cell.latitude)
      const longitude = Number(cell.longitude)

      const exactDistanceA = getDistanceMeters(
        latitude, longitude, storeA[0], storeA[1]
      )
      const exactDistanceB = getDistanceMeters(
        latitude, longitude, storeB[0], storeB[1]
      )

      return {
        ...cell,
        exactDistanceA,
        exactDistanceB,
        distanceA: Math.round(exactDistanceA),
        distanceB: Math.round(exactDistanceB),
        nearestDistance: Math.min(exactDistanceA, exactDistanceB),
      }
    })
    .filter(
      (cell) =>
        Number.isFinite(cell.exactDistanceA) &&
        Number.isFinite(cell.exactDistanceB) &&
        cell.exactDistanceA > 500 &&
        cell.exactDistanceB > 500 &&
        Number.isFinite(Number(cell.pings))
    )

  if (!eligible.length) return []

  const pings = eligible.map((cell) => Number(cell.pings))
  const distances = eligible.map((cell) => cell.nearestDistance)

  const minPings = Math.min(...pings)
  const maxPings = Math.max(...pings)
  const minDistance = Math.min(...distances)
  const maxDistance = Math.max(...distances)

  return eligible
    .map((cell) => {
      const footfallScore = normalize(
        Number(cell.pings), minPings, maxPings
      )
      const separationScore = normalize(
        cell.nearestDistance, minDistance, maxDistance
      )

      return {
        ...cell,
        footfallScore,
        separationScore,
        opportunityScore:
          0.70 * footfallScore + 0.30 * separationScore,
      }
    })
    .sort((a, b) => b.opportunityScore - a.opportunityScore)
    .slice(0, 15)
}
