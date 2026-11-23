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
      setError('Tap to play the recording.')
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
      const completed = [...results, body]
      setResults(completed)
      if (index + 1 === samples.length) {
        await saveSession(completed)
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

  async function saveSession(completed) {
    setPhase('saving')
    setError('')
    try {
      const response = await fetch('/api/session', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(completed),
      })
      if (!response.ok) throw Error()
      setScreen('results')
    } catch {
      setError('Could not save this session.')
      setPhase('save-error')
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

  if (window.location.pathname === '/slp') return <SessionDashboard samples={samples} sampleError={sampleError} />

  return <div className="app">
    <header className="topbar">
      <div className="brand"><Mascot small /><span>PronouncedFish</span></div>
      <span className="header-caption">Sunny Reef
        {screen === 'journey' && sample && <span className="header-count"> · Picture {index + 1} of {samples.length}</span>}
      </span>
    </header>

    {screen === 'journey' && <main className="practice-screen">
      <h1>What do you see?</h1>
      <div className="practice-layout">
        <div className="picture-card">{sample ? <WordArt word={sample.target_word} /> : <div className="picture-loading">Loading pictures…</div>}</div>
        <div className="interaction">
          <div className="interaction-inner">
            <button className="play-button"
              onClick={phase === 'save-error' ? () => saveSession(results) : phase === 'analysis-error' ? analyzeCurrent : playCurrent}
              disabled={!sample || ['playing', 'analyzing', 'saving'].includes(phase)}>
              <svg viewBox="0 0 32 32" aria-hidden="true"><path d="M12 7v18l14-9Z" fill="currentColor"/></svg>
              <strong>{phase === 'playing' ? 'Playing…' : phase === 'analyzing' ? 'Checking…' : phase === 'saving' ? 'Saving…' : phase === 'save-error' ? 'Retry save' : phase === 'analysis-error' ? 'Retry analysis' : 'Play recording'}</strong>
            </button>
            {(error || sampleError) && <p className="error" role="alert">{error || sampleError}</p>}
          </div>
        </div>
      </div>
      <span className="bubble bubble-one"/><span className="bubble bubble-two"/><span className="bubble bubble-three"/>
      <ReefDecor />
    </main>}

    {screen === 'results' && <main className="results-screen">
      <h1>Sunny Reef complete</h1>
      <div className="results-intro">
        <Mascot />
        <div className="results-card">
          <h2>All {samples.length} pictures complete</h2>
          <button className="restart-button" onClick={startOver}>Play again</button>
        </div>
      </div>
      <ReefDecor />
    </main>}

    {screen === 'journey' && sample && <audio key={sample.id} ref={audioRef} src={sample.audio_url} preload="auto" onEnded={() => { if (phase === 'playing') analyzeCurrent() }} onError={() => { setPhase('audio-error'); setError('Could not load the recording. Tap to retry.') }} />}
  </div>
}

createRoot(document.getElementById('root')).render(<App />)
