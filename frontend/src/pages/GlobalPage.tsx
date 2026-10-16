import { useQuery } from '@tanstack/react-query'
import { useState, type FormEvent } from 'react'
import { KChart } from '../components/KChart'
import { Sparkline } from '../components/Sparkline'
import type { Bar } from '../lib/api'
import { arrow, direction, fmtFixed, fmtMonthDay, fmtPct, fmtSigned } from '../lib/format'
import type { Mode } from '../lib/marketMode'
import styles from './GlobalPage.module.css'

interface Item {
  symbol: string
  name: string
  date: string
  close: number
  change: number
  change_pct: number
  spark: number[]
}

interface Adr {
  name: string
  adr: string
  local: string
  ratio: number
  adr_close: number
  adr_date: string
  local_close: number
  local_date: string
  fx: number
  fx_date: string
  implied_twd: number
  premium_pct: number
  adr_change_pct: number
}

interface GlobalData {
  generated_at: string
  groups: { title: string; items: Item[] }[]
  adrs: Adr[]
  note: string
  sources: string[]
}

async function getJson<T>(url: string): Promise<T> {
  const r = await fetch(url)
  if (!r.ok) {
    let msg = `API ${r.status}`
    try {
      msg = (await r.json()).detail ?? msg
    } catch {
      // 非 JSON
    }
    throw new Error(msg)
  }
  return r.json()
}

const RANGES = [
  { key: '6mo', label: '6 月' },
  { key: '1y', label: '1 年' },
  { key: '5y', label: '5 年' },
]
const EXAMPLES = ['AAPL', 'NVDA', 'TSM', '0700.HK', '9988.HK']

