import React, { useEffect, useRef, useState } from 'react'
import './dashboard.css'
import Mascot from './Mascot'

function phoneText(phones, brackets = false) {
  if (!phones?.length) return '—'
  return brackets ? `[${phones.join(' ')}]` : `/${phones.join(' ')}/`
}

function differences(analysis) {
  if (analysis?.status !== 'ok') return 'Could not assess'
  const changes = analysis.alignment.filter(row => row.kind !== 'match')
  if (!changes.length) return 'No candidate differences'
  return changes.map(row => {
    if (row.kind === 'substitution') return `${phoneText([row.expected_phone])} → [${row.recognized_phone}]`
    if (row.kind === 'omission') return `Missing ${phoneText([row.expected_phone])}`
    return `Extra [${row.recognized_phone}]`
  }).join(' · ')
}

export default function SessionDashboard({ samples, sampleError, onDemo }) {
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
        <button onClick={onDemo}><span aria-hidden="true">▦</span> Audio demo</button>
        <span className="dash-nav-active"><span aria-hidden="true">▥</span> Sample analysis</span>
      </nav>
      <div className="dash-clinician"><span className="dash-avatar small">SLP</span><span><strong>Clinician view</strong></span></div>
    </aside>

    <div className="dash-main-area">
      <header className="dash-topbar"><span>Sample analysis</span></header>
      <main className="dash-content">
        <div className="dash-profile"><span className="dash-avatar">10</span><div><h1>Ten child voices</h1><p>Ten different speakers · Ten words · Paidologos recordings</p></div><button onClick={onDemo}>Open audio demo</button></div>
        <div className="dash-tabs"><span className="active">Recordings &amp; model results</span></div>

        {(error || sampleError) && <p className="dash-load-error" role="alert">{error || sampleError}</p>}
        {!error && !sampleError && !rows.length && <p className="dash-loading">Loading saved analysis…</p>}

        {rows.length > 0 && <>
          <div className="dash-overview">
            <section className="dash-card dash-trends">
              <div className="dash-card-heading"><div><h2>Sound label comparison</h2><p>Target versus model output for each recording</p></div></div>
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
              <div className="dash-legend"><span><i className="blue-line"/> Matching labels</span><span><i className="coral-line"/> Candidate changes</span></div>
            </section>

            <section className="dash-card dash-latest">
              <div className="dash-card-heading"><h2>Analysis summary</h2></div>
              <div className="dash-metrics"><div><strong>{rows.length}</strong><span>Recordings</span></div><div><strong>{exact}</strong><span>Exact label matches</span></div><div><strong>{withChanges}</strong><span>With candidate changes</span></div></div>
              {unassessable > 0 && <p>{unassessable} recording{unassessable === 1 ? '' : 's'} could not be assessed.</p>}
            </section>
          </div>

          <section className="dash-card dash-attempts">
            <div className="dash-attempts-header"><div><h2>Recording breakdown</h2><span>One analysis per child voice</span></div><span className="dash-pill blue">All {rows.length} recordings</span></div>
            <div className="dash-table-wrap"><table><thead><tr><th>Recording</th><th>Target sounds</th><th>Model heard</th><th>Candidate differences</th><th>Playback</th></tr></thead><tbody>
              {rows.map(({ sample, result }) => <tr key={sample.id}>
                <td><strong>{sample.target_word.toUpperCase()}</strong><small>{sample.label}</small></td>
                <td className="dash-phone">{phoneText(result.analysis.expected_phones)}</td>
                <td className="dash-phone">{phoneText(result.recognition.recognized_phones, true)}</td>
                <td className="dash-differences">{differences(result.analysis)}</td>
                <td><button className="dash-play" onClick={() => play(sample)} aria-label={`Play ${sample.target_word} recording`}>▷</button></td>
              </tr>)}
            </tbody></table></div>
          </section>
          {playError && <p className="dash-load-error" role="alert">{playError}</p>}
        </>}
      </main>
    </div>
  </div>
}
