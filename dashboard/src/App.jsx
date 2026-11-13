
import { useEffect, useState } from 'react'
import './App.css'
import GeoPulseMap from './GeoPulseMap'

const numberFormat = new Intl.NumberFormat('en-IN')

const formatNumber = (value) =>
  numberFormat.format(Math.round(value || 0))

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
    period === 'Today' ? 1 : period === '7 days' ? 7 : 30

  const selectedDays = daily.slice(-daysToShow)

  const selectedPings = selectedDays.reduce(
    (sum, day) => sum + day.pings,
    0,
  )

  const averageDailyDevices = selectedDays.length
    ? selectedDays.reduce(
        (sum, day) => sum + day.unique_devices,
        0,
      ) / selectedDays.length
    : 0

  const stores = [
    {
      name: 'Store A',
      area: '500 m catchment',
      visitors: summary.stores.store_a.unique_devices,
      pings: summary.stores.store_a.catchment_pings,
      color: '#b6f36b',
    },
    {
      name: 'Store B',
      area: '500 m catchment',
      visitors: summary.stores.store_b.unique_devices,
      pings: summary.stores.store_b.catchment_pings,
      color: '#ff765e',
    },
  ]

  const metrics = [
    {
      label: 'SIMULATED DEVICES',
      value: formatNumber(summary.metadata.unique_devices),
      icon: '◉',
      tone: 'lime',
      footer: 'Across the full 30-day dataset',
    },
    {
      label: 'GPS PINGS',
      value: formatNumber(selectedPings),
      icon: '↗',
      tone: 'coral',
      footer: `${period} selected period`,
    },
    {
      label: 'CATCHMENT OVERLAP',
      value: `${summary.overlap.jaccard_percent}%`,
      icon: '◎',
      tone: 'violet',
      footer: '500 m catchment · full dataset',
    },
    {
      label: 'AVG. DAILY ACTIVE DEVICES',
      value: formatNumber(averageDailyDevices),
      icon: '◷',
      tone: 'aqua',
      footer: `Average across ${selectedDays.length} day(s)`,
    },
  ]

  const hourly = summary.hourly || []

  const maxHourly = Math.max(
    ...hourly.map((item) => item.average_daily_unique_devices),
    1,
  )

  const peakHour = hourly.reduce(
    (peak, item) =>
      item.average_daily_unique_devices >
      peak.average_daily_unique_devices
        ? item
        : peak,
    hourly[0] || {
      label: '--',
      average_daily_unique_devices: 0,
    },
  )

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
          {[
            'Overview',
            'Mobility map',
            'Store analytics',
            'Catchment zones',
            'Cannibalization',
          ].map((item, i) => (
            <button
              key={item}
              className={`nav-item ${
                activeNav === item ? 'active' : ''
              }`}
              onClick={() => setActiveNav(item)}
            >
              <span className="nav-icon">
                {['◉', '⌖', '▥', '◎', '⇄'][i]}
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
              <small>1M GPS pings loaded</small>
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
            <button className="icon-button" aria-label="Notifications">
              ♧
            </button>
            <div className="top-avatar">R</div>
          </div>
        </header>

        <div className="page-content">
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

            <div className="period-picker">
              {['Today', '7 days', '30 days'].map((item) => (
                <button
                  key={item}
                  className={period === item ? 'selected' : ''}
                  onClick={() => setPeriod(item)}
                >
                  {item}
                </button>
              ))}
            </div>
          </section>

          <section className="metrics-grid">
            {metrics.map((metric) => (
              <article
                className={`metric-card ${metric.tone}`}
                key={metric.label}
              >
                <div className="metric-top">
                  <span>{metric.label}</span>
                  <span className="metric-icon">{metric.icon}</span>
                </div>

                <div className="metric-value">{metric.value}</div>

                <div className="metric-footer">
                  <strong>{metric.footer}</strong>
                </div>
              </article>
            ))}
          </section>

          <section className="map-section">
            <div className="section-heading">
              <div>
                <div className="eyebrow">THE BIG PICTURE</div>
                <h2>
                  Mobility <em>landscape</em>
                </h2>
              </div>

              <button
                className="outline-button"
                onClick={() => setActiveNav('Mobility map')}
              >
                ⌖ Explore map
              </button>
            </div>

            <div className="map-layout">
              <div className="map-canvas">
                <GeoPulseMap
                  summary={summary}
                  selectedLayer={selectedLayer}
                />

                <div className="map-legend">
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
                </div>

                <div className="map-layer-control">
                  <small>MAP LAYER</small>
                  <select
                    value={selectedLayer}
                    onChange={(e) => setSelectedLayer(e.target.value)}
                  >
                    <option>Footfall density</option>
                    <option>Store catchments</option>
                    <option>Visitor overlap</option>
                  </select>
                </div>

                <div className="map-disclaimer">
                  Aggregated simulated GPS ping density · 250 m grid
                </div>
              </div>

              <aside className="store-panel">
                <div className="panel-heading">
                  <div>
                    <small>LOCATION PERFORMANCE</small>
                    <h3>Store pulse</h3>
                  </div>
                  <span>···</span>
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
                  <span>↗</span> Unique simulated devices detected in
                  each catchment
                </div>
              </aside>
            </div>
          </section>

          <section className="bottom-grid">
            <article className="analytics-card">
              <div className="card-heading">
                <div>
                  <small>HOURLY ACTIVITY</small>
                  <h3>When the city moves</h3>
                </div>
                <span>24 HOURS · DAILY AVERAGE</span>
              </div>

              <div className="bar-chart">
                {hourly.map((item) => {
                  const height = Math.max(
                    3,
                    (item.average_daily_unique_devices / maxHourly) *
                      100,
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
