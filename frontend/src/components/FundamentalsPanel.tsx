import { useState } from 'react'
import { Link } from 'react-router'
import { niceScale } from '../lib/chartScale'
import { arrow, direction, fmtFixed, fmtInt, fmtPct, fmtPrice, fmtSigned, fmtYi } from '../lib/format'
import {
  useFundamentals,
  type BalanceQuarter,
  type DividendYear,
  type IncomeQuarter,
  type PeersData,
  type PeRiver,
} from '../lib/fundamentals'
import styles from './FundamentalsPanel.module.css'

/** 個股基本面（預設收合，展開才向後端請求）：季損益、本益比河流圖、資產負債、股利政策、同業比較。 */
export function FundamentalsPanel({ code }: { code: string }) {
  const [open, setOpen] = useState(false)
  const q = useFundamentals(code, open)

  return (
    <section aria-labelledby="fund-h" className={styles.wrap}>
      <button
        type="button"
        id="fund-h"
        className={styles.toggleBtn}
        aria-expanded={open}
        onClick={() => setOpen((v) => !v)}
      >
        <span>財務基本面 · 季損益、資產負債、股利政策、本益比河流圖、同業比較</span>
        <span className={styles.toggleMeta}>{open ? '▲ 收合' : '▼ 展開載入'}</span>
      </button>

      {open && (
        <div className={styles.body}>
          {q.isPending && <div className={styles.skel} aria-busy="true" aria-label="載入基本面資料中" />}
          {q.isError && <p className={styles.muted}>目前無法取得基本面資料：{(q.error as Error).message}</p>}
          {q.data && (
            <>
              <div className={styles.block}>
                <div className={styles.head}>
                  <h3 className={styles.h3}>單季損益與三率</h3>
                  <span className={`${styles.sub} num`}>
                    {q.data.eps_ttm != null ? `近四季合計 EPS ${fmtFixed(q.data.eps_ttm)} 元 · ` : ''}金額單位：億元
                  </span>
                </div>
                <IncomeTable rows={q.data.income} />
              </div>

              <div className={styles.grid2}>
                <div className={styles.block}>
                  <div className={styles.head}>
                    <h3 className={styles.h3}>本益比河流圖</h3>
                    <span className={`${styles.sub} num`}>
                      {q.data.river ? `${q.data.river.start} ～ ${q.data.river.end} · 目前 ${fmtFixed(q.data.river.current_pe)} 倍` : '近五年'}
                    </span>
                  </div>
                  <RiverChart river={q.data.river} />
                </div>

                <div className={styles.block}>
                  <div className={styles.head}>
                    <h3 className={styles.h3}>資產負債與結構</h3>
                    <span className={styles.sub}>金額單位：億元</span>
                  </div>
                  <BalanceTable rows={q.data.balance} />
                </div>
              </div>

              <div className={styles.grid2}>
                <div className={styles.block}>
                  <div className={styles.head}>
                    <h3 className={styles.h3}>歷年股利政策（依所屬年度）</h3>
                    <span className={styles.sub}>單位：元／股（季配息合併計算）</span>
                  </div>
                  <DividendTable rows={q.data.dividends} />
                </div>

                <div className={styles.block}>
                  <div className={styles.head}>
                    <h3 className={styles.h3}>
                      同業比較{q.data.peers ? ` · ${q.data.peers.industry}` : ''}
                    </h3>
                    <span className={`${styles.sub} num`}>
                      {q.data.peers
                        ? `上市同業 ${q.data.peers.count} 檔${q.data.peers.median_pe != null ? ` · 本益比中位數 ${fmtFixed(q.data.peers.median_pe)} 倍` : ''} · ${q.data.peers.asof}`
                        : '依選股總表同產業成交值排序'}
                    </span>
                  </div>
                  <PeersTable peers={q.data.peers} currentCode={code} />
                </div>
              </div>

              <p className={styles.muted}>基本面資料來源：{q.data.sources.join('、')}。</p>
            </>
          )}
        </div>
      )}
    </section>
  )
}

