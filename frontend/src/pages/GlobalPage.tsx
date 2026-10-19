import { useQuery } from '@tanstack/react-query'
import { useEffect, useRef, useState, type FormEvent } from 'react'
import { useSearchParams } from 'react-router'
import { KChart } from '../components/KChart'
import { Sparkline } from '../components/Sparkline'
import type { Bar } from '../lib/api'
import { arrow, direction, fmtFixed, fmtMonthDay, fmtPct, fmtSigned } from '../lib/format'
import type { Mode } from '../lib/marketMode'
import {
  DEFAULT_US_FILTERS,
  filterUsStocks,
  sortUsStocks,
  US_PRESETS,
  type UsFilters,
  type UsSortKey,
  type UsStocksData,
} from '../lib/usStocks'
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
  const us = useQuery({ queryKey: ['global-us'], queryFn: () => getJson<UsStocksData>('/api/global/us'), staleTime: 10 * 60_000, retry: 2 })
  // 代號放網址（?s=AAPL），可分享、可加書籤、上一頁可回到前一檔
  const [params, setParams] = useSearchParams()
  const symbol = params.get('s') || 'AAPL'
  const setSymbol = (s: string) => setParams({ s }, { replace: false })
  const lookupRef = useRef<HTMLElement | null>(null)

  const pickSymbol = (sym: string) => {
    setSymbol(sym)
    lookupRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' })
  }

  // 從網址帶代號進來時捲到查詢區，只捲一次。要等上方表格（q）與下方美股區（us）都載入：
  // 下方還沒長出來時頁面不夠高，scrollIntoView 會被捲動上限卡住、停在半途
  const pendingScroll = useRef(params.has('s'))
  useEffect(() => {
    if (pendingScroll.current && q.data && us.isFetched) {
      pendingScroll.current = false
      lookupRef.current?.scrollIntoView({ block: 'start' })
    }
  }, [q.data, us.isFetched])

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
              <div className={styles.tableBox}>
              <table className={styles.table}>
                <tbody>
                  {g.items.map((it) => (
                    <tr key={it.symbol}>
                      <th scope="row">
                        <button type="button" className={styles.symBtn} onClick={() => pickSymbol(it.symbol)} title={`看 ${it.name} K 線`}>
                          {it.name}
                        </button>
                      </th>
                      <td className="num">{fmtFixed(it.close, it.close < 100 ? 2 : 2)}</td>
                      <td className={`num ${direction(it.change_pct)}`}>{arrow(it.change_pct)} {fmtPct(it.change_pct)}</td>
                      <td className={`num ${styles.date}`}>{fmtMonthDay(it.date)}</td>
                      <td className={styles.spark}>
                        <Sparkline values={it.spark} label={it.name} width={72} />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
              </div>
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

      <Lookup mode={mode} symbol={symbol} setSymbol={setSymbol} sectionRef={lookupRef} />

      {us.data && (
        <>
          <UsScreenerSection data={us.data} onPick={pickSymbol} />
          <UsEarningsSection data={us.data} onPick={pickSymbol} />
        </>
      )}
      {us.isError && <p className={styles.muted}>美股選股與財報日曆：{(us.error as Error).message}</p>}

      <p className={styles.muted}>資料：Yahoo Finance。本頁不構成投資建議。</p>
    </div>
  )
}

function Lookup({
  mode,
  symbol,
  setSymbol,
  sectionRef,
}: {
  mode: Mode
  symbol: string
  setSymbol: (s: string) => void
  sectionRef: React.RefObject<HTMLElement | null>
}) {
  const [text, setText] = useState('')
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
    <section ref={sectionRef} className={styles.card} aria-labelledby="lk-h">
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

function UsScreenerSection({ data, onPick }: { data: UsStocksData; onPick: (sym: string) => void }) {
  const [preset, setPreset] = useState('all')
  const [f, setF] = useState<UsFilters>(DEFAULT_US_FILTERS)
  const [sortKey, setSortKey] = useState<UsSortKey>('market_cap_b')
  const [asc, setAsc] = useState(false)

  const applyPreset = (id: string) => {
    setPreset(id)
    const found = US_PRESETS.find((p) => p.id === id)
    setF({ ...DEFAULT_US_FILTERS, ...(found?.filters ?? {}) })
  }

  const toggleSort = (k: UsSortKey) => {
    if (sortKey === k) setAsc((v) => !v)
    else {
      setSortKey(k)
      setAsc(k === 'pe' || k === 'forward_pe' || k === 'rating_score')
    }
  }

  const numOrNull = (s: string) => (s.trim() === '' ? null : Number(s))
  const rows = sortUsStocks(filterUsStocks(data.rows, f), sortKey, asc)

  const thSort = (k: UsSortKey, label: string) => (
    <th scope="col">
      <button type="button" className={styles.sortBtn} onClick={() => toggleSort(k)}>
        {label} {sortKey === k ? (asc ? '↑' : '↓') : ''}
      </button>
    </th>
  )

  return (
    <section className={styles.card} aria-labelledby="us-sc-h">
      <div className={styles.cardHead}>
        <h2 id="us-sc-h" className={styles.h2}>美股權值 50 多因子選股</h2>
        <span className={`${styles.muted} num`}>
          符合 {rows.length} / {data.rows.length} 檔 · 資料日期 {data.asof}（點擊股票可看 K 線）
        </span>
      </div>

      <div className={styles.examples} role="group" aria-label="美股快選策略">
        {US_PRESETS.map((p) => (
          <button key={p.id} type="button" className={styles.chip} aria-pressed={preset === p.id} onClick={() => applyPreset(p.id)}>
            {p.label}
          </button>
        ))}
      </div>

      <div className={styles.filters}>
        <label className={styles.field}>
          板塊
          <select
            className={styles.select}
            value={f.sector}
            onChange={(e) => {
              setPreset('custom')
              setF({ ...f, sector: e.target.value })
            }}
          >
            <option value="">全部</option>
            {data.sectors.map((s) => (
              <option key={s} value={s}>{s}</option>
            ))}
          </select>
        </label>
        <label className={styles.field}>
          市值 ≥
          <select
            className={styles.select}
            value={f.minMcapB ?? ''}
            onChange={(e) => {
              setPreset('custom')
              setF({ ...f, minMcapB: numOrNull(e.target.value) })
            }}
          >
            <option value="">不限</option>
            <option value="100">1,000 億美元</option>
            <option value="300">3,000 億美元</option>
            <option value="1000">1 兆美元</option>
          </select>
        </label>
        <label className={styles.field}>
          本益比 ≤
          <input
            type="number"
            className={styles.numInput}
            value={f.maxPe ?? ''}
            placeholder="不限"
            onChange={(e) => {
              setPreset('custom')
              setF({ ...f, maxPe: numOrNull(e.target.value) })
            }}
          />
        </label>
        <label className={styles.field}>
          前瞻 PE ≤
          <input
            type="number"
            className={styles.numInput}
            value={f.maxForwardPe ?? ''}
            placeholder="不限"
            onChange={(e) => {
              setPreset('custom')
              setF({ ...f, maxForwardPe: numOrNull(e.target.value) })
            }}
          />
        </label>
        <label className={styles.field}>
          殖利率 ≥ %
          <input
            type="number"
            step="0.5"
            className={styles.numInput}
            value={f.minYield ?? ''}
            placeholder="不限"
            onChange={(e) => {
              setPreset('custom')
              setF({ ...f, minYield: numOrNull(e.target.value) })
            }}
          />
        </label>
        <label className={styles.field}>
          <input
            type="checkbox"
            checked={f.aboveMa200}
            onChange={(e) => {
              setPreset('custom')
              setF({ ...f, aboveMa200: e.target.checked })
            }}
          />
          站上年線（200MA）
        </label>
      </div>

      <div className={styles.tableBox}>
        <table className={styles.table}>
          <thead>
            <tr>
              <th scope="col">股票</th>
              <th scope="col">收盤（USD）</th>
              {thSort('change_pct', '漲跌')}
              {thSort('market_cap_b', '市值（十億）')}
              {thSort('pe', '本益比')}
              {thSort('forward_pe', '前瞻 PE')}
              {thSort('dividend_yield', '殖利率')}
              {thSort('pullback_pct', '距 52 週高')}
              {thSort('rating_score', '華爾街評等')}
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.symbol}>
                <th scope="row">
                  <button type="button" className={styles.symBtn} onClick={() => onPick(r.symbol)}>
                    <span className={`${styles.symCode} num`}>{r.symbol}</span>
                    {r.name}
                  </button>
                  <span className={styles.sectorTag}>{r.sector}</span>
                </th>
                <td className="num">{fmtFixed(r.close)}</td>
                <td className={`num ${direction(r.change_pct)}`}>
                  {arrow(r.change_pct)} {fmtPct(r.change_pct)}
                </td>
                <td className="num">{r.market_cap_b != null ? fmtFixed(r.market_cap_b, 0) : '—'}</td>
                <td className="num">{r.pe != null ? fmtFixed(r.pe, 1) : '—'}</td>
                <td className="num">{r.forward_pe != null ? fmtFixed(r.forward_pe, 1) : '—'}</td>
                <td className="num">{r.dividend_yield > 0 ? `${fmtFixed(r.dividend_yield)}%` : '—'}</td>
                <td className={`num ${direction(r.pullback_pct)}`}>{fmtPct(r.pullback_pct)}</td>
                <td className="num">
                  {r.rating_label ? `${r.rating_label}${r.rating_score != null ? ` (${fmtFixed(r.rating_score, 1)})` : ''}` : '—'}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  )
}

function UsEarningsSection({ data, onPick }: { data: UsStocksData; onPick: (sym: string) => void }) {
  const [showAll, setShowAll] = useState(false)
  const list = showAll
    ? [...data.rows].sort((a, b) => (a.earnings_date ?? '9999').localeCompare(b.earnings_date ?? '9999'))
    : data.upcoming_earnings

  return (
    <section className={styles.card} aria-labelledby="us-earn-h">
      <div className={styles.cardHead}>
        <h2 id="us-earn-h" className={styles.h2}>美股財報日曆與華爾街共識</h2>
        <div className={styles.seg} role="group" aria-label="財報範圍">
          <button type="button" className={styles.segBtn} aria-pressed={!showAll} onClick={() => setShowAll(false)}>
            近期財報（{data.upcoming_earnings.length}）
          </button>
          <button type="button" className={styles.segBtn} aria-pressed={showAll} onClick={() => setShowAll(true)}>
            全部 50 檔
          </button>
        </div>
      </div>

      <div className={styles.tableBox}>
        <table className={styles.table}>
          <thead>
            <tr>
              <th scope="col">財報日（美東）</th>
              <th scope="col">股票</th>
              <th scope="col">收盤</th>
              <th scope="col">過去四季 EPS</th>
              <th scope="col">當年預估 EPS</th>
              <th scope="col">下年預估 EPS</th>
              <th scope="col">前瞻本益比</th>
              <th scope="col">華爾街評等</th>
            </tr>
          </thead>
          <tbody>
            {list.map((r) => (
              <tr key={r.symbol}>
                <td className="num">
                  {r.earnings_date ?? '—'}
                  {r.earnings_date && r.earnings_is_estimate && <span className={styles.estTag}>預估</span>}
                </td>
                <th scope="row">
                  <button type="button" className={styles.symBtn} onClick={() => onPick(r.symbol)}>
                    <span className={`${styles.symCode} num`}>{r.symbol}</span>
                    {r.name}
                  </button>
                  <span className={styles.sectorTag}>{r.sector}</span>
                </th>
                <td className="num">{fmtFixed(r.close)}</td>
                <td className="num">{r.eps_ttm != null ? fmtFixed(r.eps_ttm) : '—'}</td>
                <td className="num">{r.eps_current_year != null ? fmtFixed(r.eps_current_year) : '—'}</td>
                <td className="num">{r.eps_forward != null ? fmtFixed(r.eps_forward) : '—'}</td>
                <td className="num">{r.forward_pe != null ? fmtFixed(r.forward_pe, 1) : '—'}</td>
                <td className="num">
                  {r.rating_label ? `${r.rating_label}${r.rating_score != null ? ` (${fmtFixed(r.rating_score, 1)})` : ''}` : '—'}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className={styles.muted}>{data.note}</p>
    </section>
  )
}
