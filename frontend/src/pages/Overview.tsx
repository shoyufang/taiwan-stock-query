import { useQuery } from '@tanstack/react-query'
import type { ReactNode } from 'react'
import { IndexChart } from '../components/IndexChart'
import { fetchOverview, NotReadyError, type ForeignNet, type Overview as Data, type Quote } from '../lib/api'
import { arrow, direction, fmtDateLong, fmtFixed, fmtInt, fmtMonthDay, fmtPct, fmtPrice, fmtSigned, fmtWanLots, fmtYi } from '../lib/format'
import type { Mode } from '../lib/marketMode'
import styles from './Overview.module.css'

export function Overview({ mode }: { mode: Mode }) {
  const q = useQuery({
    queryKey: ['overview'],
    queryFn: fetchOverview,
    refetchInterval: 60_000,
    retry: (count, err) => err instanceof NotReadyError || count < 2,
    retryDelay: 5_000,
  })

  if (q.isPending) return <Skeleton />
  if (q.isError)
    return (
      <p className={styles.notice} role="status">
        {q.error instanceof NotReadyError ? '資料準備中，幾秒後自動重試…' : '目前無法取得資料，稍後自動重試。'}
      </p>
    )
  return <OverviewBody d={q.data} mode={mode} />
}

function OverviewBody({ d, mode }: { d: Data; mode: Mode }) {
  return (
    <article className={styles.page}>
      {mode === 'live' && (
        <p className={styles.notice} role="note">
          盤中即時行情將於 P2 上線；以下為 {fmtMonthDay(d.asof)} 收盤資料。
        </p>
      )}

      <header className={styles.lead}>
        <div className={styles.kicker}>盤後總覽 · {fmtDateLong(d.asof)}</div>
        <h1 className={styles.headline}>{d.headline}</h1>
        <p className={styles.leadText}>{d.lead}</p>
      </header>

      <section className={styles.stats} aria-label="主要數據">
        <Stat label="加權指數" value={fmtFixed(d.taiex.close)}>
          <span className={`num ${direction(d.taiex.change)}`}>
            {arrow(d.taiex.change)} {fmtSigned(d.taiex.change, 2)}（{fmtPct(d.taiex.change_pct)}）
          </span>
        </Stat>
        <Stat label="成交金額" value={fmtYi(d.turnover_twd)} unit="億元">
          <span className={styles.muted}>上市全部證券</span>
        </Stat>
        <Stat label="漲 / 平 / 跌" value="">
          <span className="num">
            <span className="up">{fmtInt(d.breadth.up)}</span> / {fmtInt(d.breadth.flat)} / <span className="down">{fmtInt(d.breadth.down)}</span>
          </span>
          <span className={styles.muted}>
            上市股票；漲停 {d.breadth.up_limit}、跌停 {d.breadth.down_limit}
          </span>
        </Stat>
        <Stat label="外資買賣超" value={fmtWanLots(d.institutional.foreign)} unit="萬張" dir={direction(d.institutional.foreign)}>
          <span className={styles.muted}>
            投信 {fmtWanLots(d.institutional.trust)}・自營商 {fmtWanLots(d.institutional.dealer)} 萬張
          </span>
        </Stat>
      </section>

      <section aria-labelledby="chart-h" className={styles.section}>
        <div className={styles.sectionHead}>
          <h2 id="chart-h" className={styles.h2}>加權指數　近六個月</h2>
          <span className={`${styles.muted} num`}>
            {d.index_series[0]?.date} 至 {d.asof}
          </span>
        </div>
        <IndexChart series={d.index_series} label="加權指數" />
      </section>

      <div className={styles.cols3}>
        <section aria-labelledby="tv-h">
          <h2 id="tv-h" className={styles.h2}>成交值排行</h2>
          <QuoteTable rows={d.top_value} showValue />
        </section>
        <section aria-labelledby="inst-h">
          <h2 id="inst-h" className={styles.h2}>三大法人</h2>
          <InstBars inst={d.institutional} />
          <h3 className={styles.h3}>外資買超</h3>
          <ForeignTable rows={d.foreign_buy} />
          <h3 className={styles.h3}>外資賣超</h3>
          <ForeignTable rows={d.foreign_sell} />
        </section>
        <section aria-labelledby="mv-h">
          <h2 id="mv-h" className={styles.h2}>漲幅居前</h2>
          <QuoteTable rows={d.gainers} />
          <h2 className={styles.h2} style={{ marginTop: 28 }}>跌幅居前</h2>
          <QuoteTable rows={d.losers} />
        </section>
      </div>

      <section aria-labelledby="intl-h" className={styles.section}>
        <h2 id="intl-h" className={styles.h2}>國際市場</h2>
        <div className={styles.tableBox}>
          <table className={styles.table}>
            <thead>
              <tr>
                <th scope="col">指標</th>
                <th scope="col">收盤日</th>
                <th scope="col">收盤</th>
                <th scope="col">漲跌幅</th>
              </tr>
            </thead>
            <tbody>
              {d.international.map((r) => (
                <tr key={r.symbol}>
                  <td>{r.name}</td>
                  <td className="num">{fmtMonthDay(r.date)}</td>
                  <td className="num">{fmtFixed(r.close)}</td>
                  <td className={`num ${r.symbol === 'TWD=X' ? '' : direction(r.change_pct)}`}>{fmtPct(r.change_pct)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p className={styles.footnote}>美股取台股該日開盤前最後一個已收盤交易日；美元/台幣上升代表台幣貶值。</p>
      </section>

      <footer className={styles.footnote}>
        資料：{d.sources.join('、')}。紅色為上漲、綠色為下跌（台股慣例）。資料產生時間 {d.generated_at.replace('T', ' ').slice(0, 16)}。
      </footer>
    </article>
  )
}

function Stat({ label, value, unit, dir, children }: { label: string; value: string; unit?: string; dir?: string; children?: ReactNode }) {
  return (
    <div className={styles.stat}>
      <div className={styles.kicker}>{label}</div>
      {value && (
        <div className={`${styles.statValue} num ${dir ?? ''}`}>
          {value}
          {unit && <span className={styles.unit}> {unit}</span>}
        </div>
      )}
      <div className={styles.statSub}>{children}</div>
    </div>
  )
}

function QuoteTable({ rows, showValue }: { rows: Quote[]; showValue?: boolean }) {
  return (
    <div className={styles.tableBox}>
      <table className={styles.table}>
        <thead>
          <tr>
            <th scope="col">股票</th>
            <th scope="col">收盤</th>
            <th scope="col">漲跌</th>
            {showValue && <th scope="col">億元</th>}
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.code}>
              <td>
                <span className={`${styles.code} num`}>{r.code}</span>
                {r.name}
              </td>
              <td className="num">{fmtPrice(r.close)}</td>
              <td className={`num ${direction(r.change_pct)}`}>{fmtPct(r.change_pct)}</td>
              {showValue && <td className="num">{fmtYi(r.value_twd, 1)}</td>}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function ForeignTable({ rows }: { rows: ForeignNet[] }) {
  return (
    <table className={styles.table}>
      <tbody>
        {rows.map((r) => (
          <tr key={r.code}>
            <td>
              <span className={`${styles.code} num`}>{r.code}</span>
              {r.name}
            </td>
            <td className={`num ${direction(r.lots)}`}>{fmtSigned(r.lots)} 張</td>
          </tr>
        ))}
      </tbody>
    </table>
  )
}

function InstBars({ inst }: { inst: Data['institutional'] }) {
  const items = [
    ['外資', inst.foreign],
    ['投信', inst.trust],
    ['自營商', inst.dealer],
  ] as const
  const max = Math.max(...items.map(([, v]) => Math.abs(v)), 1)
  return (
    <div className={styles.inst}>
      {items.map(([name, v]) => {
        const w = (Math.abs(v) / max) * 50
        return (
          <div key={name} className={styles.instRow}>
            <span>{name}</span>
            <div className={styles.instTrack} aria-hidden="true">
              <div className={styles.instZero} />
              <div
                className={`${styles.instBar} ${v >= 0 ? styles.barUp : styles.barDown}`}
                style={{ left: `${v >= 0 ? 50 : 50 - w}%`, width: `${Math.max(w, 0.5)}%` }}
              />
            </div>
            <span className={`num ${direction(v)}`}>{fmtWanLots(v)} 萬張</span>
          </div>
        )
      })}
    </div>
  )
}

function Skeleton() {
  return (
    <div className={styles.page} aria-busy="true" aria-label="載入中">
      <div className={styles.skel} style={{ height: 120 }} />
      <div className={styles.skel} style={{ height: 90 }} />
      <div className={styles.skel} style={{ height: 320 }} />
    </div>
  )
}
