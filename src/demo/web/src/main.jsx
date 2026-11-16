import React, { useEffect, useRef, useState } from 'react'
import { createRoot } from 'react-dom/client'
import './style.css'
import SessionDashboard from './SessionDashboard'

const PICTURES = { sun: '☀️', gift: '🎁', seal: '🦭', sheep: '🐑', shell: '🐚', ship: '🚢', shoe: '👟', shop: '🏪', soup: '🍲', chute: '🛝' }

function Fish({ small = false }) {
  return <span className={small ? 'fish fish-small' : 'fish'} aria-hidden="true">🐟</span>
}

function Header({ screen, onBack }) {
  return <header className="topbar">
    <button className="brand" onClick={onBack} aria-label="Return to audio choices"><Fish small /> <span>PronouncedFish</span></button>
    <div className="progress"><strong>Audio demo · {screen === 'choose' ? 'Choose a clip' : screen === 'practice' ? 'Listen' : 'Review'}</strong><div className="progress-dots"><i className="done"/><i className={screen !== 'choose' ? 'done' : ''}/><i className={screen === 'results' ? 'done' : ''}/><i/><i/><i/><i/><i/><i/><i/></div></div>
    <span className="mode-label">Child speech demo</span>
  </header>
}

function Picture({ word }) {
  if (word !== 'sun') return <div className="picture-card" role="img" aria-label={`Picture of ${word}`}><span className="picture-emoji" aria-hidden="true">{PICTURES[word]}</span></div>
  return <div className="picture-card" role="img" aria-label="Illustration of a sun and clouds">
    <svg viewBox="0 0 400 400" aria-hidden="true"><circle cx="200" cy="200" r="135" fill="#fff1bf"/>
      {[0,45,90,135,180,225,270,315].map(a => <rect key={a} x="194" y="68" width="12" height="33" rx="6" fill="#ecb634" transform={`rotate(${a} 200 200)`}/>)}
      <circle cx="200" cy="200" r="80" fill="#f8d773"/><ellipse cx="170" cy="143" rx="24" ry="11" transform="rotate(-30 170 143)" fill="#ffe9a2"/>
      <path d="M74 284c0-17 14-30 31-30 7-21 38-24 50-2 19-2 34 12 34 31 0 13-11 22-24 22H98c-14 0-24-9-24-21Zm221-78c0-17 13-29 30-29 8-22 38-24 51-2 17-2 30 11 30 29 0 14-11 24-25 24h-61c-15 0-25-9-25-22Z" fill="white"/>
    </svg>
  </div>
}

