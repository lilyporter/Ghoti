import React, { useEffect, useRef } from 'react'
import './dashboard.css'
import Mascot from './Mascot'

// Fictional dashboard records. The playback buttons use the real demo recordings.
const attempts = [
  { word: 'sun', try: 2, target: '/s/ · Initial', score: 72, review: 'Needs cue', time: '0:03' },
  { word: 'gift', try: 1, target: '/g/ · Initial', score: 82, review: 'Confirmed', time: '0:02' },
  { word: 'seal', try: 2, target: '/s/ · Initial', score: 79, review: 'Pending review', time: '0:03' },
  { word: 'sheep', try: 1, target: '/ʃ/ · Initial', score: 83, review: 'Pending review', time: '0:02' },
  { word: 'soup', try: 1, target: '/s/ · Initial', score: 86, review: 'Confirmed', time: '0:03' },
]

function TrendChart() {
  return <div className="dash-chart" role="img" aria-label="Example progress chart: initial s rises from 58 to 78 percent over six sessions; final s rises from 50 to 63 percent">
    <div className="dash-chart-labels"><span>100%</span><span>75%</span><span>50%</span><span>25%</span><span>0%</span></div>
    <div className="dash-chart-plot">
      <svg viewBox="0 0 600 164" preserveAspectRatio="none" aria-hidden="true">
        {[0, 40, 80, 120, 160].map(y => <line key={y} x1="0" x2="600" y1={y} y2={y} stroke="#e4e9ef" />)}
        <polyline points="0,96 120,90 240,83 360,79 480,73 600,67" fill="none" stroke="#3678ed" strokeWidth="2.5" />
        <polyline points="0,110 120,106 240,102 360,99 480,95 600,92" fill="none" stroke="#4f967c" strokeWidth="2" strokeDasharray="6 4" />
        {[[0,96],[120,90],[240,83],[360,79],[480,73],[600,67]].map(([x,y]) => <circle key={`a${x}`} cx={x} cy={y} r="4" fill="#3678ed" stroke="white" strokeWidth="1.5" />)}
        {[[0,110],[120,106],[240,102],[360,99],[480,95],[600,92]].map(([x,y]) => <circle key={`b${x}`} cx={x} cy={y} r="3.5" fill="#4f967c" stroke="white" strokeWidth="1.5" />)}
      </svg>
      <div className="dash-chart-dates"><span>Sep 19</span><span>Sep 23</span><span>Sep 26</span><span>Sep 30</span><span>Oct 3</span><span>Oct 7</span></div>
    </div>
  </div>
}

export default function SessionDashboard({ samples, onDemo }) {
  const playingRef = useRef(null)
  useEffect(() => () => playingRef.current?.pause(), [])
  function play(word) {
    const sample = samples.find(item => item.target_word === word)
    if (!sample) return
    playingRef.current?.pause()
    const audio = new Audio(sample.audio_url)
    playingRef.current = audio
    audio.play().catch(() => {})
  }

  return <div className="dashboard">
    <aside className="dash-sidebar">
      <div className="dash-brand"><Mascot small /> PronouncedFish</div>
      <nav aria-label="Dashboard navigation">
        <button onClick={onDemo}><span aria-hidden="true">▦</span> Audio demo</button>
        <span className="dash-nav-active"><span aria-hidden="true">▥</span> Session analysis</span>
      </nav>
      <div className="dash-clinician"><span className="dash-avatar small">JL</span><span><strong>Jordan Lee, SLP</strong><small>Example clinician</small></span></div>
    </aside>

    <div className="dash-main-area">
      <header className="dash-topbar"><span>Maya Chen</span><span>English (US) <span className="dash-top-icons" aria-hidden="true">ⓘ &nbsp; ♧</span></span></header>
      <main className="dash-content">
        <div className="dash-profile"><span className="dash-avatar">MC</span><div><h1>Maya Chen</h1><p>Age 5 · English (US)</p></div><button onClick={onDemo}>+ Try a recording</button></div>
        <div className="dash-tabs"><span className="active">Progress &amp; sessions</span><span>Practice plan</span><span>Mouth map</span><span>Notes</span></div>

        <div className="dash-overview">
          <section className="dash-card dash-trends"><div className="dash-card-heading"><div><h2>Sound-level trends</h2><p>Example accuracy estimates · Across sample sessions</p></div><div className="dash-filters"><span>✓ &nbsp; /s/</span><span>⌄ &nbsp; All positions</span></div></div><TrendChart/><div className="dash-legend"><span><i className="blue-line"/> /s/ · Initial · Word</span><span><i className="green-line"/> /s/ · Final · Word</span><small>Session date →</small></div></section>
          <section className="dash-card dash-latest"><div className="dash-card-heading"><h2>Latest session</h2><span className="dash-pill neutral">6 to review</span></div><h3>Sunny Reef</h3><p>Oct 7, 2026 · 10:20 AM · 10 min</p><div className="dash-metrics"><div><strong>10</strong><span>Prompts</span></div><div><strong>14</strong><span>Attempts</span></div><div><strong>8</strong><span>Reviewed</span></div></div><div className="dash-estimate"><strong>78%</strong><span>Example accuracy estimate<small>/s/ initial · 74% previous session</small></span></div></section>
        </div>

        <section className="dash-card dash-attempts"><div className="dash-attempts-header"><div><h2>Session attempts</h2><span>Oct 7 · Sunny Reef</span></div><span className="dash-pill blue">Showing 5 of 14 example attempts</span></div><div className="dash-table-wrap"><table><thead><tr><th>Word / attempt</th><th>Target / position</th><th>Example estimate</th><th>Example review</th><th>Playback</th></tr></thead><tbody>{attempts.map(row => <tr key={row.word}><td><strong>{row.word.toUpperCase()}</strong><small>Try {row.try}</small></td><td>{row.target}</td><td><strong>{row.score}%</strong></td><td><span className={`dash-pill ${row.review === 'Confirmed' ? 'confirmed' : row.review === 'Needs cue' ? 'neutral' : 'blue'}`}>{row.review}</span></td><td><button className="dash-play" onClick={() => play(row.word)} aria-label={`Play ${row.word} recording`}>▷</button><small>{row.time}</small></td></tr>)}</tbody></table></div><div className="dash-table-footer"><button onClick={onDemo}>Open audio demo →</button></div></section>
        <section className="dash-note"><span aria-hidden="true">✎</span><div><strong>Jordan Lee · Today, 10:35 AM</strong><p>SUN: /s/ still needed a model and visual cue. Continue initial words; allow a second try without rushing.</p></div><span className="dash-note-tag">Example note</span></section>
      </main>
    </div>
  </div>
}
