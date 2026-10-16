import { useQuery } from '@tanstack/react-query'
import { useState, type FormEvent, type ReactNode } from 'react'
import { useNavigate, useParams } from 'react-router'
import { FundamentalsPanel } from '../components/FundamentalsPanel'
import { KChart, MA_LINES } from '../components/KChart'
import { fetchKbar, fetchStock, NotFoundError, searchStocks, type StockPage as Data } from '../lib/api'
import { arrow, direction, fmtDateLong, fmtFixed, fmtInt, fmtMonthDay, fmtPct, fmtPrice, fmtSigned, fmtYi } from '../lib/format'
import { liveToBar, taipeiToday } from '../lib/indicators'
import type { Mode } from '../lib/marketMode'
import { useLiveQuotes, type LiveStock } from '../lib/useLiveQuotes'
import styles from './StockPage.module.css'
import { periodText, statusOf, useAttention } from '../lib/attention'

const RANGES = [
  { years: 1, label: '1 年' },
  { years: 3, label: '3 年' },
  { years: 5, label: '5 年' },
  { years: 0, label: '全部' },
]

export function StockPage({ mode }: { mode: Mode }) {
  const { code = '2330' } = useParams()
  const q = useQuery({ queryKey: ['stock', code], queryFn: () => fetchStock(code), retry: (n, e) => !(e instanceof NotFoundError) && n < 2 })

  return (
    <div className={styles.page}>
      <StockSearch current={code} />
      {q.isPending && <div className={styles.skel} style={{ height: 480 }} aria-busy="true" aria-label="載入中" />}
      {q.isError && (
        <p className={styles.notice} role="status">
          {q.error instanceof NotFoundError ? `找不到股票「${code}」。請確認代號或用名稱搜尋。` : '目前無法取得資料，稍後再試。'}
        </p>
      )}
      {q.data && <Body d={q.data} mode={mode} />}
    </div>
  )
}

function StockSearch({ current }: { current: string }) {
  const navigate = useNavigate()
  const [text, setText] = useState('')
  const sugg = useQuery({ queryKey: ['search', text], queryFn: () => searchStocks(text), enabled: text.trim().length >= 1, staleTime: 60_000 })
  const [msg, setMsg] = useState('')

  async function submit(e: FormEvent) {
    e.preventDefault()
    const first = text.trim().split(/\s+/)[0]
    if (!first) return
    const hits = await searchStocks(first)
    if (hits.length) {
      setText('')
      setMsg('')
      navigate(`/stock/${hits[0].code}`)
    } else setMsg(`找不到「${first}」`)
  }

  return (
    <form className={styles.search} onSubmit={submit} role="search">
      <label htmlFor="stock-q" className="sr-only">
        搜尋股票
      </label>
      <input
        id="stock-q"
        className={styles.searchInput}
        list="stock-sugg"
        value={text}
        onChange={(e) => setText(e.target.value)}
        placeholder={`代號或名稱，例：2330、台積電（目前 ${current}）`}
        autoComplete="off"
      />
      <datalist id="stock-sugg">
        {(sugg.data ?? []).map((s) => (
          <option key={s.code} value={`${s.code} ${s.name}`} />
        ))}
      </datalist>
      <button type="submit" className={styles.searchBtn}>
        查詢
      </button>
      {msg && <span className={styles.muted}>{msg}</span>}
    </form>
  )
}

function Body({ d, mode }: { d: Data; mode: Mode }) {
  const code = d.profile.code
  const { data: liveData } = useLiveQuotes([code], mode === 'live')
  const today = taipeiToday()
  const live = liveData[code] as LiveStock | undefined
  const liveBar = mode === 'live' ? liveToBar(live, today) : undefined

  return mode === 'live' ? <LiveLayout d={d} live={liveBar ? live : undefined} liveBar={liveBar} /> : <ReportLayout d={d} />
}

// ── 盤中（終端機）──