export function GlobalPage({ mode }: { mode: Mode }) {
  const q = useQuery({ queryKey: ['global'], queryFn: () => getJson<GlobalData>('/api/global'), refetchInterval: 5 * 60_000, retry: 3, retryDelay: 5000 })
  return (
    <div className={styles.page}>
      <header>
        <h1 className={styles.h1}>全球市場</h1>
        <p className={styles.muted}>{q.data?.note ?? '資料載入中…'}</p>
      </header>
      {q.data && (
        <div className={styles.groups}>
          {q.data.groups.map((g) => (
            <section key={g.title} className={styles.card} aria-label={g.title}>
              <h2 className={styles.h2}>{g.title}</h2>
              <table className={styles.table}>
                <tbody>
                  {g.items.map((it) => (
                    <tr key={it.symbol}>
                      <th scope="row">{it.name}</th>
                      <td className="num">{fmtFixed(it.close, it.close < 100 ? 2 : 2)}</td>
                      <td className={`num ${direction(it.change_pct)}`}>{arrow(it.change_pct)} {fmtPct(it.change_pct)}</td>
                      <td className={`num ${styles.date}`}>{fmtMonthDay(it.date)}</td>
                      <td className={styles.spark}>
                        <Sparkline values={it.spark} label={it.name} />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </section>
          ))}
        </div>
      )}

      {q.data && q.data.adrs.length > 0 && (
        <section className={styles.card} aria-labelledby="adr-h">
          <h2 id="adr-h" className={styles.h2}>台灣 ADR 溢價</h2>
          <div className={styles.tableBox}>
            <table className={styles.table}>
              <thead>
                <tr>
                  <th scope="col">公司</th>
                  <th scope="col">ADR 收盤（美元）</th>
                  <th scope="col">換算台幣／股</th>
                  <th scope="col">台股收盤</th>
                  <th scope="col">溢價</th>
                </tr>
              </thead>
              <tbody>
                {q.data.adrs.map((a) => (
                  <tr key={a.adr}>
                    <th scope="row">
                      {a.name} <span className={styles.muted}>{a.adr}</span>
                    </th>
                    <td className="num">
                      {fmtFixed(a.adr_close)} <span className={styles.date}>{fmtMonthDay(a.adr_date)}</span>
                    </td>
                    <td className="num">{fmtFixed(a.implied_twd)}</td>
                    <td className="num">
                      {fmtFixed(a.local_close)} <span className={styles.date}>{fmtMonthDay(a.local_date)}</span>
                    </td>
                    <td className={`num ${direction(a.premium_pct)}`}>{fmtSigned(a.premium_pct, 2)}%</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className={styles.muted}>
            換算台幣／股＝ADR 收盤 × 美元兌台幣（{q.data.adrs[0].fx}）÷ 換算比例。比例：台積電、聯電 1 ADR＝5 股，日月光投控 1 ADR＝2 股。ADR 與台股收盤日不同，溢價會受隔夜行情影響。
          </p>
        </section>
      )}
      {q.isError && <p className={styles.muted}>{(q.error as Error).message}，稍後自動重試。</p>}

      <Lookup mode={mode} />
      <p className={styles.muted}>資料：Yahoo Finance。本頁不構成投資建議。</p>
    </div>
  )
}

function Lookup({ mode }: { mode: Mode }) {
  const [text, setText] = useState('')
  const [symbol, setSymbol] = useState('AAPL')
  const [range, setRange] = useState('1y')
  const k = useQuery({
    queryKey: ['gkbar', symbol, range],
    queryFn: () => getJson<{ meta: { symbol: string; name: string; currency: string; exchange: string }; bars: Bar[] }>(`/api/global/kbar?symbol=${encodeURIComponent(symbol)}&range=${range}`),
    retry: false,
    staleTime: 10 * 60_000,
  })
  const submit = (e: FormEvent) => {
    e.preventDefault()
    if (text.trim()) setSymbol(text.trim().toUpperCase())
  }
  const bars = k.data?.bars ?? []
  const last = bars[bars.length - 1]
  const prev = bars[bars.length - 2]
  const chg = last && prev ? last.close - prev.close : 0
  return (
    <section className={styles.card} aria-labelledby="lk-h">
      <h2 id="lk-h" className={styles.h2}>港美股查詢</h2>
      <form className={styles.lookup} onSubmit={submit}>
        <label htmlFor="g-sym" className="sr-only">
          代號
        </label>
        <input id="g-sym" className={styles.input} value={text} onChange={(e) => setText(e.target.value)} placeholder="Yahoo 代號，例：AAPL、0700.HK" autoComplete="off" />
        <button type="submit" className={styles.primary}>
          查詢
        </button>
        <span className={styles.examples}>
          {EXAMPLES.map((s) => (
            <button key={s} type="button" className={styles.chip} aria-pressed={symbol === s} onClick={() => setSymbol(s)}>
              {s}
            </button>
          ))}
        </span>
      </form>
      {k.isError && <p className={styles.muted}>{(k.error as Error).message}</p>}
      {k.data && last && (
        <>
          <div className={styles.quote}>
            <strong className={styles.name}>{k.data.meta.name}</strong>
            <span className={styles.muted}>
              {k.data.meta.symbol}・{k.data.meta.exchange}・{k.data.meta.currency}
            </span>
            <span className={`num ${styles.price} ${direction(chg)}`}>{fmtFixed(last.close)}</span>
            <span className={`num ${direction(chg)}`}>
              {arrow(chg)} {fmtSigned(chg, 2)}（{fmtPct(prev ? (chg / prev.close) * 100 : 0)}）
            </span>
            <span className={styles.muted}>{fmtMonthDay(last.date)} 收盤</span>
          </div>
          <div className={styles.seg} role="group" aria-label="期間">
            {RANGES.map((r) => (
              <button key={r.key} type="button" className={styles.segBtn} aria-pressed={range === r.key} onClick={() => setRange(r.key)}>
                {r.label}
              </button>
            ))}
          </div>
          <KChart bars={bars} mode={mode} height={380} />
          <p className={styles.muted}>沿用台股慣例：紅色為上漲、綠色為下跌。</p>
        </>
      )}
    </section>
  )
}
