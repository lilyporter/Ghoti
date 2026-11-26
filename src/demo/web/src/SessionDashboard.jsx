import React, { useEffect, useRef, useState } from 'react'
import './dashboard.css'
import Mascot from './Mascot'
import maya from './maya.json'
import overviewIcon from './assets/overview.svg'
import caseloadIcon from './assets/caseload.svg'
import sessionIcon from './assets/session.svg'
import practiceIcon from './assets/practice.svg'
import notesIcon from './assets/notes.svg'

function ProgressHistory({ history }) {
  const series = ['Initial', 'Final'].map((position, seriesIndex) => ({
    position,
    color: seriesIndex === 0 ? '#1473e6' : '#27866d',
    points: history.map(({ attempts }, index) => {
      const tokens = attempts.flatMap(({ analysis }) => {
        if (analysis.status !== 'ok') return []
        const targetIndex = seriesIndex === 0 ? 0 : analysis.expected_phones.length - 1
        return analysis.alignment.filter(token => token.expected_index === targetIndex && token.expected_phone === 's')
      })
      const matched = tokens.filter(token => token.kind === 'match').length
      return {
        x: 50 + index * 490 / Math.max(1, history.length - 1),
        y: tokens.length ? 180 - 160 * matched / tokens.length : null,
        matched,
        total: tokens.length,
      }
    }),
  }))
  return <section className="dash-card dash-history">
    <div className="dash-card-heading"><div><h2>Sound-level trends</h2><p>Pasketti target matches · Penney recording sessions</p></div><span className="dash-pill">/s/</span></div>
    {history.length ? <svg className="dash-history-chart" viewBox="0 0 580 220" role="img" aria-labelledby="trend-title">
      <title id="trend-title">{series.map(({ position, points }) => position + ' /s/: ' + points.map(({ matched, total }) => matched + ' of ' + total).join(', ')).join('. ')}</title>
      {[0, 25, 50, 75, 100].map(value => <g key={value}><text x="0" y={184 - value * 1.6}>{value}%</text><line x1="50" x2="540" y1={180 - value * 1.6} y2={180 - value * 1.6}/></g>)}
      {series.map(({ position, color, points }) => <g key={position}>
        {points.map(({ x, y, matched, total }, index) => y !== null && <g key={history[index].id}>
          {index > 0 && points[index - 1].y !== null && <path d={`M${points[index - 1].x},${points[index - 1].y} L${x},${y}`} fill="none" stroke={color} strokeWidth="2" strokeDasharray={position === 'Final' ? '6 4' : undefined}/>}
          <circle cx={x} cy={y} r="4" fill={color}><title>{position} /s/ · {matched}/{total} matched</title></circle>
        </g>)}
      </g>)}
      {history.map(({ id }, index) => <text key={id} x={series[0].points[index].x} y="208" textAnchor="middle">Session {index + 1}</text>)}
    </svg> : <p className="dash-loading">No recording history available.</p>}
    <div className="dash-legend"><span><i className="blue-line"/> /s/ · Initial</span><span><i className="green-line"/> /s/ · Final</span></div>
  </section>
}

function phoneText(phones, brackets = false) {
  if (!phones?.length) return '—'
  return brackets ? `[${phones.join(' ')}]` : `/${phones.join(' ')}/`
}

function differences(analysis) {
  if (analysis?.status !== 'ok') return 'Could not assess'
  const changes = analysis.alignment.filter(row => row.kind !== 'match')
  if (!changes.length) return 'Sounds matched'
  return changes.map(row => {
    if (row.kind === 'substitution') return `${phoneText([row.expected_phone])} → [${row.recognized_phone}]`
    if (row.kind === 'omission') return `Missing ${phoneText([row.expected_phone])}`
    return `Extra [${row.recognized_phone}]`
  }).join(' · ')
}

