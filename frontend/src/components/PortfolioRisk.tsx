import { useQuery } from '@tanstack/react-query'
import { portfolioApi, type PortfolioRisk as Risk } from '../lib/api'
import { direction, fmtFixed, fmtInt, fmtMonthDay, fmtPct } from '../lib/format'
import { Sparkline } from './Sparkline'
import styles from './PortfolioRisk.module.css'

const pct = (n: number | null | undefined, digits = 2) => (n == null ? '—' : `${fmtFixed(n, digits)}%`)

function Metric({ label, value, sub, dir }: { label: string; value: string; sub?: string; dir?: number }) {
  return (
    <div className={styles.metric}>
      <div className={styles.label}>{label}</div>
      <div className={`num ${styles.value} ${dir != null ? direction(dir) : ''}`}>{value}</div>
      {sub && <div className={styles.sub}>{sub}</div>}
    </div>
  )
}

/** 相關係數上色：正相關用強調色、負相關用跌色，深淺依絕對值。 */
function cellStyle(v: number | null): React.CSSProperties {
  if (v == null) return {}
  const c = v >= 0 ? 'var(--accent)' : 'var(--down)'
  return { background: `color-mix(in srgb, ${c} ${Math.round(Math.abs(v) * 35)}%, transparent)` }
}

/** signature：持股（代號與股數）變動時重抓。 */
export function PortfolioRisk({ signature }: { signature: string }) {
  const q = useQuery({ queryKey: ['portfolio-risk', signature], queryFn: portfolioApi.risk, staleTime: 30 * 60_000, retry: 1 })

  return (
    <section className={styles.card} aria-labelledby="risk-h">
      <div className={styles.head}>
        <h2 id="risk-h" className={styles.h2}>風險分析</h2>
        {q.data?.status === 'ok' && (
          <span className={styles.muted}>
            {q.data.start} ～ {q.data.end}・{q.data.days} 個交易日
          </span>
        )}
      </div>
      {q.isPending && <div className={styles.skel} aria-busy="true" aria-label="計算風險指標中" />}
      {q.isError && <p className={styles.muted}>目前無法計算風險指標：{(q.error as Error).message}</p>}
      {q.data && <Body d={q.data} />}
    </section>
  )
}

