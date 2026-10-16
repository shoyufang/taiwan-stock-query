import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useMemo, useState } from 'react'
import { Link } from 'react-router'
import { watchlistApi } from '../lib/api'
import { direction, fmtDateLong, fmtFixed, fmtPct, fmtPrice, fmtSigned } from '../lib/format'
import { applyFilters, PRESETS, sortRows, type Filters, type ScreenRow, type SortKey } from '../lib/screener'
import { addCode } from '../lib/watchlistOps'
import styles from './ScreenerPage.module.css'

interface Base {
  asof: string
  generated_at: string
  days: number
  rows: ScreenRow[]
  sources: string[]
}

async function fetchBase(): Promise<Base> {
  const r = await fetch('/api/screener/base')
  if (!r.ok) throw new Error(r.status === 503 ? '選股資料準備中' : `API ${r.status}`)
  return r.json()
}

const FIELDS: { key: keyof Filters; label: string; unit: string }[] = [
  { key: 'priceMin', label: '股價 ≥', unit: '元' },
  { key: 'priceMax', label: '股價 ≤', unit: '元' },
  { key: 'pctMin', label: '漲跌幅 ≥', unit: '%' },
  { key: 'valueMin', label: '成交值 ≥', unit: '億' },
  { key: 'peMax', label: '本益比 ≤', unit: '倍' },
  { key: 'yieldMin', label: '殖利率 ≥', unit: '%' },
  { key: 'pbMax', label: '股淨比 ≤', unit: '倍' },
  { key: 'foreignMin', label: '外資買超 ≥', unit: '張' },
  { key: 'trustMin', label: '投信買超 ≥', unit: '張' },
  { key: 'foreignStreakMin', label: '外資連買 ≥', unit: '天' },
  { key: 'trustStreakMin', label: '投信連買 ≥', unit: '天' },
]

const COLS: { key: SortKey; label: string }[] = [
  { key: 'close', label: '收盤' },
  { key: 'change_pct', label: '漲跌幅' },
  { key: 'value_e8', label: '成交值（億）' },
  { key: 'pe', label: '本益比' },
  { key: 'dividend_yield', label: '殖利率%' },
  { key: 'pb', label: '股淨比' },
  { key: 'foreign', label: '外資（張）' },
  { key: 'trust', label: '投信（張）' },
  { key: 'foreign_streak', label: '外資連續' },
  { key: 'trust_streak', label: '投信連續' },
]

const PAGE = 100