function LiveLayout({ d, live, liveBar }: { d: Data; live?: LiveStock; liveBar?: ReturnType<typeof liveToBar> }) {
  const q = d.quote
  const price = live?.close ?? q.close
  const change = live?.change ?? q.change
  const pct = live?.change_pct ?? q.change_pct
  return (
    <>
      <section className={styles.quoteBar} aria-label="報價">
        <div className={styles.title}>
          <h1 className={styles.name}>{d.profile.name}</h1>
          <span className={`${styles.muted} num`}>{d.profile.code}</span>
          <span className={styles.tag}>{d.profile.industry}</span>
          <span className={styles.tag}>{d.profile.market}</span>
          <AttentionTags code={d.profile.code} />
        </div>
        <div className={styles.priceBox}>
          <span className={`${styles.price} num ${direction(change)}`}>{fmtPrice(price)}</span>
          <span className={`num ${direction(change)}`}>
            {arrow(change)} {fmtSigned(change, 2)}（{fmtPct(pct)}）
          </span>
          <span className={styles.badge}>{live ? `即時 ${live.time.slice(11, 19)}` : `${fmtMonthDay(d.asof)} 收盤`}</span>
        </div>
        <KV k="開盤" v={fmtPrice(live?.open ?? q.open)} />
        <KV k="最高" v={fmtPrice(live?.high ?? q.high)} />
        <KV k="最低" v={fmtPrice(live?.low ?? q.low)} />
        <KV k="成交量" v={`${fmtInt(live?.total_volume ?? q.volume)} 張`} />
        <KV k="52 週" v={`${fmtPrice(q.week52_low)} – ${fmtPrice(q.week52_high)}`} />
        {d.valuation && <KV k="本益比 / 股淨比" v={`${fmtFixed(d.valuation.current)} / ${d.valuation.pbr ?? '—'}`} />}
      </section>

      <div className={styles.mainGrid}>
        <ChartCard code={d.profile.code} liveBar={liveBar} mode="live" />
        <div className={styles.side}>
          <Card title="最佳五檔" note="盤中即時">
            <Book live={live} />
          </Card>
          <Card title="外資買賣超 · 近 15 日" note="張">
            <InstBars rows={d.institutional} />
          </Card>
        </div>
      </div>

      <div className={styles.tri}>
        <Card title="融資融券 · 近 10 日" note="張">
          <MarginTable rows={d.margin} />
          {d.shareholding && <ShareholdingBlock sh={d.shareholding} compact />}
        </Card>
        <Card title="月營收 · 近 13 個月" note="億元">
          <RevenueBars rows={d.revenue} />
        </Card>
        <Card title="本益比 · 五年位置" note="">
          <PEPosition v={d.valuation} />
        </Card>
      </div>
      <FundamentalsPanel key={d.profile.code} code={d.profile.code} />
      <Footer d={d} />
    </>
  )
}

// ── 盤後（研究報告）──

function ReportLayout({ d }: { d: Data }) {
  const q = d.quote
  const s = d.report.sections
  return (
    <article className={styles.report}>
      <header>
        <div className={styles.kicker}>
          個股報告 · {d.profile.code} {d.profile.name} · {d.profile.industry} · {fmtDateLong(d.asof)}
        </div>
        <div className={styles.reportTags}>
          <AttentionTags code={d.profile.code} />
        </div>
        <h1 className={styles.headline}>{d.report.headline}</h1>
        <p className={styles.lead}>{d.report.lead}</p>
      </header>

      <section className={styles.stats} aria-label="主要數據">
        <Stat label="收盤" value={fmtPrice(q.close)}>
          <span className={`num ${direction(q.change)}`}>
            {arrow(q.change)} {fmtSigned(q.change, 2)}（{fmtPct(q.change_pct)}）
          </span>
        </Stat>
        <Stat label="成交" value={`${fmtInt(q.volume)}`} unit="張">
          <span className={styles.muted}>{fmtYi(q.value, 1)} 億元</span>
        </Stat>
        <Stat label="本益比" value={d.valuation ? fmtFixed(d.valuation.current) : '—'} unit="倍">
          <span className={styles.muted}>
            股淨比 {d.valuation?.pbr ?? '—'}・殖利率 {d.valuation?.dividend_yield ?? '—'}%
          </span>
        </Stat>
        <Stat label="52 週區間" value={`${fmtPrice(q.week52_low)}–${fmtPrice(q.week52_high)}`}>
          <span className={styles.muted}>距高點 {fmtPct(((q.close - q.week52_high) / q.week52_high) * 100)}</span>
        </Stat>
      </section>

      <section className={styles.section} aria-labelledby="k-h">
        <h2 id="k-h" className={styles.h2}>股價走勢</h2>
        <ChartCard code={d.profile.code} mode="close" bare />
      </section>

      <div className={styles.cols2}>
        <section aria-labelledby="inst-h">
          <h2 id="inst-h" className={styles.h2}>三大法人</h2>
          {s.institutional && <p className={styles.summary}>{s.institutional}</p>}
          <InstTable rows={d.institutional.slice(-10)} />
        </section>
        <section aria-labelledby="mg-h">
          <h2 id="mg-h" className={styles.h2}>融資融券與股權分散</h2>
          {s.margin && <p className={styles.summary}>{s.margin}</p>}
          <MarginTable rows={d.margin} />
          {d.shareholding && (
            <div className={styles.shSection}>
              {s.shareholding && <p className={styles.summary}>{s.shareholding}</p>}
              <ShareholdingBlock sh={d.shareholding} />
            </div>
          )}
        </section>
      </div>

      <div className={styles.cols2}>
        <section aria-labelledby="rv-h">
          <h2 id="rv-h" className={styles.h2}>月營收</h2>
          {s.revenue && <p className={styles.summary}>{s.revenue}</p>}
          <RevenueBars rows={d.revenue} />
        </section>
        <section aria-labelledby="pe-h">
          <h2 id="pe-h" className={styles.h2}>估值</h2>
          {s.valuation && <p className={styles.summary}>{s.valuation}</p>}
          <PEPosition v={d.valuation} />
        </section>
      </div>
      <FundamentalsPanel key={d.profile.code} code={d.profile.code} />
      <Footer d={d} />
    </article>
  )
}

