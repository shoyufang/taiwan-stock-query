import { useQuery } from '@tanstack/react-query'
import { useMemo, useState } from 'react'
import { Link } from 'react-router'
import { watchlistApi } from '../lib/api'
import { dayLabel, groupEvents, KIND_LABEL, type CalendarData, type EventKind } from '../lib/calendar'
import styles from './CalendarPage.module.css'

async function getCalendar(): Promise<CalendarData> {
  const r = await fetch('/api/calendar')
  if (r.status === 503) throw new Error('行事曆準備中')
  if (!r.ok) throw new Error(`API ${r.status}`)
  return r.json()
}

const KINDS: EventKind[] = ['dividend', 'conference', 'deadline']
const md = (iso: string) => iso.slice(5).replace('-', '/')

export function CalendarPage() {
  const q = useQuery({ queryKey: ['calendar'], queryFn: getCalendar, refetchInterval: 30 * 60_000, retry: 3, retryDelay: 5000 })
  const wl = useQuery({ queryKey: ['watchlist'], queryFn: watchlistApi.get })
  const [kinds, setKinds] = useState<Set<EventKind>>(new Set(KINDS))
  const [watchOnly, setWatchOnly] = useState(false)
  const [showPast, setShowPast] = useState(false)
  const watch = useMemo(() => new Set(wl.data?.codes ?? []), [wl.data])
  const groups = useMemo(
    () => (q.data ? groupEvents(q.data.events, { kinds, watchOnly, showPast }, watch, q.data.today) : []),
    [q.data, kinds, watchOnly, showPast, watch],
  )
  const toggle = (k: EventKind) =>
    setKinds((s) => {
      const n = new Set(s)
      if (n.has(k)) n.delete(k)
      else n.add(k)
      return n
    })

  return (
    <div className={styles.page}>
      <header>
        <h1 className={styles.h1}>投資行事曆</h1>
        <p className={styles.muted}>{q.data ? `${md(q.data.start)}～${md(q.data.end)}・${q.data.note}` : '資料載入中…'}</p>
      </header>

      <div className={styles.controls}>
        <div className={styles.chips} role="group" aria-label="事件類型">
          {KINDS.map((k) => (
            <button key={k} type="button" className={styles.chip} aria-pressed={kinds.has(k)} onClick={() => toggle(k)}>
              {KIND_LABEL[k]}
            </button>
          ))}
        </div>
        <label className={styles.check}>
          <input type="checkbox" checked={watchOnly} onChange={(e) => setWatchOnly(e.target.checked)} />
          只看自選股
        </label>
        <label className={styles.check}>
          <input type="checkbox" checked={showPast} onChange={(e) => setShowPast(e.target.checked)} />
          顯示過去 7 天
        </label>
      </div>

      {q.isError && <p className={styles.muted}>{(q.error as Error).message}，稍後自動重試。</p>}
      {q.data && groups.length === 0 && <p className={styles.muted}>沒有符合條件的事件。</p>}

      {q.data &&
        groups.map(([d, list]) => (
          <section key={d} className={`${styles.day} ${d === q.data.today ? styles.today : ''}`} aria-label={dayLabel(d, q.data.today)}>
            <h2 className={styles.dayHead}>{dayLabel(d, q.data.today)}</h2>
            <ul className={styles.list}>
              {list.map((e, i) => (
                <li key={`${e.kind}-${e.code ?? e.title}-${i}`} className={`${styles.item} ${e.code && watch.has(e.code) ? styles.mine : ''}`}>
                  <span className={styles.tag}>{KIND_LABEL[e.kind]}</span>
                  <div className={styles.body}>
                    <div className={styles.line}>
                      {e.code && (
                        <Link to={`/stock/${e.code}`} className={styles.stock}>
                          {e.code} {e.name}
                        </Link>
                      )}
                      <span>{e.title}</span>
                    </div>
                    {e.detail && <span className={styles.detail}>{e.detail}</span>}
                    {e.place && <span className={styles.detail}>地點：{e.place}</span>}
                  </div>
                </li>
              ))}
            </ul>
          </section>
        ))}

      <p className={styles.muted}>
        資料：{q.data?.sources.join('、') ?? '臺灣證券交易所、公開資訊觀測站'}。公布期限為法定截止日，實際公布日以公司公告為準。左側色線表示自選股。本頁不構成投資建議。
      </p>
    </div>
  )
}
