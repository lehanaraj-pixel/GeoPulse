
import { useEffect, useState } from 'react'
import './App.css'
import GeoPulseMap from './GeoPulseMap'
import { rankOpportunityLocations } from './opportunityScoring'

const numberFormat = new Intl.NumberFormat('en-IN')

const formatNumber = (value) =>
  numberFormat.format(Math.round(Number(value) || 0))
const formatDecimal = (value) =>
  new Intl.NumberFormat('en-IN', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(Number(value) || 0)

const formatDate = (date) =>
  new Date(`${date}T00:00:00`).toLocaleDateString('en-IN', {
    day: '2-digit',
    month: 'short',
  })

function MetricCard({ label, value, footer, tone = 'lime' }) {
  return (
    <article className={`metric-card ${tone}`}>
      <div className="metric-top">
        <span>{label}</span>
      </div>
      <div className="metric-value">{value}</div>
      <div className="metric-footer">
        <strong>{footer}</strong>
      </div>
    </article>
  )
}

function SectionTitle({ eyebrow, title, description }) {
  return (
    <div className="section-heading">
      <div>
        <div className="eyebrow">{eyebrow}</div>
        <h2>{title}</h2>
        {description && <p className="subtitle">{description}</p>}
      </div>
    </div>
  )
}

function App() {
  const [summary, setSummary] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [period, setPeriod] = useState('30 days')
  const [activeNav, setActiveNav] = useState('Overview')
  const [selectedLayer, setSelectedLayer] = useState('Footfall density')

  useEffect(() => {
    fetch('/data/summary.json')
      .then((response) => {
        if (!response.ok) {
          throw new Error('Could not load GPS summary data.')
        }
        return response.json()
      })
      .then((data) => setSummary(data))
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false))
  }, [])

  if (loading) {
    return (
      <main className="app-shell">
        <div className="page-content">Loading GeoPulse analytics...</div>
      </main>
    )
  }

  if (error || !summary) {
    return (
      <main className="app-shell">
        <div className="page-content">
          Data loading error: {error || 'Summary unavailable'}
        </div>
      </main>
    )
  }

  const daily = summary.daily || []

  const daysToShow =
    period === 'Latest day' ? 1 : period === '7 days' ? 7 : 30

  const selectedDays = daily.slice(-daysToShow)

  const selectedPings = selectedDays.reduce(
    (sum, day) => sum + (Number(day.pings) || 0),
    0,
  )

  const averageDailyDevices = selectedDays.length
    ? selectedDays.reduce(
        (sum, day) => sum + (Number(day.unique_devices) || 0),
        0,
      ) / selectedDays.length
    : 0

  const storeA = summary.stores.store_a
  const storeB = summary.stores.store_b
  const opportunityLocations = rankOpportunityLocations(
  summary.density_grid?.cells || [],
  [Number(storeA.latitude), Number(storeA.longitude)],
  [Number(storeB.latitude), Number(storeB.longitude)],
)
  const overlap = summary.overlap

  const stores = [
    {
      name: 'Store A',
      area: '500 m catchment',
      visitors: storeA.unique_devices,
      pings: storeA.catchment_pings,
      color: '#b6f36b',
    },
    {
      name: 'Store B',
      area: '500 m catchment',
      visitors: storeB.unique_devices,
      pings: storeB.catchment_pings,
      color: '#ff765e',
    },
  ]

  const hourly = summary.hourly || []

  const maxHourly = Math.max(
    ...hourly.map((item) => Number(item.average_daily_unique_devices) || 0),
    1,
  )

  const peakHour = hourly.reduce(
    (peak, item) =>
      Number(item.average_daily_unique_devices) >
      Number(peak.average_daily_unique_devices)
        ? item
        : peak,
    hourly[0] || {
      label: '--',
      average_daily_unique_devices: 0,
    },
  )

  const storeADailyPings = selectedDays.reduce(
    (sum, day) => sum + (Number(day.store_a_pings) || 0),
    0,
  )

  const storeBDailyPings = selectedDays.reduce(
    (sum, day) => sum + (Number(day.store_b_pings) || 0),
    0,
  )

  const storeAExclusive =
    storeA.unique_devices - overlap.unique_devices_in_both

  const storeBExclusive =
    storeB.unique_devices - overlap.unique_devices_in_both

  const navigation = [
    'Overview',
    'Mobility map',
    'Store analytics',
    'Catchment zones',
    'Cannibalization',
  ]

  const periodPicker = (
    <div className="period-picker">
      {['Latest day', '7 days', '30 days'].map((item) => (
        <button
          key={item}
          className={period === item ? 'selected' : ''}
          onClick={() => setPeriod(item)}
        >
          {item}
        </button>
      ))}
    </div>
  )

  const mapPanel = (layer = selectedLayer) => (
    <div className="map-layout">
      <div className="map-canvas">
        <GeoPulseMap
          summary={summary}
          selectedLayer={layer}
        />

        
<div className="map-legend">
  {selectedLayer === 'Opportunity zones' ? (
    <>
      <span>
        <i
          className="legend-lime"
          style={{ background: '#e6a23c' }}
        />{' '}
        Top opportunity cells
      </span>
      <span>
        <i className="legend-lime" /> Store A
      </span>
      <span>
        <i
          className="legend-lime"
          style={{ background: '#d58a2a' }}
        />{' '}
        Store B
      </span>
    </>
  ) : (
    <>
      <span>
        <i className="legend-violet" /> GPS density
      </span>
      <span>
        <i className="legend-lime" /> Store A
      </span>
      <span>
        <i
          className="legend-lime"
          style={{ background: '#d58a2a' }}
        />{' '}
        Store B
      </span>
    </>
  )}
</div>


        
<div className="map-layer-control">
  <small>MAP LAYER</small>
  <select
    value={selectedLayer}
    onChange={(event) => setSelectedLayer(event.target.value)}
  >
    <option>Footfall density</option>
    <option>Store catchments</option>
    <option>Visitor overlap</option>
    <option>Opportunity zones</option>
  </select>
</div>


        <div className="map-disclaimer">
          Aggregated simulated GPS ping density | 250 m grid
        </div>
      </div>
    </div>
  )

  const storePanel = (
    <aside className="store-panel">
      <div className="panel-heading">
        <div>
          <small>LOCATION PERFORMANCE · FULL DATASET</small>
          <h3>Store pulse</h3>
        </div>
      </div>

      {stores.map((store) => (
        <div className="store-row" key={store.name}>
          <span
            className="store-dot"
            style={{ background: store.color }}
          />

          <div className="store-info">
            <strong>{store.name}</strong>
            <small>{store.area}</small>
          </div>

          <strong className="store-visitors">
            {formatNumber(store.visitors)}
          </strong>
        </div>
      ))}

      <div className="store-note">
        Unique simulated devices detected in each catchment
      </div>
    </aside>
  )

  const dailyStoreTable = (
    <div
      style={{
        overflowX: 'auto',
        marginTop: '20px',
        background: 'var(--card-bg, #fff)',
        borderRadius: '14px',
        padding: '16px',
      }}
    >
      <h3>Daily store activity</h3>
      <p className="subtitle">
        Simulated GPS pings and devices · {period}
      </p>

      <table
        style={{
          width: '100%',
          borderCollapse: 'collapse',
          textAlign: 'left',
          fontSize: '13px',
        }}
      >
        <thead>
          <tr>
            {['Date', 'Store A pings', 'Store B pings', 'Store A devices', 'Store B devices'].map(
              (heading) => (
                <th
                  key={heading}
                  style={{
                    padding: '12px 8px',
                    borderBottom: '1px solid #ddd',
                    whiteSpace: 'nowrap',
                  }}
                >
                  {heading}
                </th>
              ),
            )}
          </tr>
        </thead>

        <tbody>
          {selectedDays.map((day) => (
            <tr key={day.date}>
              <td style={{ padding: '11px 8px' }}>
                {formatDate(day.date)}
              </td>
              <td style={{ padding: '11px 8px' }}>
                {formatNumber(day.store_a_pings)}
              </td>
              <td style={{ padding: '11px 8px' }}>
                {formatNumber(day.store_b_pings)}
              </td>
              <td style={{ padding: '11px 8px' }}>
                {formatNumber(day.store_a_unique_devices)}
              </td>
              <td style={{ padding: '11px 8px' }}>
                {formatNumber(day.store_b_unique_devices)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )

  const overview = (
    <>
      <section className="welcome-row">
        <div>
          <div className="eyebrow">
            <span /> RETAIL MOBILITY INTELLIGENCE
          </div>

          <h1>
            See the city<span>.</span>
            <br />
            Find your next <em>move.</em>
          </h1>

          <p className="subtitle">
            Understand footfall patterns, discover high-potential
            locations, and make every store count.
          </p>
        </div>

        {periodPicker}
      </section>

      <section className="metrics-grid">
        <MetricCard
          label="SIMULATED DEVICES"
          value={formatNumber(summary.metadata.unique_devices)}
          footer="Across the full 30-day dataset"
          tone="lime"
        />
        <MetricCard
          label="GPS PINGS"
          value={formatNumber(selectedPings)}
          footer={`${period} selected period`}
          tone="coral"
        />
        <MetricCard
          label="CATCHMENT OVERLAP"
          value={`${overlap.jaccard_percent}%`}
          footer="500 m catchments · full dataset"
          tone="violet"
        />
        <MetricCard
          label="AVG. DAILY ACTIVE DEVICES"
          value={formatNumber(averageDailyDevices)}
          footer={`${formatDecimal(averageDailyDevices)} average · ${selectedDays.length} days`}
          tone="aqua"
        />
      </section>

      <section className="map-section">
        <SectionTitle
          eyebrow="THE BIG PICTURE"
          title={<>Mobility <em>landscape</em></>}
        />

       {mapPanel()}

<article className="analytics-card" style={{ marginTop: '16px', overflowX: 'auto' }}>
  <div className="card-heading">
    <div>
      <small>LOCATION OPPORTUNITY</small>
      <h3>Top 15 potential locations</h3>
    </div>
    <span>OUTSIDE BOTH 500 M CATCHMENTS</span>
  </div>

  <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', fontSize: '12px' }}>
    <thead>
      <tr>
        <th>Rank</th>
        <th>Latitude</th>
        <th>Longitude</th>
        <th>GPS pings</th>
<th>Footfall Score</th>
<th>Separation Score</th>
<th>Opportunity Score</th>
<th>Store A</th>
<th>Store B</th>
      </tr>
    </thead>
    <tbody>
      {opportunityLocations.map((cell, index) => (
        <tr key={`${cell.latitude}-${cell.longitude}`}>
          <td>{index + 1}</td>
          <td>{Number(cell.latitude).toFixed(5)}</td>
          <td>{Number(cell.longitude).toFixed(5)}</td>
          <td>{formatNumber(cell.pings)}</td>
          <td>{formatDecimal(cell.footfallScore)}</td>
<td>{formatDecimal(cell.separationScore)}</td>
<td><strong>{formatDecimal(cell.opportunityScore)}</strong></td>
<td>{formatNumber(cell.distanceA)} m</td>
<td>{formatNumber(cell.distanceB)} m</td>
        </tr>
      ))}
    </tbody>
  </table>

  <p style={{ fontSize: '11px', marginTop: '10px' }}>
    Ranked using a heuristic 70:30 combination of normalized simulated GPS ping density (footfall) and distance from the nearest existing store (separation). GPS pings represent simulated activity, not confirmed customer visits or demand.
  </p>
</article>

<div style={{ marginTop: '16px' }}>
  {storePanel}
</div>
      <section className="bottom-grid">
        <article className="analytics-card">
          <div className="card-heading">
            <div>
              <small>HOURLY ACTIVITY</small>
              <h3>When the city moves</h3>
            </div>
            <span>24 HOURS · FULL 30-DAY AVERAGE</span>
          </div>

          <div className="bar-chart">
            {hourly.map((item) => {
              const height = Math.max(
                3,
                (item.average_daily_unique_devices / maxHourly) * 100,
              )

              return (
                <div className="bar-column" key={item.hour}>
                  <div
                    className="bar"
                    style={{ height: `${height}%` }}
                    title={`${item.label}: ${item.average_daily_unique_devices} average daily devices`}
                  />
                  <small>
                    {item.hour % 2 === 0
                      ? item.label.slice(0, 2)
                      : ''}
                  </small>
                </div>
              )
            })}
          </div>

          <div className="chart-caption">
            <span>
              <i /> Average daily unique devices by hour
            </span>
            <strong>Peak: {peakHour.label}</strong>
          </div>
        </article>

        <article className="opportunity-card">
          <div className="opportunity-icon">✳</div>
          <small>LOCATION OPPORTUNITY</small>
          <h3>
            Find the next
            <br />
            <em>high-street hotspot.</em>
          </h3>

          <p>
            Combine visitor density, store catchments and mobility
            patterns to evaluate promising retail locations.
          </p>

          <button onClick={() => setActiveNav('Catchment zones')}>
            Explore catchments <span>↗</span>
          </button>
        </article>
      </section>
      </section>
    </>
  )

  const mobilityMap = (
    <>
      <SectionTitle
        eyebrow="SPATIAL INTELLIGENCE"
        title={<>Mobility <em>map</em></>}
        description="Explore aggregated simulated GPS density and the configured store catchments."
      />
      {mapPanel()}
    </>
  )

  const storeAnalytics = (
    <>
      <section className="welcome-row">
        <div>
          <div className="eyebrow">RETAIL PERFORMANCE</div>
          <h1>
            Store <em>analytics.</em>
          </h1>
          <p className="subtitle">
            Compare simulated activity across the two configured store catchments.
          </p>
        </div>
        {periodPicker}
      </section>

      <section className="metrics-grid">
        <MetricCard
          label="STORE A DEVICES"
          value={formatNumber(storeA.unique_devices)}
          footer="Full 30-day catchment"
          tone="lime"
        />
        <MetricCard
          label="STORE B DEVICES"
          value={formatNumber(storeB.unique_devices)}
          footer="Full 30-day catchment"
          tone="coral"
        />
        <MetricCard
          label="STORE A PINGS"
          value={formatNumber(storeADailyPings)}
          footer={`${period} selected period`}
          tone="violet"
        />
        <MetricCard
          label="STORE B PINGS"
          value={formatNumber(storeBDailyPings)}
          footer={`${period} selected period`}
          tone="aqua"
        />
      </section>

      <section className="map-section">
        <SectionTitle
          eyebrow="LOCATION COMPARISON"
          title="Store catchments"
        />
        {storePanel}
        {dailyStoreTable}
      </section>
    </>
  )

  const catchmentZones = (
    <>
      <SectionTitle
        eyebrow="LOCATION INTELLIGENCE"
        title={<>Catchment <em>zones.</em></>}
        description="Explore the configured 500 m catchments around Store A and Store B."
      />

      <section className="metrics-grid">
        <MetricCard
          label="CATCHMENT RADIUS"
          value="500 m"
          footer="Configured radius per store"
          tone="lime"
        />
        <MetricCard
          label="STORE A CATCHMENT PINGS"
          value={formatNumber(storeA.catchment_pings)}
          footer="Full dataset"
          tone="coral"
        />
        <MetricCard
          label="STORE B CATCHMENT PINGS"
          value={formatNumber(storeB.catchment_pings)}
          footer="Full dataset"
          tone="violet"
        />
        <MetricCard
          label="SHARED DEVICES"
          value={formatNumber(overlap.unique_devices_in_both)}
          footer="Devices present in both catchments"
          tone="aqua"
        />
      </section>

      {mapPanel('Store catchments')}
      <p className="subtitle">
        Catchment presence represents simulated device observations within
        the configured radius. It does not establish a store visit or purchase.
      </p>
    </>
  )

  const cannibalization = (
    <>
      <SectionTitle
        eyebrow="NETWORK OVERLAP ANALYSIS"
        title={<>Cannibalization <em>intelligence.</em></>}
        description="Evaluate shared simulated device presence between the two store catchments."
      />

      <section className="metrics-grid">
        <MetricCard
          label="CATCHMENT OVERLAP"
          value={`${overlap.jaccard_percent}%`}
          footer="Jaccard similarity · full dataset"
          tone="violet"
        />
        <MetricCard
          label="DEVICES IN BOTH"
          value={formatNumber(overlap.unique_devices_in_both)}
          footer="Shared simulated devices"
          tone="lime"
        />
        <MetricCard
          label="STORE A ONLY"
          value={formatNumber(storeAExclusive)}
          footer="Exclusive to Store A catchment"
          tone="coral"
        />
        <MetricCard
          label="STORE B ONLY"
          value={formatNumber(storeBExclusive)}
          footer="Exclusive to Store B catchment"
          tone="aqua"
        />
      </section>

      <section className="bottom-grid">
        <article className="analytics-card">
          <div className="card-heading">
            <div>
              <small>DEVICE DISTRIBUTION</small>
              <h3>Shared vs exclusive presence</h3>
            </div>
          </div>

          <div style={{ marginTop: '24px' }}>
            {[
              {
                label: 'Shared devices',
                value: overlap.unique_devices_in_both,
                color: '#7968e8',
              },
              {
                label: 'Store A only',
                value: storeAExclusive,
                color: '#36b99a',
              },
              {
                label: 'Store B only',
                value: storeBExclusive,
                color: '#d58a2a',
              },
            ].map((item) => (
              <div key={item.label} style={{ marginBottom: '20px' }}>
                <div
                  style={{
                    display: 'flex',
                    justifyContent: 'space-between',
                    marginBottom: '7px',
                  }}
                >
                  <strong>{item.label}</strong>
                  <strong>{formatNumber(item.value)}</strong>
                </div>
                <div
                  style={{
                    height: '12px',
                    background: '#e9e9e9',
                    borderRadius: '20px',
                    overflow: 'hidden',
                  }}
                >
                  <div
                    style={{
                      width: `${(item.value / overlap.unique_devices_union) * 100}%`,
                      height: '100%',
                      background: item.color,
                      borderRadius: '20px',
                    }}
                  />
                </div>
              </div>
            ))}
          </div>

          <p className="subtitle">
            Total unique devices in the combined catchments:{' '}
            {formatNumber(overlap.unique_devices_union)}
          </p>
        </article>

        <article className="opportunity-card">
          <small>BUSINESS INTERPRETATION</small>
          <h3>
            High shared
            <br />
            <em>mobility presence.</em>
          </h3>
          <p>
            {formatNumber(overlap.unique_devices_in_both)} of{' '}
            {formatNumber(overlap.unique_devices_union)} simulated devices
            appeared in both catchments during the dataset period.
            This indicates substantial spatial overlap and warrants
            further investigation.
          </p>
          <p>
            It does not prove that customers visited both stores,
            switched between them, or made purchases.
          </p>
        </article>
      </section>

      <section className="analytics-card" style={{ marginTop: '20px' }}>
        <small>ADDITIONAL OVERLAP INDICATORS</small>
        <h3>Catchment relationship</h3>

        <div className="metrics-grid" style={{ marginTop: '18px' }}>
          <MetricCard
            label="STORE A DEVICES ALSO IN B"
            value={`${overlap.store_a_devices_also_in_b}%`}
            footer="Full dataset"
            tone="lime"
          />
          <MetricCard
            label="STORE B DEVICES ALSO IN A"
            value={`${overlap.store_b_devices_also_in_a}%`}
            footer="Full dataset"
            tone="coral"
          />
          <MetricCard
            label="PINGS INSIDE BOTH"
            value={formatNumber(overlap.pings_inside_both)}
            footer="Aggregated ping observations"
            tone="violet"
          />
        </div>
      </section>
    </>
  )

  const pageContent = {
    Overview: overview,
    'Mobility map': mobilityMap,
    'Store analytics': storeAnalytics,
    'Catchment zones': catchmentZones,
    Cannibalization: cannibalization,
  }

  return (
    <main className="app-shell">
      <aside className="sidebar">
        <div className="brand">
          <div className="brand-mark">G</div>
          <div>
            <strong>
              GeoPulse<span>.</span>
            </strong>
            <small>SPATIAL INTELLIGENCE</small>
          </div>
        </div>

        <div className="workspace-label">WORKSPACE</div>

        <nav>
          {navigation.map((item, index) => (
            <button
              key={item}
              className={`nav-item ${
                activeNav === item ? 'active' : ''
              }`}
              onClick={() => setActiveNav(item)}
            >
              <span className="nav-icon">
                {['◉', '⌖', '▥', '◎', '⇄'][index]}
              </span>
              {item}
              {item === 'Mobility map' && (
                <span className="nav-tag">DATA</span>
              )}
            </button>
          ))}
        </nav>

        <div className="sidebar-bottom">
          <div className="data-status">
            <span className="status-dot" />
            <div>
              <strong>SYNTHETIC DATA</strong>
              <small>
                {formatNumber(summary.metadata.processed_pings)} GPS pings loaded
              </small>
            </div>
          </div>

          <div className="profile">
            <div className="avatar">GP</div>
            <div>
              <strong>Retail Insights</strong>
              <small>Analytics workspace</small>
            </div>
            <span>···</span>
          </div>
        </div>
      </aside>

      <section className="main-content">
        <header className="topbar">
          <div className="breadcrumb">
            Workspace <span>/</span> <strong>{activeNav}</strong>
          </div>

          <div className="top-actions">
            <span className="live-indicator">
              <i /> DATA CONNECTED
            </span>
            <div className="top-avatar">R</div>
          </div>
        </header>

        <div className="page-content">
          {pageContent[activeNav]}

          <footer className="footer">
            <span>GEOPULSE © 2026 · RETAIL MOBILITY ANALYTICS</span>
            <span>
              SYNTHETIC GPS DATA · {summary.metadata.timezone}
            </span>
          </footer>

          <p className="subtitle">{summary.disclaimer}</p>
        </div>
      </section>
    </main>
  )
}

export default App