function App() {
  const [samples, setSamples] = useState([])
  const [screen, setScreen] = useState('choose')
  const [selected, setSelected] = useState(null)
  const [state, setState] = useState('ready')
  const [result, setResult] = useState(null)
  const [error, setError] = useState('')
  const audioRef = useRef(null)

  useEffect(() => { fetch('/api/samples').then(r => { if (!r.ok) throw Error('Could not load clips'); return r.json() }).then(setSamples).catch(e => setError(e.message)) }, [])
  function reset() { audioRef.current?.pause(); setScreen('choose'); setSelected(null); setResult(null); setState('ready'); setError('') }
  function select(item) { setSelected(item); setResult(null); setState('ready'); setError(''); setScreen('practice') }
  async function play() {
    if (!audioRef.current || state === 'analyzing') return
    setError('')
    try { audioRef.current.currentTime = 0; await audioRef.current.play(); setState('playing') }
    catch { setError('Your iPad could not play this clip. Please tap again.'); setState('ready') }
  }
  async function finished() {
    if (screen !== 'practice') { setState('ready'); return }
    if (!selected) return
    setState('analyzing')
    try {
      const response = await fetch(`/api/samples/${encodeURIComponent(selected.id)}/analyze`, { method: 'POST' })
      const body = await response.json()
      if (!response.ok) throw Error(body.detail || 'Analysis failed')
      setResult(body); setScreen('results'); setState('ready')
    } catch (e) { setError(e.message); setState('ready') }
  }
  const comparison = result?.analysis
  const recognition = result?.recognition
  const changes = comparison?.alignment?.filter(row => row.kind !== 'match') || []
  if (window.location.pathname === '/slp') return <SessionDashboard samples={samples} onDemo={() => { window.location.href = '/' }} />
  return <div className="app"><Header screen={screen} onBack={reset}/>
    <main>
      {screen === 'choose' && <section className="choose-screen"><div className="page-title"><span className="eyebrow">Step 1 of 3</span><h1>Choose a voice and word</h1><p>Listen to ten different words spoken by ten children.</p></div>
        <div className="sample-grid">{samples.map(item => <button className="sample-card" key={item.id} onClick={() => select(item)}><span className="sample-art">{PICTURES[item.target_word]}</span><span className="sample-copy"><strong>{item.label}</strong><span>Word: {item.target_word}</span></span><span className="card-arrow">→</span></button>)}</div>
        <p className="disclaimer">Real child recordings from the Paidologos corpus. Model results are for demonstration and need review.</p>
      </section>}
      {screen === 'practice' && selected && <section className="practice-screen"><h1>What do you see?</h1><div className="practice-layout"><Picture word={selected.target_word}/><div className="interaction"><h2>Listen to “{selected.target_word}”.</h2><p>Tap to play the child’s recording. Analysis starts when it finishes.</p><button className="play-button" onClick={play} disabled={state !== 'ready'}><span className="play-icon">{state === 'analyzing' ? '◌' : '▶'}</span><strong>{state === 'playing' ? 'Playing…' : state === 'analyzing' ? 'Analyzing…' : 'Tap to play'}</strong></button><div className="reassurance"><Fish/><span>{state === 'analyzing' ? 'Listening is done. The laptop is checking the sounds.' : 'Take your time. I’m right here!'}</span></div><button className="secondary-button" onClick={reset}>Choose another audio</button>{error && <p className="error" role="alert">{error}</p>}</div></div><div className="sea"/></section>}
      {screen === 'results' && selected && <section className="result-screen"><div className="page-title"><span className="eyebrow">Step 3 of 3</span><h1>Let’s look at the sounds</h1><p>Here is what the laptop heard in the selected child recording.</p></div><div className="result-layout"><div className="result-illustration"><Picture word={selected.target_word}/><h2>{selected.target_word}</h2><p>Prompt word: {selected.target_word}</p><button className="secondary-button" onClick={play}>▶ Play again</button></div><div className="result-card"><span className="eyebrow">Simple analysis</span><h2>{recognition?.status === 'ok' ? comparison?.matches_target ? 'Sounds matched the target' : 'Some sounds may be different' : 'Could not assess this clip'}</h2><div className="sound-row"><span>Expected sounds</span><strong className="ipa">/{comparison?.expected_phones?.join(' ') || '—'}/</strong></div><div className="sound-row"><span>Recognized sounds</span><strong className="ipa">[{recognition?.recognized_phones?.join(' ') || '—'}]</strong></div><div className="difference-list"><h3>What changed?</h3>{changes.length ? changes.map((row, i) => <p key={i}>{row.kind === 'substitution' ? `Possible substitution: /${row.expected_phone}/ → [${row.recognized_phone}]` : row.kind === 'omission' ? `Possible missing sound: /${row.expected_phone}/` : `Possible extra sound: [${row.recognized_phone}]`}</p>) : <p>{recognition?.status === 'ok' ? 'No sound differences were found in this comparison.' : recognition?.review_reason}</p>}</div><p className="review-note">This is an uncalibrated model result for a real child recording. Candidate differences need clinician review; this is not a diagnosis.</p><button className="primary-small" onClick={reset}>Try another audio →</button></div></div></section>}
      {screen === 'choose' && error && <p className="error" role="alert">{error}</p>}
    </main>
    {selected && <audio key={selected.id} ref={audioRef} src={selected.audio_url} preload="auto" onEnded={finished} onError={() => setError('The selected audio could not be loaded.')} />}
  </div>
}

createRoot(document.getElementById('root')).render(<App />)