// ── 共用元件 ──

function ChartCard({ code, mode, liveBar, bare }: { code: string; mode: Mode; liveBar?: ReturnType<typeof liveToBar>; bare?: boolean }) {
  const [years, setYears] = useState(1)
  const [adjusted, setAdjusted] = useState(false)
  const k = useQuery({ queryKey: ['kbar', code, adjusted, years], queryFn: () => fetchKbar(code, adjusted, years), staleTime: 10 * 60_000 })
  const body = (
    <>
      <div className={styles.chartTools}>
        <div className={styles.seg} role="group" aria-label="期間">
          {RANGES.map((r) => (
            <button key={r.years} type="button" className={styles.segBtn} aria-pressed={years === r.years} onClick={() => setYears(r.years)}>
              {r.label}
            </button>
          ))}
        </div>
        <label className={styles.toggle}>
          <input type="checkbox" checked={adjusted} onChange={(e) => setAdjusted(e.target.checked)} /> 還原權值
        </label>
        <span className={styles.legend}>
          {MA_LINES.map((m) => (
            <span key={m.period} style={{ color: m.color }}>
              ━ MA{m.period}
            </span>
          ))}
        </span>
      </div>
      {k.data ? <KChart bars={k.data} liveBar={adjusted ? undefined : liveBar} mode={mode} /> : <div className={styles.skel} style={{ height: 420 }} />}
      {adjusted && <p className={styles.footnote}>還原權值：除權息前的價格依「參考價 ÷ 前一日收盤」調整，資料來源 FinMind 除權息結果。</p>}
    </>
  )
  return bare ? body : <Card title="日 K" note="">{body}</Card>
}

function Card({ title, note, children }: { title: string; note: string; children: ReactNode }) {
  return (
    <section className={styles.card}>
      <div className={styles.cardHead}>
        <h2 className={styles.cardTitle}>{title}</h2>
        <span>{note}</span>
      </div>
      <div className={styles.cardBody}>{children}</div>
    </section>
  )
}

function KV({ k, v }: { k: string; v: string }) {
  return (
    <div className={styles.kv}>
      <span className={styles.muted}>{k}</span>
      <b className="num">{v}</b>
    </div>
  )
}

function Stat({ label, value, unit, children }: { label: string; value: string; unit?: string; children?: ReactNode }) {
  return (
    <div className={styles.stat}>
      <div className={styles.kicker}>{label}</div>
      <div className={`${styles.statValue} num`}>
        {value}
        {unit && <span className={styles.unit}> {unit}</span>}
      </div>
      <div className={styles.statSub}>{children}</div>
    </div>
  )
}

function Book({ live }: { live?: LiveStock }) {
  if (!live || !live.bid?.length)
    return <p className={styles.muted}>目前沒有即時委買賣（休市或尚未開盤）。開盤後此處即時顯示五檔。</p>
  const rows = Array.from({ length: 5 }, (_, i) => ({ bid: live.bid[i], ask: live.ask[i] }))
  return (
    <table className={styles.table}>
      <thead>
        <tr>
          <th scope="col">委買量</th>
          <th scope="col">買價</th>
          <th scope="col">賣價</th>
          <th scope="col">委賣量</th>
        </tr>
      </thead>
      <tbody>
        {rows.map((r, i) => (
          <tr key={i}>
            <td className="num">{r.bid ? fmtInt(r.bid[1]) : '—'}</td>
            <td className="num up">{r.bid ? fmtPrice(r.bid[0]) : '—'}</td>
            <td className="num down">{r.ask ? fmtPrice(r.ask[0]) : '—'}</td>
            <td className="num">{r.ask ? fmtInt(r.ask[1]) : '—'}</td>
          </tr>
        ))}
      </tbody>
    </table>
  )
}