function IncomeTable({ rows }: { rows: IncomeQuarter[] }) {
  if (!rows.length) return <p className={styles.muted}>無損益表資料（可能為 ETF 或新掛牌）。</p>
  return (
    <div className={styles.tableBox}>
      <table className={styles.table}>
        <thead>
          <tr>
            <th scope="col">季度</th>
            <th scope="col">營收（億）</th>
            <th scope="col">營收年增</th>
            <th scope="col">毛利率</th>
            <th scope="col">營益率</th>
            <th scope="col">稅後淨利（億）</th>
            <th scope="col">淨利率</th>
            <th scope="col">單季 EPS</th>
          </tr>
        </thead>
        <tbody>
          {[...rows].reverse().map((r) => (
            <tr key={r.date}>
              <td className="num">{r.quarter}</td>
              <td className="num">{r.revenue != null ? fmtYi(r.revenue, 1) : '—'}</td>
              <td className={`num ${r.revenue_yoy != null ? direction(r.revenue_yoy) : ''}`}>
                {r.revenue_yoy != null ? fmtPct(r.revenue_yoy) : '—'}
              </td>
              <td className="num">{r.gross_margin != null ? `${fmtFixed(r.gross_margin)}%` : '—'}</td>
              <td className="num">{r.operating_margin != null ? `${fmtFixed(r.operating_margin)}%` : '—'}</td>
              <td className="num">{r.net_income != null ? fmtYi(r.net_income, 1) : '—'}</td>
              <td className="num">{r.net_margin != null ? `${fmtFixed(r.net_margin)}%` : '—'}</td>
              <td className={`num ${r.eps != null ? direction(r.eps) : ''}`}>
                {r.eps != null ? fmtFixed(r.eps) : '—'}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function BalanceTable({ rows }: { rows: BalanceQuarter[] }) {
  if (!rows.length) return <p className={styles.muted}>無資產負債表資料。</p>
  return (
    <div className={styles.tableBox}>
      <table className={styles.table}>
        <thead>
          <tr>
            <th scope="col">季度</th>
            <th scope="col">總資產</th>
            <th scope="col">總負債</th>
            <th scope="col">負債比</th>
            <th scope="col">流動比</th>
            <th scope="col">每股淨值</th>
          </tr>
        </thead>
        <tbody>
          {[...rows].reverse().map((r) => (
            <tr key={r.date}>
              <td className="num">{r.quarter}</td>
              <td className="num">{r.total_assets != null ? fmtYi(r.total_assets, 0) : '—'}</td>
              <td className="num">{r.liabilities != null ? fmtYi(r.liabilities, 0) : '—'}</td>
              <td className="num">{r.debt_ratio != null ? `${fmtFixed(r.debt_ratio)}%` : '—'}</td>
              <td className="num">{r.current_ratio != null ? `${fmtFixed(r.current_ratio, 0)}%` : '—'}</td>
              <td className="num">{r.book_value_per_share != null ? fmtFixed(r.book_value_per_share) : '—'}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function DividendTable({ rows }: { rows: DividendYear[] }) {
  if (!rows.length) return <p className={styles.muted}>無股利紀錄。</p>
  return (
    <div className={styles.tableBox}>
      <table className={styles.table}>
        <thead>
          <tr>
            <th scope="col">所屬年度</th>
            <th scope="col">現金股利</th>
            <th scope="col">股票股利</th>
            <th scope="col">合計</th>
            <th scope="col">配息次數</th>
            <th scope="col">當年 EPS</th>
            <th scope="col">現金配發率</th>
          </tr>
        </thead>
        <tbody>
          {[...rows].reverse().map((r) => (
            <tr key={r.year}>
              <td className="num">{r.year}</td>
              <td className="num">{fmtFixed(r.cash)}</td>
              <td className="num">{r.stock ? fmtFixed(r.stock) : '—'}</td>
              <td className="num">{fmtFixed(r.cash + r.stock)}</td>
              <td className="num">{r.times}</td>
              <td className="num">{r.eps != null ? fmtFixed(r.eps) : '—'}</td>
              <td className="num">{r.payout != null ? `${fmtFixed(r.payout, 1)}%` : '—'}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

const W = 720
const H = 220

function RiverChart({ river }: { river: PeRiver | null }) {
  if (!river || river.series.length < 2) {
    return <p className={styles.muted}>歷史本益比資料不足（可能為虧損或掛牌未滿一季）。</p>
  }
  const s = river.series
  const allVals = s.flatMap((p) => [p.close, ...p.bands])
  const scale = niceScale(allVals)
  const y = (v: number) => H - ((v - scale.min) / (scale.max - scale.min || 1)) * H
  const x = (i: number) => (i / (s.length - 1)) * W
  const pathOf = (pick: (p: PeRiver['series'][number]) => number) =>
    s.map((p, i) => `${i ? 'L' : 'M'}${x(i).toFixed(1)},${y(pick(p)).toFixed(1)}`).join(' ')
  const areaBetween = (loIdx: number, hiIdx: number) => {
    const top = s.map((p, i) => `${i ? 'L' : 'M'}${x(i).toFixed(1)},${y(p.bands[hiIdx]).toFixed(1)}`).join(' ')
    const bot = [...s]
      .reverse()
      .map((p, ri) => {
        const i = s.length - 1 - ri
        return `L${x(i).toFixed(1)},${y(p.bands[loIdx]).toFixed(1)}`
      })
      .join(' ')
    return `${top} ${bot} Z`
  }

  return (
    <div>
      <div className={styles.riverPlot}>
        {scale.ticks.map((t) => (
          <div key={t} className={styles.gridLine} style={{ top: `${(y(t) / H) * 100}%` }}>
            <span className={`${styles.tick} num`}>{fmtInt(t)}</span>
          </div>
        ))}
        <svg
          viewBox={`0 0 ${W} ${H}`}
          preserveAspectRatio="none"
          className={styles.svg}
          role="img"
          aria-label={`本益比河流圖，${river.start} 至 ${river.end}，P10 至 P90 倍數 ${river.multiples.join(' / ')}`}
        >
          <path d={areaBetween(0, 4)} className={styles.bandOuter} />
          <path d={areaBetween(1, 3)} className={styles.bandInner} />
          {[0, 1, 3, 4].map((idx) => (
            <path key={idx} d={pathOf((p) => p.bands[idx])} className={styles.bandLine} vectorEffect="non-scaling-stroke" />
          ))}
          <path d={pathOf((p) => p.bands[2])} className={styles.midLine} vectorEffect="non-scaling-stroke" />
          <path d={pathOf((p) => p.close)} className={styles.closeLine} vectorEffect="non-scaling-stroke" />
        </svg>
      </div>
      <div className={`${styles.legendRow} num`}>
        <span>實線：收盤價 · 虛線：中位數本益比（{fmtFixed(river.multiples[2])}x）</span>
        <div className={styles.bandsList}>
          {river.percentiles.map((pct, i) => (
            <span key={pct}>
              P{pct} {fmtFixed(river.multiples[i])}x
            </span>
          ))}
        </div>
      </div>
    </div>
  )
}

function PeersTable({ peers, currentCode }: { peers: PeersData | null; currentCode: string }) {
  if (!peers || !peers.rows.length) {
    return <p className={styles.muted}>暫無同業比較資料（上櫃或選股總表尚未包含此類別）。</p>
  }
  return (
    <div className={styles.tableBox}>
      <table className={styles.table}>
        <thead>
          <tr>
            <th scope="col">股票</th>
            <th scope="col">收盤</th>
            <th scope="col">漲跌</th>
            <th scope="col">本益比</th>
            <th scope="col">股淨比</th>
            <th scope="col">殖利率</th>
            <th scope="col">外資連買賣</th>
            <th scope="col">成交（億）</th>
          </tr>
        </thead>
        <tbody>
          {peers.rows.map((r) => {
            const pct = r.change_pct ?? 0
            const streak = r.foreign_streak ?? 0
            return (
              <tr key={r.code} className={r.code === currentCode ? styles.selfRow : ''}>
                <td>
                  <Link to={`/stock/${r.code}`} className={styles.stockLink}>
                    <span className={`${styles.code} num`}>{r.code}</span>
                    {r.name}
                  </Link>
                </td>
                <td className="num">{r.close != null ? fmtPrice(r.close) : '—'}</td>
                <td className={`num ${direction(pct)}`}>
                  {r.change_pct != null ? `${arrow(pct)} ${fmtPct(pct)}` : '—'}
                </td>
                <td className="num">{r.pe != null ? fmtFixed(r.pe) : '—'}</td>
                <td className="num">{r.pb != null ? fmtFixed(r.pb) : '—'}</td>
                <td className="num">{r.dividend_yield != null ? `${fmtFixed(r.dividend_yield)}%` : '—'}</td>
                <td className={`num ${direction(streak)}`}>{streak ? `${fmtSigned(streak)} 日` : '—'}</td>
                <td className="num">{r.value_e8 != null ? fmtFixed(r.value_e8, 1) : '—'}</td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}