function Body({ d }: { d: Risk }) {
  const a = d.assumptions
  const excluded = d.excluded.length > 0 && (
    <p className={styles.muted}>
      未納入計算：{d.excluded.map((e) => `${e.name}（${e.code}，${e.reason}）`).join('、')}
    </p>
  )
  if (d.status === 'empty') return <p className={styles.muted}>先在下方新增持股，才能計算風險。</p>
  if (d.status === 'insufficient' || !d.metrics || !d.holdings) {
    return (
      <>
        <p className={styles.muted}>持股的歷史資料不足 120 個交易日，暫時無法計算。</p>
        {excluded}
      </>
    )
  }
  const m = d.metrics
  const values = (d.series ?? []).map((s) => s.value)

  return (
    <>
      <p className={styles.note}>
        試算假設：過去一年都持有<strong>目前的股數</strong>、不再平衡，價格用{a.price_basis}。這不是你的實際績效，只用來看這組持股的風險輪廓。
      </p>

      <div className={styles.metrics}>
        <Metric label="年化報酬（試算）" value={fmtPct(m.annual_return_pct)} dir={m.annual_return_pct} />
        <Metric label="年化波動度" value={pct(m.annual_vol_pct)} sub="一年大約上下震盪的幅度" />
        <Metric label="最大回撤" value={pct(m.max_drawdown.pct)} sub={`${fmtMonthDay(m.max_drawdown.peak_date)} 高點 → ${fmtMonthDay(m.max_drawdown.trough_date)}`} />
        <Metric label="Sharpe 比率" value={m.sharpe == null ? '—' : fmtFixed(m.sharpe, 2)} sub={`無風險利率假設 ${fmtFixed(a.risk_free_pct, 1)}%`} />
        <Metric
          label={`單日 VaR（${fmtFixed(a.var_level_pct, 0)}%）`}
          value={pct(m.var_1d_pct)}
          sub={`約 ${fmtInt(m.var_1d_amount)} 元；約每 20 個交易日有 1 天虧損超過此數`}
        />
        <Metric label="Beta（對加權指數）" value={m.beta == null ? '—' : fmtFixed(m.beta, 2)} sub="大盤漲跌 1%，組合約漲跌幾 %" />
      </div>

      {values.length > 1 && (
        <div className={styles.spark}>
          <Sparkline values={values} width={640} height={64} label="組合試算淨值" period="近一年" />
          <span className={styles.muted}>組合試算淨值（{d.start} ～ {d.end}）</span>
        </div>
      )}

      <div className={styles.tableBox}>
        <table className={styles.table}>
          <caption className={styles.caption}>各檔權重與風險貢獻（風險貢獻加總為 100%，負值代表有降低整體波動的效果）</caption>
          <thead>
            <tr>
              <th scope="col">股票</th>
              <th scope="col">產業</th>
              <th scope="col">市值權重</th>
              <th scope="col">風險貢獻</th>
              <th scope="col">個股年化波動</th>
            </tr>
          </thead>
          <tbody>
            {d.holdings.map((h) => (
              <tr key={h.code}>
                <th scope="row">
                  {h.name} <span className={styles.code}>{h.code}</span>
                </th>
                <td>{h.industry ?? '—'}</td>
                <td className="num">
                  <Bar pct={h.weight_pct} />
                  {pct(h.weight_pct, 1)}
                </td>
                <td className={`num ${h.risk_pct > h.weight_pct + 5 ? styles.hot : ''}`}>
                  <Bar pct={Math.max(h.risk_pct, 0)} />
                  {pct(h.risk_pct, 1)}
                </td>
                <td className="num">{pct(h.vol_pct, 1)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {d.top_weight_pct != null && d.top_weight_pct >= 40 && (
        <p className={styles.muted}>最大一檔占市值 {fmtFixed(d.top_weight_pct, 1)}%，組合風險高度集中在這一檔。</p>
      )}

      <div className={styles.split}>
        {d.industries && d.industries.length > 0 && (
          <div>
            <h3 className={styles.h3}>產業集中度</h3>
            <ul className={styles.industries}>
              {d.industries.map((r) => (
                <li key={r.industry}>
                  <span>{r.industry}</span>
                  <Bar pct={r.weight_pct} />
                  <span className="num">{pct(r.weight_pct, 1)}</span>
                </li>
              ))}
            </ul>
          </div>
        )}

        {d.correlation && (
          <div className={styles.tableBox}>
            <h3 className={styles.h3}>持股相關性（日報酬）</h3>
            <table className={styles.corr}>
              <thead>
                <tr>
                  <th scope="col" />
                  {d.correlation.codes.map((c) => (
                    <th key={c} scope="col" className="num">
                      {c}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {d.correlation.matrix.map((row, i) => (
                  <tr key={d.correlation!.codes[i]}>
                    <th scope="row">{d.correlation!.names[i]}</th>
                    {row.map((v, j) => (
                      <td key={j} className="num" style={i === j ? undefined : cellStyle(v)}>
                        {v == null ? '—' : fmtFixed(v, 2)}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
            <p className={styles.muted}>1 代表同漲同跌、0 代表無關、負值代表反向。數字愈接近 1，分散效果愈差。</p>
          </div>
        )}
      </div>

      {excluded}
      {d.excluded_jumps > 0 && (
        <p className={styles.muted}>有 {d.excluded_jumps} 個交易日的單日漲跌超過 10.5%（可能是分割或減資未調整），當日以 0 計算。</p>
      )}
      <p className={styles.muted}>
        資料：FinMind（日 K、除權息、加權指數）。年化以 {a.annualization_days} 個交易日計；基準為{a.benchmark}。本區為歷史統計，不代表未來，也不構成投資建議。
      </p>
    </>
  )
}

function Bar({ pct }: { pct: number }) {
  return (
    <span className={styles.bar} aria-hidden="true">
      <span style={{ width: `${Math.min(Math.max(pct, 0), 100)}%` }} />
    </span>
  )
}