function InstBars({ rows }: { rows: Data['institutional'] }) {
  const max = Math.max(...rows.map((r) => Math.abs(r.foreign)), 1)
  const last = rows[rows.length - 1]
  return (
    <>
      <div className={styles.bars} role="img" aria-label="外資近 15 日買賣超柱狀圖">
        <div className={styles.zero} />
        {rows.map((r) => {
          const h = (Math.abs(r.foreign) / max) * 50
          return (
            <div key={r.date} className={styles.barCol} title={`${fmtMonthDay(r.date)} ${fmtSigned(r.foreign)} 張`}>
              <div className={r.foreign >= 0 ? styles.barUp : styles.barDown} style={{ top: `${r.foreign >= 0 ? 50 - h : 50}%`, height: `${Math.max(h, 0.6)}%` }} />
            </div>
          )
        })}
      </div>
      <div className={`${styles.axis} num`}>
        <span>{fmtMonthDay(rows[0].date)}</span>
        <span>{fmtMonthDay(last.date)}</span>
      </div>
      <div className={`${styles.tri3} num`}>
        <Mini k={`外資 ${fmtMonthDay(last.date)}`} v={last.foreign} />
        <Mini k="投信" v={last.trust} />
        <Mini k="自營商" v={last.dealer} />
      </div>
    </>
  )
}

function Mini({ k, v }: { k: string; v: number }) {
  return (
    <div>
      <div className={styles.muted}>{k}</div>
      <div className={direction(v)}>{fmtSigned(v)}</div>
    </div>
  )
}

