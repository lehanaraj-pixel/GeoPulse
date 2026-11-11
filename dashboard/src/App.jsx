
import { useState } from 'react'
import './App.css'

const metrics = [
  { label: 'UNIQUE VISITORS', value: '24,892', change: '+12.8%', icon: '◉', tone: 'lime' },
  { label: 'TOTAL FOOTFALL', value: '38,416', change: '+8.4%', icon: '↗', tone: 'coral' },
  { label: 'STORE OVERLAP', value: '18.6%', change: '-2.3%', icon: '◎', tone: 'violet' },
  { label: 'AVG. DWELL TIME', value: '42 min', change: '+6.2%', icon: '◷', tone: 'aqua' },
]

const stores = [
  { name: 'Brew District', area: 'Central Avenue', visitors: '8,420', color: '#b6f36b' },
  { name: 'The Daily Grind', area: 'Riverside Plaza', visitors: '6,185', color: '#ff765e' },
  { name: 'Bean Theory', area: 'North Market', visitors: '4,920', color: '#9b83ff' },
]

const bars = [28, 35, 31, 48, 66, 84, 73, 57, 91, 100, 78, 62]

function App() {
  const [period, setPeriod] = useState('Today')
  const [activeNav, setActiveNav] = useState('Overview')
  const [selectedLayer, setSelectedLayer] = useState('Footfall density')

  return (
    <main className="app-shell">
      <aside className="sidebar">
        <div className="brand">
          <div className="brand-mark">G</div>
          <div>
            <strong>GeoPulse<span>.</span></strong>
            <small>SPATIAL INTELLIGENCE</small>
          </div>
        </div>

        <div className="workspace-label">WORKSPACE</div>
        <nav>
          {['Overview', 'Mobility map', 'Store analytics', 'Catchment zones', 'Cannibalization'].map((item, i) => (
            <button
              key={item}
              className={`nav-item ${activeNav === item ? 'active' : ''}`}
              onClick={() => setActiveNav(item)}
            >
              <span className="nav-icon">{['◫', '⌖', '▥', '◉', '⇄'][i]}</span>
              {item}
              {item === 'Mobility map' && <span className="nav-tag">LIVE</span>}
            </button>
          ))}
        </nav>

        <div className="sidebar-bottom">
          <div className="data-status">
            <span className="status-dot" />
            <div><strong>DEMO DATA</strong><small>Illustrative dataset</small></div>
          </div>
          <div className="profile">
            <div className="avatar">GP</div>
            <div><strong>Retail Insights</strong><small>Analytics workspace</small></div>
            <span>···</span>
          </div>
        </div>
      </aside>

      <section className="main-content">
        <header className="topbar">
          <div className="breadcrumb">Workspace <span>/</span> <strong>{activeNav}</strong></div>
          <div className="top-actions">
            <span className="live-indicator"><i /> DEMO ENVIRONMENT</span>
            <button className="icon-button" aria-label="Notifications">♧</button>
            <div className="top-avatar">R</div>
          </div>
        </header>

        <div className="page-content">
          <section className="welcome-row">
            <div>
              <div className="eyebrow"><span /> RETAIL MOBILITY INTELLIGENCE</div>
              <h1>See the city<span>.</span><br />Find your next <em>move.</em></h1>
              <p className="subtitle">Understand footfall, discover high-potential locations, and make every store count.</p>
            </div>
            <div className="period-picker">
              {['Today', '7 days', '30 days'].map(item => (
                <button key={item} className={period === item ? 'selected' : ''} onClick={() => setPeriod(item)}>
                  {item}
                </button>
              ))}
            </div>
          </section>

          <section className="metrics-grid">
            {metrics.map(metric => (
              <article className={`metric-card ${metric.tone}`} key={metric.label}>
                <div className="metric-top">
                  <span>{metric.label}</span>
                  <span className="metric-icon">{metric.icon}</span>
                </div>
                <div className="metric-value">{metric.value}</div>
                <div className="metric-footer"><strong>{metric.change}</strong><span> vs previous period</span></div>
              </article>
            ))}
          </section>

          <section className="map-section">
            <div className="section-heading">
              <div>
                <div className="eyebrow">THE BIG PICTURE</div>
                <h2>Mobility <em>landscape</em></h2>
              </div>
              <button className="outline-button">⌖ Explore map</button>
            </div>

            <div className="map-layout">
              <div className="map-canvas">
                <div className="map-grid" />
                <svg className="map-art" viewBox="0 0 900 440" preserveAspectRatio="xMidYMid slice" aria-label="Illustrative retail mobility map">
                  <g className="roads">
                    <path d="M-30 95 L220 145 L430 80 L680 150 L940 75" />
                    <path d="M-20 260 L180 205 L390 275 L600 215 L940 300" />
                    <path d="M130 -20 L210 150 L170 310 L260 470" />
                    <path d="M390 -20 L430 80 L390 275 L470 470" />
                    <path d="M690 -20 L680 150 L720 290 L680 470" />
                    <path d="M-20 380 L180 205 L430 80 L600 -20" />
                    <path d="M220 145 L390 275 L600 215 L810 400" />
                  </g>
                  <g className="minor-roads">
                    <path d="M40 170 L300 220 L510 165 L850 230" />
                    <path d="M300 0 L320 160 L290 440" />
                    <path d="M550 0 L530 180 L570 440" />
                    <path d="M0 330 L250 310 L490 350 L900 330" />
                  </g>
                  <g className="map-zones">
                    <circle cx="250" cy="165" r="88" fill="#b6f36b" />
                    <circle cx="585" cy="220" r="104" fill="#9b83ff" />
                    <circle cx="430" cy="330" r="70" fill="#ff765e" />
                  </g>
                  <g className="map-points">
                    <circle cx="250" cy="165" r="13" />
                    <circle cx="585" cy="220" r="13" />
                    <circle cx="430" cy="330" r="13" />
                  </g>
                </svg>
                <div className="map-label label-one"><i /> BREW DISTRICT</div>
                <div className="map-label label-two"><i /> DAILY GRIND</div>
                <div className="map-label label-three"><i /> BEAN THEORY</div>
                <div className="map-legend">
                  <span><i className="legend-lime" /> High density</span>
                  <span><i className="legend-violet" /> Medium density</span>
                  <span><i className="legend-coral" /> Low density</span>
                </div>
                <div className="map-layer-control">
                  <small>MAP LAYER</small>
                  <select value={selectedLayer} onChange={e => setSelectedLayer(e.target.value)}>
                    <option>Footfall density</option>
                    <option>Store catchments</option>
                    <option>Visitor overlap</option>
                  </select>
                </div>
                <div className="map-disclaimer">Illustrative map · Not actual GPS observations</div>
              </div>

              <aside className="store-panel">
                <div className="panel-heading"><div><small>LOCATION PERFORMANCE</small><h3>Store pulse</h3></div><span>•••</span></div>
                {stores.map(store => (
                  <div className="store-row" key={store.name}>
                    <span className="store-dot" style={{ background: store.color }} />
                    <div className="store-info"><strong>{store.name}</strong><small>{store.area}</small></div>
                    <strong className="store-visitors">{store.visitors}</strong>
                  </div>
                ))}
                <div className="store-note"><span>↗</span> Sample store metrics for interface demonstration.</div>
              </aside>
            </div>
          </section>

          <section className="bottom-grid">
            <article className="analytics-card">
              <div className="card-heading"><div><small>TRAFFIC PATTERNS</small><h3>When the city moves</h3></div><span>24 HOURS</span></div>
              <div className="bar-chart">
                {bars.map((height, i) => (
                  <div className="bar-column" key={i}>
                    <div className="bar" style={{ height: `${height}%` }} />
                    <small>{['6a', '8a', '10a', '12p', '2p', '4p', '6p', '8p', '10p', '12a', '2a', '4a'][i]}</small>
                  </div>
                ))}
              </div>
              <div className="chart-caption"><span><i /> Illustrative hourly footfall distribution</span><strong>Peak: 10 AM</strong></div>
            </article>

            <article className="opportunity-card">
              <div className="opportunity-icon">✳</div>
              <small>LOCATION OPPORTUNITY</small>
              <h3>Find the next<br /><em>high-street hotspot.</em></h3>
              <p>Combine visitor density, store overlap and catchment reach to evaluate promising retail locations.</p>
              <button onClick={() => setActiveNav('Catchment zones')}>Explore catchments <span>↗</span></button>
            </article>
          </section>

          <footer className="footer">
            <span>GEOPULSE © 2026 · HYPER-LOCAL RETAIL MOBILITY ANALYTICS</span>
            <span>DEMO INTERFACE · SAMPLE VALUES ONLY</span>
          </footer>
        </div>
      </section>
    </main>
  )
}

export default App
