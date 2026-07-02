import React, { useEffect, useState } from 'react'

const API_BASE = import.meta.env.VITE_API_BASE || 'http://localhost:8000'

async function readApiResponse(res) {
  const text = await res.text()
  try {
    return text ? JSON.parse(text) : {}
  } catch {
    throw new Error(`Expected JSON from API, received: ${text.slice(0, 80)}`)
  }
}

function wait(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms))
}

function AnswerText({ text, sources, onCitationClick }) {
  const sourceIds = new Set((sources || []).map((source) => source.citation))
  const parts = String(text || '').split(/(\[\d+\])/g)

  return (
    <pre>
      {parts.map((part, index) => {
        const match = part.match(/^\[(\d+)\]$/)
        if (!match) {
          return <React.Fragment key={`${part}-${index}`}>{part}</React.Fragment>
        }

        const citation = Number(match[1])
        if (!sourceIds.has(citation)) {
          return <span key={`${part}-${index}`} className="bad-citation">{part}</span>
        }

        return (
          <button
            key={`${part}-${index}`}
            className="citation"
            type="button"
            onClick={() => onCitationClick(citation)}
            title={`Show source ${part}`}
          >
            {part}
          </button>
        )
      })}
    </pre>
  )
}

function parseSseEvent(raw) {
  const event = { event: 'message', data: '' }
  raw.split('\n').forEach((line) => {
    if (line.startsWith('event:')) {
      event.event = line.slice(6).trim()
    } else if (line.startsWith('data:')) {
      event.data += line.slice(5).trim()
    }
  })
  return event
}