function InstTable({ rows }: { rows: Data['institutional'] }) {
  return (
    <div className={styles.tableBox}>
      <table className={styles.table}>
        <thead>
          <tr>
            <th scope="col">日期</th>
            <th scope="col">外資</th>
            <th scope="col">投信</th>
            <th scope="col">自營商</th>
          </tr>
        </thead>
        <tbody>
          {[...rows].reverse().map((r) => (
            <tr key={r.date}>
              <td className="num">{fmtMonthDay(r.date)}</td>
              {(['foreign', 'trust', 'dealer'] as const).map((k) => (
                <td key={k} className={`num ${direction(r[k])}`}>
                  {fmtSigned(r[k])}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
      <p className={styles.footnote}>單位：張</p>
    </div>
  )
}

function MarginTable({ rows }: { rows: Data['margin'] }) {
  return (
    <div className={styles.tableBox}>
      <table className={styles.table}>
        <thead>
          <tr>
            <th scope="col">日期</th>
            <th scope="col">融資餘額</th>
            <th scope="col">增減</th>
            <th scope="col">融券餘額</th>
          </tr>
        </thead>
        <tbody>
          {[...rows].reverse().map((r) => (
            <tr key={r.date}>
              <td className="num">{fmtMonthDay(r.date)}</td>
              <td className="num">{fmtInt(r.margin_balance)}</td>
              <td className={`num ${direction(r.margin_change)}`}>{fmtSigned(r.margin_change)}</td>
              <td className="num">{fmtInt(r.short_balance)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function RevenueBars({ rows }: { rows: Data['revenue'] }) {
  const max = Math.max(...rows.map((r) => r.revenue), 1)
  const last = rows[rows.length - 1]
  return (
    <>
      <div className={styles.revBars} role="img" aria-label={`近 ${rows.length} 個月營收柱狀圖，最新 ${last.year}/${last.month} ${fmtYi(last.revenue, 1)} 億元`}>
        {rows.map((r, i) => (
          <div key={`${r.year}-${r.month}`} className={styles.revCol} title={`${r.year}/${r.month} ${fmtYi(r.revenue, 1)} 億`}>
            <div className={i === rows.length - 1 ? styles.revLast : styles.revBar} style={{ height: `${(r.revenue / max) * 100}%` }} />
            <span className={styles.revLabel}>{r.month}</span>
          </div>
        ))}
      </div>
      <div className={`${styles.tri3} num`}>
        <div>
          <div className={styles.muted}>
            {last.year}/{last.month} 營收
          </div>
          <div>{fmtYi(last.revenue, 1)}</div>
        </div>
        <div>
          <div className={styles.muted}>年增</div>
          <div className={last.yoy == null ? '' : direction(last.yoy)}>{last.yoy == null ? '—' : fmtPct(last.yoy)}</div>
        </div>
        <div>
          <div className={styles.muted}>月增</div>
          <div className={last.mom == null ? '' : direction(last.mom)}>{last.mom == null ? '—' : fmtPct(last.mom)}</div>
        </div>
      </div>
    </>
  )
}

function PEPosition({ v }: { v: Data['valuation'] }) {
  if (!v) return <p className={styles.muted}>無本益比資料（可能為虧損或 ETF）。</p>
  const pos = (x: number) => `${((x - v.min) / (v.max - v.min || 1)) * 100}%`
  return (
    <div>
      <div className={`${styles.peNow} num`}>
        {fmtFixed(v.current)} <span className={styles.unit}>倍</span>
      </div>
      <div className={styles.muted}>高於過去五年 {v.pct_rank.toFixed(0)}% 的交易日</div>
      <div className={styles.peTrack} role="img" aria-label={`五年本益比區間 ${v.min} 至 ${v.max}，中位數 ${v.median}，目前 ${v.current}`}>
        <div className={styles.peFill} style={{ width: pos(v.current) }} />
        <div className={styles.peMedian} style={{ left: pos(v.median) }} />
      </div>
      <div className={`${styles.peScale} num`}>
        <span>{fmtFixed(v.min)}<br />五年低</span>
        <span style={{ left: pos(v.median) }} className={styles.peMid}>
          {fmtFixed(v.median)}
          <br />
          中位數
        </span>
        <span>{fmtFixed(v.max)}<br />五年高</span>
      </div>
      <p className={styles.footnote}>
        統計 {v.start} 至 {v.end}，共 {fmtInt(v.days)} 個交易日
      </p>
    </div>
  )
}

function Footer({ d }: { d: Data }) {
  return (
    <p className={styles.footnote}>
      資料：{d.sources.join('、')}；盤中報價：永豐金。紅色為上漲、綠色為下跌。資料日期 {d.asof}。本頁不構成投資建議。
    </p>
  )
}

function ShareholdingBlock({ sh, compact }: { sh: NonNullable<Data['shareholding']>; compact?: boolean }) {
  return (
    <div className={compact ? styles.shCompact : styles.shBox}>
      <div className={styles.shHead}>
        <span>集保股權分散（{sh.date}）</span>
        <span className="num">總股東 {fmtInt(sh.total_holders)} 人</span>
      </div>
      <div
        className={styles.shBar}
        role="img"
        aria-label={`大戶（>400 張）${sh.large_400_pct.toFixed(2)}%、中實戶（50–400 張）${sh.mid_pct.toFixed(2)}%、散戶（≤50 張）${sh.retail_pct.toFixed(2)}%`}
      >
        <div className={styles.shLarge} style={{ width: `${sh.large_400_pct}%` }} title={`>400 張大戶 ${sh.large_400_pct.toFixed(2)}%`} />
        <div className={styles.shMid} style={{ width: `${sh.mid_pct}%` }} title={`50–400 張中實戶 ${sh.mid_pct.toFixed(2)}%`} />
        <div className={styles.shRetail} style={{ width: `${sh.retail_pct}%` }} title={`≤50 張散戶 ${sh.retail_pct.toFixed(2)}%`} />
      </div>
      <div className={`${styles.shStats} num`}>
        <div>
          <div className={styles.muted}>&gt;400 張大戶</div>
          <div>
            <b>{fmtFixed(sh.large_400_pct)}%</b> <span className={styles.muted}>({fmtInt(sh.large_400_holders)}人)</span>
          </div>
        </div>
        <div>
          <div className={styles.muted}>&gt;1,000 張千張</div>
          <div>
            <b>{fmtFixed(sh.large_1000_pct)}%</b> <span className={styles.muted}>({fmtInt(sh.large_1000_holders)}人)</span>
          </div>
        </div>
        <div>
          <div className={styles.muted}>≤50 張散戶</div>
          <div>
            <b>{fmtFixed(sh.retail_pct)}%</b> <span className={styles.muted}>({fmtInt(sh.retail_holders)}人)</span>
          </div>
        </div>
      </div>
    </div>
  )
}

function AttentionTags({ code }: { code: string }) {
  const { data } = useAttention()
  const { disposition, notice } = statusOf(data, code)
  return (
    <>
      {disposition && (
        <span className={`${styles.tag} ${styles.alertTag}`} title={`${disposition.reason}${disposition.match ? `，${disposition.match}` : ''}`}>
          處置 {periodText(disposition)}
        </span>
      )}
      {notice && (
        <span className={`${styles.tag} ${styles.alertTag}`} title={notice.reason}>
          注意股
        </span>
      )}
    </>
  )
}

