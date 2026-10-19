import { useQuery } from '@tanstack/react-query'
import { direction, fmtFixed, fmtInt, fmtPct } from '../lib/format'
import styles from './GlobalFundamentals.module.css'

export interface GlobalFund {
  symbol: string
  name: string
  quote_type: string | null
  currency: string | null
  financial_currency: string | null
  has_data: boolean
  profile: { sector: string | null; industry: string | null; country: string | null; employees: number | null; website: string | null; summary: string | null }
  valuation: { market_cap: number | null; trailing_pe: number | null; forward_pe: number | null; pb: number | null; ps: number | null; peg: number | null; eps_ttm: number | null; eps_forward: number | null; beta: number | null }
  dividend: { rate: number | null; yield_pct: number | null; payout_pct: number | null; five_year_avg_yield_pct: number | null; ex_date: string | null }
  profitability: { gross_margin: number | null; operating_margin: number | null; profit_margin: number | null; roe: number | null; roa: number | null; revenue_growth: number | null; earnings_growth: number | null }
  health: { total_revenue: number | null; total_cash: number | null; total_debt: number | null; free_cashflow: number | null; debt_to_equity: number | null; current_ratio: number | null }
  analyst: { target_mean: number | null; target_high: number | null; target_low: number | null; count: number | null; rating_score: number | null; rating_label: string | null }
  quarters: { quarter: string; revenue: number | null; net_income: number | null; net_margin: number | null; eps: number | null; eps_estimate: number | null; surprise_pct: number | null }[]
  next_earnings: string | null
}

async function getJson<T>(url: string): Promise<T> {
  const r = await fetch(url)
  if (!r.ok) {
    const body = await r.json().catch(() => null)
    throw new Error(body?.detail ?? `HTTP ${r.status}`)
  }
  return r.json() as Promise<T>
}

const dash = '—'

/** 原幣大金額：≥1 兆顯示「兆」，否則「億」。 */
function fmtBig(n: number | null): string {
  if (n == null) return dash
  const a = Math.abs(n)
  if (a >= 1e12) return `${fmtFixed(n / 1e12, 2)} 兆`
  if (a >= 1e8) return `${fmtFixed(n / 1e8, a >= 1e10 ? 0 : 1)} 億`
  return fmtInt(Math.round(n))
}

const num = (n: number | null, digits = 2, unit = '') => (n == null ? dash : `${fmtFixed(n, digits)}${unit}`)
const pctPlain = (n: number | null, digits = 2) => (n == null ? dash : `${fmtFixed(n, digits)}%`)
const pctSigned = (n: number | null) => (n == null ? dash : fmtPct(n))

function Stat({ label, value, tone }: { label: string; value: string; tone?: string }) {
  return (
    <div className={styles.stat}>
      <div className={styles.label}>{label}</div>
      <div className={`num ${styles.value} ${tone ?? ''}`}>{value}</div>
    </div>
  )
}

