import React, { useEffect, useRef, useState } from 'react'
import { createRoot } from 'react-dom/client'
import './style.css'
import SessionDashboard from './SessionDashboard'
import Mascot from './Mascot'
import WordArt from './WordArt'

function ReefDecor() {
  return <svg className="reef-decor" viewBox="0 0 1200 170" preserveAspectRatio="none" aria-hidden="true">
    <path d="M0 89c188 38 334 63 515 22 234-53 377-116 685-37v96H0Z" fill="#d0eff1" />
    <path d="M8 170V68m0 59C37 118 40 92 39 53M8 150c-25-11-26-32-26-63" fill="none" stroke="#e48657" strokeWidth="14" strokeLinecap="round" />
    <path d="M1191 170V95m0 51c-29-8-34-34-32-48m32 62c25-8 28-30 29-47" fill="none" stroke="#4d9a7d" strokeWidth="13" strokeLinecap="round" />
  </svg>
}

function ResultCard({ sample, result }) {
  const analysis = result.analysis
  const recognized = result.recognition
  const changes = analysis.alignment?.filter(row => row.kind !== 'match') || []
  return <article className="journey-result-card">
    <div className="journey-result-art"><WordArt word={sample.target_word} /></div>
    <div className="journey-result-copy">
      <div className="journey-result-heading"><h3>{sample.target_word}</h3><span>{sample.label}</span></div>
      <p><span>Target</span> <strong>/{analysis.expected_phones?.join(' ') || '—'}/</strong></p>
      <p><span>Model heard</span> <strong>[{recognized.recognized_phones?.join(' ') || '—'}]</strong></p>
      <div className={analysis.status !== 'ok' || changes.length ? 'result-status review' : 'result-status'}>
        {analysis.status !== 'ok' ? 'Could not assess this clip' : changes.length ? `${changes.length} possible sound ${changes.length === 1 ? 'difference' : 'differences'}` : 'No sound differences found'}
      </div>
    </div>
  </article>
}

function App() {
  const [samples, setSamples] = useState([])
  const [sampleError, setSampleError] = useState('')
  const [screen, setScreen] = useState('journey')
  const [index, setIndex] = useState(0)
  const [phase, setPhase] = useState('ready')
  const [results, setResults] = useState([])
  const [error, setError] = useState('')
  const [autoNext, setAutoNext] = useState(false)
  const audioRef = useRef(null)
  const inFlightRef = useRef(false)

  useEffect(() => {
    fetch('/api/samples')
      .then(response => { if (!response.ok) throw Error('Could not load recordings'); return response.json() })
      .then(setSamples)
      .catch(e => setSampleError(e.message))
  }, [])

  const sample = samples[index]

  async function playCurrent() {
    if (!audioRef.current || phase === 'analyzing' || phase === 'playing') return
    setError('')
    try {
      audioRef.current.currentTime = 0
      await audioRef.current.play()
      setPhase('playing')
    } catch {
      setPhase('ready')
      setError('Tap to play this recording. Your iPad may need another tap to continue.')
    }
  }

  useEffect(() => {
    if (screen === 'journey' && autoNext && phase === 'ready' && sample) {
      setAutoNext(false)
      playCurrent()
    }
  }, [autoNext, index, phase, screen, sample])

  async function analyzeCurrent() {
    if (!sample || inFlightRef.current) return
    inFlightRef.current = true
    setPhase('analyzing')
    setError('')
    try {
      const response = await fetch(`/api/samples/${encodeURIComponent(sample.id)}/analyze`, { method: 'POST' })
      const body = await response.json()
      if (!response.ok) throw Error(body.detail || 'Analysis failed')
      setResults(previous => [...previous, body])
      if (index + 1 === samples.length) {
        setScreen('results')
        setPhase('ready')
      } else {
        setIndex(index + 1)
        setPhase('ready')
        setAutoNext(true)
      }
    } catch (e) {
      setError(e.message)
      setPhase('analysis-error')
    } finally {
      inFlightRef.current = false
    }
  }

  function startOver() {
    audioRef.current?.pause()
    setIndex(0)
    setResults([])
    setPhase('ready')
    setScreen('journey')
    setAutoNext(false)
    setError('')
  }

  if (window.location.pathname === '/slp') return <SessionDashboard samples={samples} sampleError={sampleError} onDemo={() => { window.location.href = '/' }} />

  return <div className="app">
    <header className="topbar">
      <div className="brand"><Mascot small /><span>PronouncedFish</span></div>
      <span className="header-caption">Sunny Reef</span>
      <span className="header-count">{screen === 'results' ? 'Journey complete' : `Picture ${index + 1} of ${samples.length || 10}`}</span>
    </header>

    {screen === 'journey' && <main className="practice-screen">
      <h1>What do you see?</h1>
      <div className="practice-layout">
        <div className="picture-card">{sample ? <WordArt word={sample.target_word} /> : <div className="picture-loading">Loading pictures…</div>}</div>
        <div className="interaction">
          <div className="interaction-inner">
            <span className="picture-step">Picture {index + 1} of {samples.length || 10}</span>
            <h2>{sample ? `Listening.` : 'Getting ready…'}</h2>
            <button className="play-button" onClick={phase === 'analysis-error' ? analyzeCurrent : playCurrent} disabled={!sample || phase === 'playing' || phase === 'analyzing'}>
              <svg viewBox="0 0 32 32" aria-hidden="true"><path d="M12 7v18l14-9Z" fill="currentColor"/></svg>
              <strong>{phase === 'playing' ? 'Playing…' : phase === 'analyzing' ? 'Checking…' : phase === 'analysis-error' ? 'Try analysis again' : index === 0 && !results.length ? 'Tap to play' : 'Tap to continue'}</strong>
            </button>
            <div className="reassurance"><Mascot /><span>{phase === 'analyzing' ? 'Nice listening! I’m checking this one.' : 'Take your time!'}</span></div>
            {(error || sampleError) && <p className="error" role="alert">{error || sampleError}</p>}
          </div>
        </div>
      </div>
      <span className="bubble bubble-one"/><span className="bubble bubble-two"/><span className="bubble bubble-three"/>
      <ReefDecor />
    </main>}

    {screen === 'results' && <main className="results-screen">
      <div className="results-intro"><Mascot /><div><span className="picture-step">All ten pictures complete</span><h1>Let’s look at the sounds!</h1></div></div>
      <div className="journey-results">{samples.map(sample => {
        const result = results.find(item => item.sample_id === sample.id)
        return result && <ResultCard key={sample.id} sample={sample} result={result} />
      })}</div>
      <button className="restart-button" onClick={startOver}>Listen again →</button>
    </main>}

    {screen === 'journey' && sample && <audio key={sample.id} ref={audioRef} src={sample.audio_url} preload="auto" onEnded={() => { if (phase === 'playing') analyzeCurrent() }} onError={() => { setPhase('audio-error'); setError('This recording could not be loaded. Tap to try again.') }} />}
  </div>
}

createRoot(document.getElementById('root')).render(<App />)
