import { useQuery } from '@tanstack/react-query'
import { useEffect, useRef, useState, type FormEvent, type KeyboardEvent } from 'react'
import Markdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { parseSse, toolLabel, type ChatMessage } from '../lib/aiChat'
import styles from './AiPage.module.css'

interface AiStatus {
  configured: boolean
  model: string | null
  tools: boolean
}

const EXAMPLES = ['今天大盤重點是什麼？', '台積電最近外資動向與本益比位置', '我的自選股這週有哪些除權息或法說會？', '幫我看投資組合的損益與集中度']

export function AiPage() {
  const st = useQuery({ queryKey: ['ai-status'], queryFn: () => fetch('/api/ai/status').then((r) => r.json() as Promise<AiStatus>) })
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [text, setText] = useState('')
  const [busy, setBusy] = useState(false)
  const [progress, setProgress] = useState<string[]>([])
  const abort = useRef<AbortController | null>(null)
  const bottom = useRef<HTMLDivElement>(null)

  useEffect(() => {
    bottom.current?.scrollIntoView({ block: 'end' })
  }, [messages, progress])
  useEffect(() => () => abort.current?.abort(), [])

  async function send(question: string) {
    const q = question.trim()
    if (!q || busy) return
    const history: ChatMessage[] = [...messages.filter((m) => !m.error), { role: 'user', content: q }]
    setMessages([...messages, { role: 'user', content: q }])
    setText('')
    setBusy(true)
    setProgress([])
    const steps: string[] = []
    const ctrl = new AbortController()
    abort.current = ctrl
    let finished = false
    const finish = (m: ChatMessage) => {
      finished = true
      setMessages((prev) => [...prev, m])
    }
    try {
      const r = await fetch('/api/ai/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ messages: history.map(({ role, content }) => ({ role, content })) }),
        signal: ctrl.signal,
      })
      if (!r.ok || !r.body) {
        let detail = `API ${r.status}`
        try {
          detail = (await r.json()).detail ?? detail
        } catch {
          // 非 JSON
        }
        throw new Error(detail)
      }
      const reader = r.body.pipeThrough(new TextDecoderStream()).getReader()
      let buf = ''
      for (;;) {
        const { value, done } = await reader.read()
        if (done) break
        const parsed = parseSse(buf + value)
        buf = parsed.rest
        for (const ev of parsed.events) {
          if (ev.type === 'tool') {
            steps.push(toolLabel(ev.name, ev.args))
            setProgress([...steps])
          } else if (ev.type === 'status') {
            setProgress([...steps, ev.text])
          } else if (ev.type === 'answer') {
            finish({ role: 'assistant', content: ev.text, steps: [...steps] })
          } else if (ev.type === 'error') {
            finish({ role: 'assistant', content: ev.text, steps: [...steps], error: true })
          }
        }
      }
      if (!finished) finish({ role: 'assistant', content: '連線中斷，沒有收到回覆。', steps, error: true })
    } catch (e) {
      if (!finished) finish({ role: 'assistant', content: ctrl.signal.aborted ? '已停止。' : (e as Error).message, steps, error: true })
    } finally {
      setBusy(false)
      setProgress([])
      abort.current = null
    }
  }

  const submit = (e: FormEvent) => {
    e.preventDefault()
    void send(text)
  }
  const onKey = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey && !e.nativeEvent.isComposing) {
      e.preventDefault()
      void send(text)
    }
  }

  if (st.data && !st.data.configured) {
    return (
      <div className={styles.page}>
        <h1 className={styles.h1}>AI 助理</h1>
        <section className={styles.card}>
          <p>AI 助理還沒設定金鑰。請在自己電腦的終端機執行下面這行，依畫面提示貼上 Agnes 金鑰並選擇模型：</p>
          <pre className={styles.cmd}>ssh -t home "bash ~/apps/twstock/deploy/set-agnes.sh"</pre>
          <p className={styles.muted}>金鑰只存在 home server，不會出現在網頁或程式碼裡。</p>
        </section>
      </div>
    )
  }

  return (
    <div className={styles.page}>
      <header className={styles.head}>
        <div>
          <h1 className={styles.h1}>AI 助理</h1>
          <p className={styles.muted}>
            {st.data?.model ? `模型：${st.data.model}・` : ''}會查本站資料與證交所、櫃買、公開資訊觀測站等官方資料後回答。回答僅供參考，不構成投資建議。
          </p>
        </div>
        {messages.length > 0 && (
          <button type="button" className={styles.secondary} onClick={() => setMessages([])} disabled={busy}>
            新對話
          </button>
        )}
      </header>

      <section className={styles.chat} aria-label="對話" aria-live="polite">
        {messages.length === 0 && (
          <div className={styles.examples}>
            {EXAMPLES.map((q) => (
              <button key={q} type="button" className={styles.chip} onClick={() => void send(q)} disabled={busy || !st.data}>
                {q}
              </button>
            ))}
          </div>
        )}
        {messages.map((m, i) => (
          <article key={i} className={m.role === 'user' ? styles.user : `${styles.bot} ${m.error ? styles.err : ''}`}>
            {m.steps && m.steps.length > 0 && (
              <details className={styles.steps}>
                <summary>查了 {m.steps.length} 項資料</summary>
                <ul>
                  {m.steps.map((s, j) => (
                    <li key={j}>{s}</li>
                  ))}
                </ul>
              </details>
            )}
            {m.role === 'assistant' && !m.error ? (
              <div className={styles.md}>
                <Markdown remarkPlugins={[remarkGfm]}>{m.content}</Markdown>
              </div>
            ) : (
              <p className={styles.plain}>{m.content}</p>
            )}
          </article>
        ))}
        {busy && (
          <div className={styles.progress} role="status">
            {(progress.length ? progress : ['送出中…']).map((p, i) => (
              <div key={i}>{p}</div>
            ))}
          </div>
        )}
        <div ref={bottom} />
      </section>

      <form className={styles.form} onSubmit={submit}>
        <label htmlFor="ai-q" className="sr-only">
          問題
        </label>
        <textarea id="ai-q" className={styles.input} rows={2} value={text} onChange={(e) => setText(e.target.value)} onKeyDown={onKey}
          placeholder="輸入問題，Enter 送出、Shift+Enter 換行" maxLength={2000} />
        {busy ? (
          <button type="button" className={styles.secondary} onClick={() => abort.current?.abort()}>
            停止
          </button>
        ) : (
          <button type="submit" className={styles.primary} disabled={!text.trim()}>
            送出
          </button>
        )}
      </form>
    </div>
  )
}