export function GlobalFundamentals({ symbol, lastClose }: { symbol: string; lastClose?: number }) {
  const q = useQuery({
    queryKey: ['gfund', symbol],
    queryFn: () => getJson<GlobalFund>(`/api/global/fundamentals?symbol=${encodeURIComponent(symbol)}`),
    retry: false,
    staleTime: 60 * 60_000,
  })

  if (q.isPending) return <div className={styles.skel} aria-busy="true" aria-label="載入基本面資料中" />
  if (q.isError) return <p className={styles.muted}>目前無法取得基本面資料：{(q.error as Error).message}</p>
  const d = q.data
  if (!d.has_data) return <p className={styles.muted}>{symbol} 是指數、期貨或匯率等商品，沒有公司基本面資料。</p>

  const v = d.valuation
  const p = d.profitability
  const a = d.analyst
  const upside = a.target_mean != null && lastClose ? ((a.target_mean - lastClose) / lastClose) * 100 : null
  const finCur = d.financial_currency ?? d.currency ?? ''
  const curNote = d.financial_currency && d.currency && d.financial_currency !== d.currency
    ? `報價幣別 ${d.currency}、財報幣別 ${d.financial_currency}`
    : `幣別 ${d.currency ?? '—'}`

  return (
    <div className={styles.wrap}>
      <div className={styles.head}>
        <h3 className={styles.h3}>基本面</h3>
        <span className={styles.muted}>
          {[d.profile.sector, d.profile.industry].filter(Boolean).join(' · ')}
          {d.profile.sector ? ' · ' : ''}
          {curNote}
        </span>
      </div>

      <div className={styles.grid}>
        <Stat label="市值" value={`${fmtBig(v.market_cap)}${v.market_cap != null ? ` ${d.currency ?? ''}` : ''}`} />
        <Stat label="本益比（近四季）" value={num(v.trailing_pe, 1, ' 倍')} />
        <Stat label="預估本益比" value={num(v.forward_pe, 1, ' 倍')} />
        <Stat label="股價淨值比" value={num(v.pb, 2, ' 倍')} />
        <Stat label="EPS（近四季）" value={num(v.eps_ttm)} />
        <Stat label="殖利率" value={pctPlain(d.dividend.yield_pct)} />
        <Stat label="毛利率" value={pctPlain(p.gross_margin, 1)} />
        <Stat label="營業利益率" value={pctPlain(p.operating_margin, 1)} />
        <Stat label="淨利率" value={pctPlain(p.profit_margin, 1)} />
        <Stat label="ROE" value={pctPlain(p.roe, 1)} />
        <Stat label="營收年增" value={pctSigned(p.revenue_growth)} tone={p.revenue_growth != null ? direction(p.revenue_growth) : ''} />
        <Stat label="負債／權益" value={d.health.debt_to_equity != null ? `${fmtFixed(d.health.debt_to_equity, 1)}%` : dash} />
      </div>

      {(a.rating_label || a.target_mean != null) && (
        <div className={styles.analyst}>
          <span>
            分析師共識 <strong>{a.rating_label ?? dash}</strong>
            {a.rating_score != null && <span className={styles.muted}>（{fmtFixed(a.rating_score, 2)}，1 為強力買進、5 為賣出）</span>}
          </span>
          {a.target_mean != null && (
            <span className="num">
              目標價均值 <strong>{fmtFixed(a.target_mean)}</strong>
              {upside != null && <span className={direction(upside)}>（距現價 {fmtPct(upside)}）</span>}
              {a.target_low != null && a.target_high != null && (
                <span className={styles.muted}>
                  {' '}區間 {fmtFixed(a.target_low)}–{fmtFixed(a.target_high)}
                </span>
              )}
            </span>
          )}
          {a.count != null && <span className={styles.muted}>{a.count} 位分析師</span>}
          {d.next_earnings && <span className={styles.muted}>下次財報 {d.next_earnings}</span>}
          {d.dividend.ex_date && <span className={styles.muted}>最近除息 {d.dividend.ex_date}</span>}
        </div>
      )}

      {d.quarters.length > 0 && (
        <div className={styles.tableBox}>
          <table className={styles.table}>
            <caption className={styles.caption}>近四季財報（金額單位：{finCur}）</caption>
            <thead>
              <tr>
                <th scope="col">季別</th>
                <th scope="col">營收</th>
                <th scope="col">淨利</th>
                <th scope="col">淨利率</th>
                <th scope="col">EPS</th>
                <th scope="col">預估 EPS</th>
                <th scope="col">優於預期</th>
              </tr>
            </thead>
            <tbody>
              {[...d.quarters].reverse().map((r) => (
                <tr key={r.quarter}>
                  <th scope="row">{r.quarter}</th>
                  <td className="num">{fmtBig(r.revenue)}</td>
                  <td className="num">{fmtBig(r.net_income)}</td>
                  <td className="num">{pctPlain(r.net_margin, 1)}</td>
                  <td className="num">{num(r.eps, 2)}</td>
                  <td className="num">{num(r.eps_estimate, 2)}</td>
                  <td className={`num ${r.surprise_pct != null ? direction(r.surprise_pct) : ''}`}>{pctSigned(r.surprise_pct)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {d.profile.summary && (
        <details className={styles.about}>
          <summary>公司簡介（英文原文）</summary>
          <p>{d.profile.summary}</p>
          <p className={styles.muted}>
            {[d.profile.country, d.profile.employees != null ? `員工 ${fmtInt(d.profile.employees)} 人` : null].filter(Boolean).join(' · ')}
            {d.profile.website && (
              <>
                {' · '}
                <a href={d.profile.website} target="_blank" rel="noreferrer noopener">
                  官網
                </a>
              </>
            )}
          </p>
        </details>
      )}

      <p className={styles.muted}>資料：Yahoo Finance（每 6 小時更新）。本區不構成投資建議。</p>
    </div>
  )
}