export default function App() {
  const [appConfig, setAppConfig] = useState({
    enable_streaming: true,
    enable_background_ingestion: true
  })
  const [url, setUrl] = useState('')
  const [ingesting, setIngesting] = useState(false)
  const [ingestMessage, setIngestMessage] = useState(null)
  const [summary, setSummary] = useState(null)
  const [error, setError] = useState(null)

  const [question, setQuestion] = useState('')
  const [conversationId] = useState(() => crypto.randomUUID())
  const [asking, setAsking] = useState(false)
  const [answer, setAnswer] = useState(null)
  const [openCitation, setOpenCitation] = useState(null)

  useEffect(() => {
    async function loadConfig() {
      try {
        const res = await fetch(`${API_BASE}/config`)
        const data = await readApiResponse(res)
        if (res.ok) {
          setAppConfig((prev) => ({ ...prev, ...data }))
        }
      } catch {
        // Keep safe defaults if config cannot be loaded.
      }
    }

    loadConfig()
  }, [])

  async function handleIngest() {
    setError(null)
    setSummary(null)
    setIngestMessage(null)
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

      const data = await readApiResponse(res)

      if (!res.ok) {
        setError(data.detail || JSON.stringify(data))
        return
      }

      setIngestMessage(data.message || 'Ingestion queued')

      if (!appConfig.enable_background_ingestion || !data.job_id) {
        if (data.status === 'exists') {
          setSummary({ title: data.title, summary: 'Article already ingested' })
        } else {
          setSummary({ title: data.title, summary: data.summary })
        }
        return
      }

      while (data.job_id) {
        await wait(1000)
        const statusRes = await fetch(`${API_BASE}/ingest/status/${data.job_id}`)
        const statusData = await readApiResponse(statusRes)

        if (!statusRes.ok) {
          setError(statusData.detail || JSON.stringify(statusData))
          return
        }

        setIngestMessage(statusData.message || statusData.status)

        if (statusData.status === 'completed') {
          const result = statusData.result || {}
          if (result.status === 'exists') {
            setSummary({ title: result.title, summary: 'Article already ingested' })
          } else {
            setSummary({ title: result.title, summary: result.summary })
          }
          return
        }

        if (statusData.status === 'failed') {
          setError(statusData.error || 'Ingestion failed')
          return
        }
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
    setOpenCitation(null)
    if (!question) {
      setError('Please enter a question')
      return
    }
    setAsking(true)
    try {
      const q = encodeURIComponent(question)
      const conversationParam = `conversation_id=${encodeURIComponent(conversationId)}`
      if (!appConfig.enable_streaming) {
        const res = await fetch(`${API_BASE}/ask?question=${q}&${conversationParam}`)
        const data = await readApiResponse(res)

        if (!res.ok) {
          setError(data.detail || JSON.stringify(data))
          return
        }

        setAnswer({
          answer: data.answer,
          context: data.context || [],
          sources: data.sources || [],
          invalidCitations: data.invalid_citations || [],
          missingCitations: Boolean(data.missing_citations),
          citationRetryUsed: Boolean(data.citation_retry_used)
        })
        return
      }

      const res = await fetch(`${API_BASE}/ask/stream?question=${q}&${conversationParam}`)
      if (!res.ok) {
        const data = await readApiResponse(res)
        setError(data.detail || JSON.stringify(data))
        return
      }

      setAnswer({
        answer: '',
        context: [],
        sources: [],
        invalidCitations: [],
        missingCitations: false,
        citationRetryUsed: false
      })

      const reader = res.body.getReader()
      const decoder = new TextDecoder()
      let buffer = ''

      while (true) {
        const { value, done } = await reader.read()
        if (done) {
          break
        }

        buffer += decoder.decode(value, { stream: true })
        const events = buffer.split('\n\n')
        buffer = events.pop()

        events.forEach((rawEvent) => {
          const parsed = parseSseEvent(rawEvent)
          if (!parsed.data) {
            return
          }
          const data = JSON.parse(parsed.data)

          if (parsed.event === 'token') {
            setAnswer((prev) => ({
              ...(prev || {}),
              answer: `${prev?.answer || ''}${data.text || ''}`
            }))
          } else if (parsed.event === 'final') {
            setAnswer({
              answer: data.answer,
              context: data.context || [],
              sources: data.sources || [],
              invalidCitations: data.invalid_citations || [],
              missingCitations: Boolean(data.missing_citations),
              citationRetryUsed: Boolean(data.citation_retry_used || data.citation_repaired)
            })
          } else if (parsed.event === 'error') {
            setError(data.detail || 'Streaming failed')
          }
        })
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
        <button onClick={handleIngest} disabled={ingesting || asking}>
          {ingesting ? 'Ingesting...' : 'Ingest Article'}
        </button>

        {ingestMessage && (
          <div className="notice">{ingestMessage}</div>
        )}

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
        <button onClick={handleAsk} disabled={asking || ingesting}>
          {asking ? 'Thinking...' : ingesting ? 'Wait for ingest' : 'Ask Question'}
        </button>

        {answer && (
          <div className="result">
            <h3>Answer</h3>
            <AnswerText
              text={answer.answer}
              sources={answer.sources}
              onCitationClick={setOpenCitation}
            />

            {answer.citationRetryUsed && !answer.missingCitations && answer.invalidCitations.length === 0 && (
              <div className="notice">
                Citations were repaired on a second pass.
              </div>
            )}

            {answer.invalidCitations.length > 0 && (
              <div className="warning">
                Unsupported citation(s): {answer.invalidCitations.map((c) => `[${c}]`).join(', ')}
              </div>
            )}

            {answer.missingCitations && (
              <div className="warning">
                Answer did not include inline citations.
              </div>
            )}

            <h4>Sources</h4>
            <ul className="sources">
              {answer.sources && answer.sources.map((source) => (
                <li key={source.citation}>
                  <details open={openCitation === source.citation}>
                    <summary>
                      <strong>[{source.citation}] {source.title || 'Unknown'}</strong>
                      {' '}— Chunk {source.chunk_number}
                    </summary>
                    <p>{source.text}</p>
                    {source.url && (
                      <a href={source.url} target="_blank" rel="noreferrer">Open article</a>
                    )}
                  </details>
                </li>
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