export default function SessionDashboard({ samples, sampleError }) {
  const [session, setSession] = useState(null)
  const [history, setHistory] = useState([])
  const [historyError, setHistoryError] = useState(false)
  const [selectedHistory, setSelectedHistory] = useState(null)
  const [error, setError] = useState('')
  const [playError, setPlayError] = useState('')
  const playingRef = useRef(null)

  useEffect(() => {
    const controller = new AbortController()
    fetch('/api/history', { signal: controller.signal })
      .then(response => {
        if (!response.ok) throw Error()
        return response.json()
      })
      .then(setHistory)
      .catch(error => { if (error.name !== 'AbortError') setHistoryError(true) })
    return () => controller.abort()
  }, [])

  useEffect(() => {
    let stopped = false
    let timer
    const controller = new AbortController()

    async function loadSession() {
      try {
        const response = await fetch('/api/analysis', { signal: controller.signal })
        if (!response.ok) throw Error('Could not load the session.')
        const data = await response.json()
        if (!stopped) {
          setSession(data)
          setError('')
        }
      } catch (error) {
        if (!stopped) setError(error.message)
      } finally {
        if (!stopped) timer = setTimeout(loadSession, 2000)
      }
    }

    loadSession()
    return () => {
      stopped = true
      controller.abort()
      clearTimeout(timer)
      playingRef.current?.pause()
    }
  }, [])

  const byId = new Map((session?.results || []).map(result => [result.sample_id, result]))
  const rows = samples.map(sample => ({ sample, result: byId.get(sample.id) })).filter(row => row.result)
  const historyIndex = history.findIndex(item => item.id === selectedHistory)
  const attemptRows = historyIndex < 0 ? rows : history[historyIndex].attempts.map(result => ({
    result,
    sample: { id: result.sample_id, target_word: result.target_word, audio_url: '/api/history/' + encodeURIComponent(result.sample_id) + '/audio' },
  }))
  const exact = rows.filter(row => row.result.analysis.matches_target).length
  const withChanges = rows.filter(row => row.result.analysis.status === 'ok' && !row.result.analysis.matches_target).length
  const unassessable = rows.length - exact - withChanges

  function selectSession(id) {
    setSelectedHistory(id)
    setPlayError('')
    playingRef.current?.pause()
  }

  function play(sample) {
    playingRef.current?.pause()
    setPlayError('')
    const audio = new Audio(sample.audio_url)
    playingRef.current = audio
    audio.play().catch(() => setPlayError(`Could not play ${sample.target_word}.`))
  }

  return <div className="dashboard">
    <aside className="dash-sidebar">
      <div className="dash-brand"><Mascot small /> PronouncedFish</div>
      <nav aria-label="Patient record">
        <a className="dash-nav-item" href="#patient"><span><img src={overviewIcon} alt=""/></span>Overview</a>
        <a className="dash-nav-item" href="#history"><span><img src={caseloadIcon} alt=""/></span>Previous sessions</a>
        <a className="dash-nav-item dash-nav-active" href="#session"><span><img src={sessionIcon} alt=""/></span>Session analysis</a>
        <a className="dash-nav-item" href="#practice"><span><img src={practiceIcon} alt=""/></span>Practice plan</a>
        <a className="dash-nav-item" href="#notes"><span className="dash-nav-note"><img src={notesIcon} alt=""/></span>Clinical notes</a>
      </nav>
      <div className="dash-clinician"><span className="dash-avatar small">JL</span><span><strong>Jordan Lee, SLP</strong><small>Clinician</small></span></div>
    </aside>

    <div className="dash-main-area">
      <main className="dash-content">
        <div id="patient" className="dash-profile"><span className="dash-avatar">MC</span><div><h1>Maya Chen</h1><p>Age 7 · English (US)</p></div></div>
        <nav className="dash-tabs" aria-label="Maya Chen’s record">
          <a href="#session">Progress &amp; sessions</a>
          <a href="#practice">Practice plan</a>
          <a href="#notes">Notes</a>
        </nav>
        {(error || sampleError) && <p className="dash-load-error" role="alert">{error || sampleError}</p>}
        {!error && !sampleError && !rows.length && <p className="dash-loading">
          {session && samples.length ? 'Complete an iPad session to see its results.' : 'Loading session…'}
        </p>}

        <div id="session" className="dash-overview dash-session-overview">
          <ProgressHistory history={history} />
          {rows.length > 0 && <section className="dash-card dash-latest" aria-labelledby="session-heading">
            <div className="dash-card-heading">
              <h2 id="session-heading">{session.completed_at ? 'Latest session' : 'Example session'}</h2>
              {withChanges > 0 && <span className="dash-pill dash-change-pill">{withChanges} with changes</span>}
            </div>
            <h3>Sunny Reef</h3>
            {session.completed_at && <time dateTime={session.completed_at}>{new Date(session.completed_at).toLocaleString([], { month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' })}</time>}
            <div className="dash-session-score" role="status">
              <strong>{exact} / {rows.length}</strong>
              <span>Model word matches{unassessable > 0 && <small>{unassessable} unassessed</small>}</span>
            </div>
          </section>}
        </div>

        {attemptRows.length > 0 && <>
          <section id="attempts" className="dash-card dash-attempts" aria-labelledby="attempts-heading">
            <div className="dash-attempts-header">
              <div><h2 id="attempts-heading">{historyIndex < 0 ? "Session attempts" : `Session ${historyIndex + 1} attempts`}</h2><span>{attemptRows.length} attempts</span></div>
              {historyIndex >= 0 && <button className="dash-text-button" onClick={() => selectSession(null)}>Current session</button>}
            </div>
            {playError && <p className="dash-load-error" role="alert">{playError}</p>}
            <div className="dash-table-wrap"><table><thead><tr><th>Word</th><th>Target phones</th><th>Model output</th><th>Comparison</th><th>Playback</th></tr></thead><tbody>
              {attemptRows.map(({ sample, result }) => <tr key={sample.id}>
                <td><strong>{sample.target_word}</strong></td>
                <td className="dash-phone">{phoneText(result.analysis.expected_phones)}</td>
                <td className="dash-phone">{phoneText(result.recognition.recognized_phones, true)}</td>
                <td className="dash-differences">{result.analysis.matches_target ? <span className="dash-match">Match</span> : differences(result.analysis)}</td>
                <td><button className="dash-play" onClick={() => play(sample)} aria-label={`Play ${sample.target_word} recording`}><svg viewBox="0 0 24 24" aria-hidden="true"><path d="m9 6 9 6-9 6Z"/></svg></button></td>
              </tr>)}
            </tbody></table></div>
          </section>
        </>}

        <div id="history" className="dash-overview dash-history-overview">
          <section className="dash-card dash-attempts">
            <div className="dash-attempts-header"><h2>Previous sessions</h2><span className="dash-pill">{history.length} sessions</span></div>
            {historyError && <p className="dash-load-error" role="alert">Could not load recording history.</p>}
            {history.length > 0 && <div className="dash-table-wrap"><table><thead><tr><th>Session</th><th>Attempts</th><th>Model matches</th><th>Analysis</th></tr></thead><tbody>
              {history.map(({ id, attempts }, index) => <tr key={id}>
                <td><strong>Session {index + 1}</strong></td>
                <td>{attempts.length}</td>
                <td>{attempts.filter(({ analysis }) => analysis.matches_target).length}/{attempts.length}</td>
                <td><a className="dash-text-button" href="#attempts" onClick={() => selectSession(id)} aria-label={`Review session ${index + 1}`}>Review</a></td>
              </tr>)}
            </tbody></table></div>}
          </section>
          <section id="practice" className="dash-card dash-home-practice">
            <h2>Practice goals</h2>
            {maya.goals.map(goal => <div className="dash-goal" key={goal.title}><div><span className="dash-pill">{goal.sound}</span><strong>{goal.title}</strong></div><small>Goal {goal.target}%</small></div>)}
            <h3>Practice words</h3>
            <div className="dash-practice-words">{maya.practice.words.map(word => <span key={word}>{word}</span>)}</div>
          </section>
        </div>
        <section id="notes" className="dash-card dash-clinical-notes"><h2>Clinical notes</h2>{maya.notes.map(note => <article key={note.date}><div><strong>{note.title}</strong><span>{note.author} · {note.date}</span></div><p>{note.text}</p></article>)}</section>
      </main>
    </div>
  </div>
}
