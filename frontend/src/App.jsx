import React, { useState } from 'react'

const API_BASE = import.meta.env.VITE_API_BASE || '/api'

export default function App() {
  const [url, setUrl] = useState('')
  const [ingesting, setIngesting] = useState(false)
  const [summary, setSummary] = useState(null)
  const [error, setError] = useState(null)

  const [question, setQuestion] = useState('')
  const [asking, setAsking] = useState(false)
  const [answer, setAnswer] = useState(null)

  async function handleIngest() {
    setError(null)
    setSummary(null)
    if (!url) {
      setError('Please enter a Wikipedia URL')
      return
    }
    setIngesting(true)
    try {
      const res = await fetch(`${API_BASE}/ingest`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({ url })
      })

      const data = await res.json()

      if (!res.ok) {
        setError(data.detail || JSON.stringify(data))
      } else if (data.status === 'exists') {
        setSummary({ title: data.title, summary: 'Article already ingested' })
      } else {
        setSummary({ title: data.title, summary: data.summary })
      }
    } catch (e) {
      setError(String(e))
    } finally {
      setIngesting(false)
    }
  }

  async function handleAsk() {
    setError(null)
    setAnswer(null)
    if (!question) {
      setError('Please enter a question')
      return
    }
    setAsking(true)
    try {
      const q = encodeURIComponent(question)
      const res = await fetch(`${API_BASE}/ask?question=${q}`)
      const data = await res.json()
      if (!res.ok) {
        setError(data.detail || JSON.stringify(data))
      } else {
        setAnswer({ answer: data.answer, context: data.context })
      }
    } catch (e) {
      setError(String(e))
    } finally {
      setAsking(false)
    }
  }

  return (
    <div className="container">
      <h1>Wikipedia RAG Demo</h1>

      <section className="card">
        <h2>Ingest Article</h2>
        <input
          placeholder="https://en.wikipedia.org/wiki/Example"
          value={url}
          onChange={(e) => setUrl(e.target.value)}
        />
        <button onClick={handleIngest} disabled={ingesting}>
          {ingesting ? 'Ingesting...' : 'Ingest Article'}
        </button>

        {summary && (
          <div className="result">
            <h3>{summary.title}</h3>
            <pre>{summary.summary}</pre>
          </div>
        )}
      </section>

      <section className="card">
        <h2>Ask a Question</h2>
        <input
          placeholder="Ask a question about ingested articles"
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
        />
        <button onClick={handleAsk} disabled={asking}>
          {asking ? 'Thinking...' : 'Ask Question'}
        </button>

        {answer && (
          <div className="result">
            <h3>Answer</h3>
            <pre>{answer.answer}</pre>

            <h4>Context (returned chunks)</h4>
            <ul>
              {answer.context && answer.context.map((c, i) => (
                <li key={i}><strong>{c.title || 'Unknown'}</strong> — Chunk {c.chunk_number}: {c.text?.slice(0, 200)}...</li>
              ))}
            </ul>
          </div>
        )}
      </section>

      {error && (
        <div className="error">{error}</div>
      )}

    </div>
  )
}