export function ScreenerPage() {
  const q = useQuery({ queryKey: ['screener'], queryFn: fetchBase, staleTime: 5 * 60_000, retry: 3, retryDelay: 5000 })
  const [preset, setPreset] = useState<string>('dual')
  const [custom, setCustom] = useState<Filters>({})
  const [sort, setSort] = useState<{ key: SortKey; desc: boolean }>({ key: 'value_e8', desc: true })
  const [limit, setLimit] = useState(PAGE)

  const filters: Filters = { ...(PRESETS.find((p) => p.key === preset)?.filters ?? {}), ...custom }
  const rows = useMemo(() => (q.data ? sortRows(applyFilters(q.data.rows, filters), sort.key, sort.desc) : []), [q.data, JSON.stringify(filters), sort])
  const industries = useMemo(() => [...new Set((q.data?.rows ?? []).map((r) => r.industry).filter(Boolean))].sort(), [q.data])

  const qc = useQueryClient()
  const wl = useQuery({ queryKey: ['watchlist'], queryFn: watchlistApi.get })
  const addWl = useMutation({
    mutationFn: (code: string) => watchlistApi.put(addCode(wl.data?.codes ?? [], code)),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['watchlist'] }),
  })

  const setNum = (key: keyof Filters, v: string) =>
    setCustom((c) => {
      const next = { ...c }
      if (v.trim() === '' || Number.isNaN(Number(v))) delete next[key]
      else (next as Record<string, number>)[key] = Number(v)
      return next
    })

  return (
    <div className={styles.page}>
      <header>
        <h1 className={styles.h1}>選股</h1>
        <p className={styles.muted}>
          上市普通股，{q.data ? `${fmtDateLong(q.data.asof)}收盤；法人連續天數以最近 ${q.data.days} 個交易日計算。` : '資料載入中…'}
        </p>
      </header>

      <section className={styles.card} aria-label="篩選條件">
        <div className={styles.presets} role="group" aria-label="常用策略">
          {PRESETS.map((p) => (
            <button key={p.key} type="button" className={styles.chip} aria-pressed={preset === p.key} title={p.hint} onClick={() => setPreset(preset === p.key ? '' : p.key)}>
              {p.label}
            </button>
          ))}
        </div>
        {preset && <p className={styles.muted}>{PRESETS.find((p) => p.key === preset)?.hint}；下方條件會再疊加。</p>}
        <div className={styles.fields}>
          {FIELDS.map((f) => (
            <label key={f.key} className={styles.field}>
              <span>
                {f.label}
                <span className={styles.unit}>{f.unit}</span>
              </span>
              <input inputMode="decimal" className={styles.input} value={custom[f.key] ?? ''} onChange={(e) => setNum(f.key, e.target.value)} />
            </label>
          ))}
          <label className={styles.field}>
            <span>產業</span>
            <select className={styles.input} value={custom.industry ?? ''} onChange={(e) => setCustom((c) => ({ ...c, industry: e.target.value || undefined }))}>
              <option value="">全部</option>
              {industries.map((i) => (
                <option key={i} value={i}>{i}</option>
              ))}
            </select>
          </label>
        </div>
        <button type="button" className={styles.link} onClick={() => { setCustom({}); setPreset('') }}>清除全部條件</button>
      </section>

      {q.isError && <p className={styles.muted}>{(q.error as Error).message}，稍後自動重試。</p>}
      {q.data && (
        <section className={styles.card} aria-label="選股結果">
          <div className={styles.resultHead}>
            <strong>符合 {rows.length} 檔</strong>
            <span className={styles.muted}>點欄位標題排序</span>
          </div>
          <div className={styles.tableBox}>
            <table className={styles.table}>
              <thead>
                <tr>
                  <th scope="col">股票</th>
                  <th scope="col">產業</th>
                  {COLS.map((c) => (
                    <th key={c.key} scope="col" aria-sort={sort.key === c.key ? (sort.desc ? 'descending' : 'ascending') : 'none'}>
                      <button type="button" className={styles.sortBtn} onClick={() => setSort((s) => ({ key: c.key, desc: s.key === c.key ? !s.desc : true }))}>
                        {c.label}
                        {sort.key === c.key ? (sort.desc ? ' ▼' : ' ▲') : ''}
                      </button>
                    </th>
                  ))}
                  <th scope="col"><span className="sr-only">加入自選</span></th>
                </tr>
              </thead>
              <tbody>
                {rows.slice(0, limit).map((r) => (
                  <tr key={r.code}>
                    <td>
                      <Link to={`/stock/${r.code}`} className={styles.stock}>
                        <span className={`${styles.code} num`}>{r.code}</span>
                        {r.name}
                      </Link>
                    </td>
                    <td className={styles.muted}>{r.industry}</td>
                    <td className="num">{fmtPrice(r.close)}</td>
                    <td className={`num ${direction(r.change_pct)}`}>{fmtPct(r.change_pct)}</td>
                    <td className="num">{fmtFixed(r.value_e8)}</td>
                    <td className="num">{r.pe != null ? fmtFixed(r.pe) : '—'}</td>
                    <td className="num">{r.dividend_yield != null ? fmtFixed(r.dividend_yield) : '—'}</td>
                    <td className="num">{r.pb != null ? fmtFixed(r.pb) : '—'}</td>
                    <td className={`num ${direction(r.foreign)}`}>{fmtSigned(r.foreign)}</td>
                    <td className={`num ${direction(r.trust)}`}>{fmtSigned(r.trust)}</td>
                    <td className={`num ${direction(r.foreign_streak)}`}>{streakText(r.foreign_streak)}</td>
                    <td className={`num ${direction(r.trust_streak)}`}>{streakText(r.trust_streak)}</td>
                    <td>
                      {wl.data?.codes.includes(r.code) ? (
                        <span className={styles.muted}>已在自選</span>
                      ) : (
                        <button type="button" className={styles.addBtn} onClick={() => addWl.mutate(r.code)} disabled={addWl.isPending}>
                          ＋自選
                        </button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {rows.length > limit && (
            <button type="button" className={styles.more} onClick={() => setLimit((l) => l + PAGE)}>
              顯示更多（還有 {rows.length - limit} 檔）
            </button>
          )}
          <p className={styles.muted}>資料：{q.data.sources.join('、')}。本頁不構成投資建議。</p>
        </section>
      )}
    </div>
  )
}

function streakText(n: number): string {
  if (n > 0) return `買 ${n} 天`
  if (n < 0) return `賣 ${-n} 天`
  return '—'
}
