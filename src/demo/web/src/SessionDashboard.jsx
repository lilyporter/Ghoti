import React, { useEffect, useRef, useState } from 'react'
import './dashboard.css'
import Mascot from './Mascot'
import maya from './maya.json'

function ProgressHistory() {
  const points = key => maya.sessions.map((session, index) => `${35 + index * 100},${180 - session[key] * 1.6}`).join(' ')
  return <section className="dash-card dash-history">
    <div className="dash-card-heading"><div><h2>Sound-level trends</h2><p>Word practice · Across recent sessions</p></div><span className="dash-pill">/s/</span></div>
    <svg className="dash-history-chart" viewBox="0 0 580 220" role="img" aria-label="Initial s progress increases from 58 to 78 percent; final s increases from 49 to 63 percent">
      {[0,25,50,75,100].map(value => <g key={value}><text x="0" y={184-value*1.6}>{value}%</text><line x1="35" x2="555" y1={180-value*1.6} y2={180-value*1.6}/></g>)}
      <polyline points={points('initialS')} fill="none" stroke="#3975ea" strokeWidth="3"/>
      <polyline points={points('finalS')} fill="none" stroke="#4f967c" strokeWidth="2" strokeDasharray="6 4"/>
      {maya.sessions.map((session,index) => <g key={session.date}><circle cx={35+index*100} cy={180-session.initialS*1.6} r="3.5" fill="#3975ea"/><circle cx={35+index*100} cy={180-session.finalS*1.6} r="3" fill="#4f967c"/><text x={35+index*100} y="208" textAnchor="middle">{session.date}</text></g>)}
    </svg>
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
  const [results, setResults] = useState(null)
  const [error, setError] = useState('')
  const [playError, setPlayError] = useState('')
  const playingRef = useRef(null)

  useEffect(() => {
    fetch('/api/analysis')
      .then(response => { if (!response.ok) throw Error('Could not load saved analysis'); return response.json() })
      .then(data => setResults(data.results))
      .catch(e => setError(e.message))
    return () => playingRef.current?.pause()
  }, [])

  const byId = new Map((results || []).map(result => [result.sample_id, result]))
  const rows = samples.map(sample => ({ sample, result: byId.get(sample.id) })).filter(row => row.result)
  const exact = rows.filter(row => row.result.analysis.matches_target).length
  const withChanges = rows.filter(row => row.result.analysis.status === 'ok' && !row.result.analysis.matches_target).length
  const unassessable = rows.length - exact - withChanges

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
      <nav aria-label="Dashboard navigation">
        <span className="dash-nav-item"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M3 3h6v6H3Zm12 0h6v6h-6ZM3 15h6v6H3Zm12 0h6v6h-6Z"/></svg>Overview</span>
        <span className="dash-nav-item"><svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="10" cy="7" r="4"/><path d="M3 21v-3a6 6 0 0 1 12 0v3m1-18a4 4 0 0 1 0 8m2 3a5 5 0 0 1 3 5v2"/></svg>Caseload</span>
        <span className="dash-nav-item dash-nav-active" aria-current="page"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M3 21V12m6 9V9m6 12v-6m6 6V7M2 9l7-6 6 6 7-8"/></svg>Session analysis</span>
        <span className="dash-nav-item"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M3 5h4m5 0h9M3 12h10m5 0h3M3 19h4m5 0h9M8 2v6m6 1v6m-6 1v6"/></svg>Practice plans</span>
        <span className="dash-nav-item"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="m5 19 1-5L17 3l4 4-11 11Zm10-14 4 4M5 19l5-1"/></svg>Clinical notes</span>
      </nav>
      <div className="dash-clinician"><span className="dash-avatar small">JL</span><span><strong>Jordan Lee, SLP</strong><small>Clinician</small></span></div>
    </aside>

    <div className="dash-main-area">
      <header className="dash-topbar"><span>Maya Chen</span><span>English (US)</span></header>
      <main className="dash-content">
        <div className="dash-profile"><span className="dash-avatar">MC</span><div><h1>Maya Chen</h1><p>Age 7 · English (US)</p></div></div>
        <div className="dash-tabs"><span className="active">Progress &amp; sessions</span></div>

        <div className="dash-overview dash-history-overview">
          <ProgressHistory />
          <section className="dash-card dash-goals"><div className="dash-card-heading"><h2>Practice goals</h2></div>
            {maya.goals.map(goal => <div className="dash-goal" key={goal.title}><div><span className="dash-pill">{goal.sound}</span><strong>{goal.title}</strong></div><p>{goal.detail}</p><div className="dash-goal-track"><i style={{width:`${goal.progress}%`}}/></div><small>{goal.progress}% · Goal {goal.target}%</small></div>)}
          </section>
        </div>

        {(error || sampleError) && <p className="dash-load-error" role="alert">{error || sampleError}</p>}
        {!error && !sampleError && !rows.length && <p className="dash-loading">Loading saved analysis…</p>}

        {rows.length > 0 && <>
          <div className="dash-overview">
            <section className="dash-card dash-trends">
              <div className="dash-card-heading"><div><h2>Sound comparisons</h2><p>Sunny Reef · Matching sound labels by word</p></div></div>
              <div className="dash-comparison-chart">
                {rows.map(({ sample, result }) => {
                  const alignment = result.analysis.alignment || []
                  const matched = alignment.filter(item => item.kind === 'match').length
                  const changed = alignment.length - matched
                  return <div className="dash-comparison-row" key={sample.id}>
                    <span>{sample.target_word}</span>
                    <div className="dash-comparison-track" aria-label={`${sample.target_word}: ${matched} matched sound labels and ${changed} candidate changes`}>
                      {alignment.length > 0 && <><i className="matched" style={{ flex: matched }} /><i className="changed" style={{ flex: changed }} /></>}
                    </div>
                    <strong>{matched}/{alignment.length || '—'}</strong>
                  </div>
                })}
              </div>
              <div className="dash-legend"><span><i className="blue-line"/> Matching sounds</span><span><i className="coral-line"/> Differences</span></div>
            </section>

            <section className="dash-card dash-latest">
              <div className="dash-card-heading"><h2>Latest session</h2><span className="dash-pill blue">Sunny Reef</span></div>
              <h3 className="dash-session-title">Word practice</h3>
              <p className="dash-session-subtitle">Maya Chen · Individual session</p>
              <div className="dash-metrics"><div><strong>{rows.length}</strong><span>Prompts</span></div><div><strong>{rows.length}</strong><span>Attempts</span></div><div><strong>{exact}</strong><span>Matched</span></div></div>
              <div className="dash-session-score"><strong>{exact}<span> / {rows.length}</span></strong><div>Words matched the target<small>{withChanges} with sound differences</small></div></div>
              {unassessable > 0 && <p>{unassessable} recording{unassessable === 1 ? '' : 's'} could not be assessed.</p>}
            </section>
          </div>

          <section className="dash-card dash-attempts">
            <div className="dash-attempts-header"><div><h2>Session attempts</h2><span>Sunny Reef</span></div><span className="dash-pill blue">All attempts ({rows.length})</span></div>
            <div className="dash-table-wrap"><table><thead><tr><th>Word / attempt</th><th>Target sounds</th><th>Recognized sounds</th><th>Sound comparison</th><th>Playback</th></tr></thead><tbody>
              {rows.map(({ sample, result }) => <tr key={sample.id}>
                <td><strong>{sample.target_word.toUpperCase()}</strong><small>Try 1</small></td>
                <td className="dash-phone">{phoneText(result.analysis.expected_phones)}</td>
                <td className="dash-phone">{phoneText(result.recognition.recognized_phones, true)}</td>
                <td className="dash-differences">{result.analysis.matches_target ? <span className="dash-match-pill">Sounds matched</span> : differences(result.analysis)}</td>
                <td><button className="dash-play" onClick={() => play(sample)} aria-label={`Play ${sample.target_word} recording`}><svg viewBox="0 0 24 24" aria-hidden="true"><path d="m9 6 9 6-9 6Z"/></svg></button></td>
              </tr>)}
            </tbody></table></div>
            <div className="dash-table-footer">Showing all {rows.length} attempts</div>
          </section>
          {playError && <p className="dash-load-error" role="alert">{playError}</p>}
        </>}

        <div className="dash-overview dash-history-overview">
          <section className="dash-card dash-attempts"><div className="dash-attempts-header"><h2>Previous sessions</h2><span className="dash-pill">{maya.sessions.length} sessions</span></div>
            <div className="dash-table-wrap"><table><thead><tr><th>Date</th><th>Exercise</th><th>Duration</th><th>Attempts</th></tr></thead><tbody>{[...maya.sessions].reverse().map(session => <tr key={session.date}><td>{session.date}</td><td><strong>{session.name}</strong></td><td>{session.minutes} min</td><td>{session.attempts}</td></tr>)}</tbody></table></div>
          </section>
          <section className="dash-card dash-home-practice"><h2>At-home practice</h2><h3>{maya.practice.title}</h3><p>{maya.practice.schedule}</p><div className="dash-practice-words">{maya.practice.words.map(word => <span key={word}>{word}</span>)}</div></section>
        </div>
        <section className="dash-card dash-clinical-notes"><h2>Clinical notes</h2>{maya.notes.map(note => <article key={note.date}><div><strong>{note.title}</strong><span>{note.author} · {note.date}</span></div><p>{note.text}</p></article>)}</section>
      </main>
    </div>
  </div>
}
