import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useMemo, useState, type FormEvent } from 'react'
import { Link } from 'react-router'
import { PortfolioRisk } from '../components/PortfolioRisk'
import { portfolioApi, searchStocks, type HoldingIn } from '../lib/api'
import { direction, fmtFixed, fmtInt, fmtMonthDay, fmtPct, fmtPrice, fmtSigned } from '../lib/format'
import { taipeiToday } from '../lib/indicators'
import type { Mode } from '../lib/marketMode'
import { buildPositions, totals, type Holding, type Price } from '../lib/portfolio'
import { useLiveQuotes, type LiveStock } from '../lib/useLiveQuotes'
import styles from './PortfolioPage.module.css'

const money = (n: number) => fmtInt(Math.round(n))
const signedMoney = (n: number) => fmtSigned(Math.round(n))

export function PortfolioPage({ mode }: { mode: Mode }) {
  const q = useQuery({ queryKey: ['portfolio'], queryFn: portfolioApi.get, refetchInterval: 5 * 60_000 })
  const codes = useMemo(() => [...new Set((q.data?.holdings ?? []).map((h) => h.code))], [q.data])
  const { data: live } = useLiveQuotes(codes, codes.length > 0)
  const [editing, setEditing] = useState<Holding | null>(null)

  const positions = useMemo(() => {
    if (!q.data) return []
    const today = taipeiToday()
    const prices: Record<string, Price> = {}
    for (const c of codes) {
      const l = (live as Record<string, LiveStock>)[c]
      const r = q.data.quotes[c]
      if (l && l.time?.slice(0, 10) === today) prices[c] = { close: l.close, change: l.change, live: true }
      else if (r?.close != null && r.change != null) prices[c] = { close: r.close, change: r.change, live: false }
    }
    return buildPositions(q.data.holdings, q.data.quotes, prices)
  }, [q.data, live, codes])
  const t = totals(positions)
  // 持股（代號＋股數）變動才重算風險；沒有持股不顯示風險區
  const riskSignature = useMemo(() => {
    const agg: Record<string, number> = {}
    for (const h of q.data?.holdings ?? []) agg[h.code] = (agg[h.code] ?? 0) + h.shares
    return Object.entries(agg).sort().map(([c, s]) => `${c}:${s}`).join(',')
  }, [q.data])
  const lastDate = Object.values(q.data?.quotes ?? {}).map((r) => r.date).filter(Boolean).sort().pop()

  return (
    <div className={styles.page}>
      <header>
        <h1 className={styles.h1}>投資組合</h1>
        <p className={styles.muted}>
          手動輸入持股，損益以{mode === 'live' ? '即時成交價（未成交前用最近收盤）' : `最近收盤${lastDate ? `（${fmtMonthDay(lastDate)}）` : ''}`}計算。資料只存在你的 home server。
        </p>
      </header>

      {q.isError && <p className={styles.error}>{(q.error as Error).message}</p>}

      {positions.length > 0 && (
        <section className={styles.summary} aria-label="總覽">
          <Stat label="總市值" value={money(t.marketValue)} />
          <Stat label="總成本" value={money(t.costBasis)} />
          <Stat label="未實現損益" value={signedMoney(t.pnl)} sub={fmtPct(t.pnlPct)} dir={t.pnl} />
          <Stat label="今日損益" value={signedMoney(t.dayChange)} dir={t.dayChange} />
          <Stat label="扣除賣出費稅後" value={signedMoney(t.netPnl)} dir={t.netPnl} />
        </section>
      )}
      {t.missing > 0 && <p className={styles.muted}>有 {t.missing} 檔暫時沒有報價，未計入合計。</p>}

      <section className={styles.card} aria-labelledby="pos-h">
        <h2 id="pos-h" className={styles.h2}>持股</h2>
        {q.isPending ? (
          <div className={styles.skel} />
        ) : positions.length === 0 ? (
          <p className={styles.muted}>還沒有持股。用下方表單新增第一筆買進。</p>
        ) : (
          <div className={styles.tableBox}>
            <table className={styles.table}>
              <thead>
                <tr>
                  <th scope="col">股票</th>
                  <th scope="col">股數</th>
                  <th scope="col">平均成本</th>
                  <th scope="col">現價</th>
                  <th scope="col">市值</th>
                  <th scope="col">未實現損益</th>
                  <th scope="col">報酬率</th>
                  <th scope="col">今日損益</th>
                  <th scope="col">占比</th>
                </tr>
              </thead>
              <tbody>
                {positions.map((p) => (
                  <tr key={p.code}>
                    <td>
                      <Link to={`/stock/${p.code}`} className={styles.stock}>
                        <span className={`${styles.code} num`}>{p.code}</span>
                        {p.name}
                      </Link>
                    </td>
                    <td className="num">{fmtInt(p.shares)}</td>
                    <td className="num">{fmtFixed(p.avgCost, 2)}</td>
                    <td className="num">
                      {p.price !== null ? fmtPrice(p.price) : '—'}
                      {p.live && <span className={styles.live} title="即時成交價"> ●</span>}
                    </td>
                    <td className="num">{p.marketValue !== null ? money(p.marketValue) : '—'}</td>
                    <td className={`num ${p.pnl !== null ? direction(p.pnl) : ''}`}>{p.pnl !== null ? signedMoney(p.pnl) : '—'}</td>
                    <td className={`num ${p.pnlPct !== null ? direction(p.pnlPct) : ''}`}>{p.pnlPct !== null ? fmtPct(p.pnlPct) : '—'}</td>
                    <td className={`num ${p.dayChange !== null ? direction(p.dayChange) : ''}`}>{p.dayChange !== null ? signedMoney(p.dayChange) : '—'}</td>
                    <td className="num">{p.weight !== null ? `${fmtFixed(p.weight, 1)}%` : '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      {riskSignature && <PortfolioRisk signature={riskSignature} />}

      <div className={styles.cols}>
        <HoldingForm key={editing?.id ?? 'new'} editing={editing} onDone={() => setEditing(null)} />
        <Lots holdings={q.data?.holdings ?? []} names={Object.fromEntries(positions.map((p) => [p.code, p.name]))} onEdit={setEditing} editingId={editing?.id} />
      </div>

      <p className={styles.muted}>
        「扣除賣出費稅後」以手續費 0.1425%（未計券商折扣）加證交稅估算：股票 0.3%、ETF 0.1%、債券 ETF 停徵（至 2026 年底）。未計股利與已實現損益。本頁不構成投資建議。
      </p>
    </div>
  )
}

function Stat({ label, value, sub, dir }: { label: string; value: string; sub?: string; dir?: number }) {
  const cls = dir !== undefined ? direction(dir) : ''
  return (
    <div className={styles.stat}>
      <span className={styles.statLabel}>{label}</span>
      <span className={`num ${styles.statValue} ${cls}`}>{value}</span>
      {sub && <span className={`num ${cls}`}>{sub}</span>}
    </div>
  )
}

function HoldingForm({ editing, onDone }: { editing: Holding | null; onDone: () => void }) {
  const qc = useQueryClient()
  const [code, setCode] = useState(editing?.code ?? '')
  const [shares, setShares] = useState(editing ? String(editing.shares) : '')
  const [cost, setCost] = useState(editing ? String(editing.cost) : '')
  const [day, setDay] = useState(editing?.bought_on ?? '')
  const [note, setNote] = useState(editing?.note ?? '')
  const [msg, setMsg] = useState('')
  const sugg = useQuery({ queryKey: ['search', code], queryFn: () => searchStocks(code), enabled: !editing && code.trim().length >= 1, staleTime: 60_000 })
  const save = useMutation({
    mutationFn: async (h: HoldingIn) => (editing ? portfolioApi.update(editing.id, h) : portfolioApi.add(h)),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['portfolio'] })
      setMsg(editing ? '已更新' : '已新增')
      if (editing) onDone()
      else {
        setCode('')
        setShares('')
        setCost('')
        setNote('')
      }
    },
    onError: (e) => setMsg((e as Error).message),
  })

  async function submit(e: FormEvent) {
    e.preventDefault()
    setMsg('')
    let c = code.trim().split(/\s+/)[0]
    if (!editing) {
      const hits = c ? await searchStocks(c) : []
      if (!hits.length) return setMsg(`找不到「${c}」`)
      c = hits[0].code
    }
    const n = Number(shares)
    const p = Number(cost)
    if (!Number.isInteger(n) || n <= 0) return setMsg('股數要是正整數（1 張 = 1,000 股）')
    if (!(p > 0)) return setMsg('每股成本要大於 0')
    save.mutate({ code: c, shares: n, cost: p, bought_on: day || null, note })
  }

  return (
    <section className={styles.card} aria-labelledby="form-h">
      <h2 id="form-h" className={styles.h2}>{editing ? `編輯 ${editing.code} 的買進紀錄` : '新增買進'}</h2>
      <form className={styles.form} onSubmit={submit}>
        <label className={styles.field}>
          <span>股票</span>
          <input list="pf-sugg" className={styles.input} value={code} onChange={(e) => setCode(e.target.value)} placeholder="代號或名稱" autoComplete="off" disabled={!!editing} required />
        </label>
        <datalist id="pf-sugg">
          {(sugg.data ?? []).map((s) => (
            <option key={s.code} value={`${s.code} ${s.name}`} />
          ))}
        </datalist>
        <label className={styles.field}>
          <span>股數</span>
          <input className={styles.input} inputMode="numeric" value={shares} onChange={(e) => setShares(e.target.value)} placeholder="1 張 = 1000" required />
        </label>
        <label className={styles.field}>
          <span>每股成本（元）</span>
          <input className={styles.input} inputMode="decimal" value={cost} onChange={(e) => setCost(e.target.value)} placeholder="含手續費更準" required />
        </label>
        <label className={styles.field}>
          <span>買進日期（選填）</span>
          <input className={styles.input} type="date" value={day} max={taipeiToday()} onChange={(e) => setDay(e.target.value)} />
        </label>
        <label className={styles.field}>
          <span>備註（選填）</span>
          <input className={styles.input} value={note} maxLength={100} onChange={(e) => setNote(e.target.value)} />
        </label>
        <div className={styles.actions}>
          <button className={styles.primary} type="submit" disabled={save.isPending}>
            {editing ? '儲存' : '新增'}
          </button>
          {editing && (
            <button className={styles.secondary} type="button" onClick={onDone}>
              取消
            </button>
          )}
          {msg && (
            <span className={styles.muted} role="status">
              {msg}
            </span>
          )}
        </div>
      </form>
    </section>
  )
}

function Lots({ holdings, names, onEdit, editingId }: { holdings: Holding[]; names: Record<string, string>; onEdit: (h: Holding) => void; editingId?: number }) {
  const qc = useQueryClient()
  const del = useMutation({ mutationFn: portfolioApi.remove, onSuccess: () => qc.invalidateQueries({ queryKey: ['portfolio'] }) })
  return (
    <section className={styles.card} aria-labelledby="lots-h">
      <h2 id="lots-h" className={styles.h2}>買進紀錄</h2>
      {holdings.length === 0 ? (
        <p className={styles.muted}>尚無紀錄。</p>
      ) : (
        <div className={styles.tableBox}>
          <table className={styles.table}>
            <thead>
              <tr>
                <th scope="col">股票</th>
                <th scope="col">股數</th>
                <th scope="col">成本</th>
                <th scope="col">日期</th>
                <th scope="col">備註</th>
                <th scope="col">
                  <span className="sr-only">操作</span>
                </th>
              </tr>
            </thead>
            <tbody>
              {holdings.map((h) => (
                <tr key={h.id} className={h.id === editingId ? styles.editing : ''}>
                  <td>
                    <span className={`${styles.code} num`}>{h.code}</span>
                    {names[h.code] ?? ''}
                  </td>
                  <td className="num">{fmtInt(h.shares)}</td>
                  <td className="num">{fmtFixed(h.cost, 2)}</td>
                  <td className="num">{h.bought_on ?? '—'}</td>
                  <td className={styles.note}>{h.note}</td>
                  <td className={styles.ops}>
                    <button type="button" className={styles.icon} onClick={() => onEdit(h)} aria-label={`編輯 ${h.code} 這筆紀錄`}>
                      ✎
                    </button>
                    <button
                      type="button"
                      className={styles.icon}
                      onClick={() => window.confirm(`刪除 ${h.code} ${fmtInt(h.shares)} 股這筆紀錄？`) && del.mutate(h.id)}
                      aria-label={`刪除 ${h.code} 這筆紀錄`}
                    >
                      ✕
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {del.isError && <p className={styles.error}>{(del.error as Error).message}</p>}
    </section>
  )
}
