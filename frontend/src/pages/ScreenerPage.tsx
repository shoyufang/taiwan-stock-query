import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useMemo, useState } from 'react'
import { Link } from 'react-router'
import { watchlistApi } from '../lib/api'
import { direction, fmtDateLong, fmtFixed, fmtPct, fmtPrice, fmtSigned } from '../lib/format'
import {
  applyFunnel,
  CHIP_ITEMS,
  PRESETS,
  sortRows,
  TECH_GROUPS,
  TECH_ITEM_MAP,
  type Filters,
  type LogicMode,
  type PoolScope,
  type ScreenRow,
  type SortKey,
} from '../lib/screener'
import { addCode } from '../lib/watchlistOps'
import styles from './ScreenerPage.module.css'

interface Base {
  asof: string
  generated_at: string
  days: number
  tech_days?: number
  rows: ScreenRow[]
  sources: string[]
}

async function fetchBase(): Promise<Base> {
  const r = await fetch('/api/screener/base')
  if (!r.ok) throw new Error(r.status === 503 ? '選股資料準備中' : `API ${r.status}`)
  return r.json()
}

type NumericFilterKey =
  | 'priceMin'
  | 'priceMax'
  | 'pctMin'
  | 'valueMin'
  | 'volLotsMin'
  | 'peMax'
  | 'yieldMin'
  | 'pbMax'
  | 'revYoyMin'
  | 'foreignMin'
  | 'trustMin'
  | 'foreignStreakMin'
  | 'trustStreakMin'

const FIELDS: { key: NumericFilterKey; label: string; unit: string }[] = [
  { key: 'priceMin', label: '股價 ≥', unit: '元' },
  { key: 'priceMax', label: '股價 ≤', unit: '元' },
  { key: 'pctMin', label: '漲跌幅 ≥', unit: '%' },
  { key: 'valueMin', label: '成交值 ≥', unit: '億' },
  { key: 'volLotsMin', label: '成交量 ≥', unit: '張' },
  { key: 'peMax', label: '本益比 ≤', unit: '倍' },
  { key: 'yieldMin', label: '殖利率 ≥', unit: '%' },
  { key: 'pbMax', label: '股淨比 ≤', unit: '倍' },
  { key: 'revYoyMin', label: '月營收年增 ≥', unit: '%' },
  { key: 'foreignMin', label: '外資買超 ≥', unit: '張' },
  { key: 'trustMin', label: '投信買超 ≥', unit: '張' },
  { key: 'foreignStreakMin', label: '外資連買 ≥', unit: '天' },
  { key: 'trustStreakMin', label: '投信連買 ≥', unit: '天' },
]

const COLS: { key: SortKey; label: string }[] = [
  { key: 'close', label: '收盤' },
  { key: 'change_pct', label: '漲跌幅' },
  { key: 'value_e8', label: '成交值(億)' },
  { key: 'vol_ratio', label: '量比' },
  { key: 'rsi14', label: 'RSI(14)' },
  { key: 'k', label: 'K / D' },
  { key: 'pe', label: '本益比' },
  { key: 'dividend_yield', label: '殖利率%' },
  { key: 'rev_yoy', label: '營收YoY%' },
  { key: 'foreign', label: '外資(張)' },
  { key: 'trust', label: '投信(張)' },
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

  const presetFilters = PRESETS.find((p) => p.key === preset)?.filters ?? {}
  const activePool: PoolScope = custom.pool ?? presetFilters.pool ?? 'all'
  const activeTechSignals = custom.techSignals ?? presetFilters.techSignals ?? []
  const activeTechMode: LogicMode = custom.techMode ?? presetFilters.techMode ?? 'OR'
  const activeChipSignals = custom.chipSignals ?? presetFilters.chipSignals ?? []
  const activeChipMode: LogicMode = custom.chipMode ?? presetFilters.chipMode ?? 'OR'

  const filters: Filters = {
    ...presetFilters,
    ...custom,
    pool: activePool,
    techSignals: activeTechSignals,
    techMode: activeTechMode,
    chipSignals: activeChipSignals,
    chipMode: activeChipMode,
  }

  const { rows: filteredRows, funnel } = useMemo(
    () => (q.data ? applyFunnel(q.data.rows, filters) : { rows: [], funnel: { total: 0, pool: 0, afterTech: 0, afterChip: 0, final: 0 } }),
    [q.data, JSON.stringify(filters)],
  )
  const rows = useMemo(() => sortRows(filteredRows, sort.key, sort.desc), [filteredRows, sort])
  const industries = useMemo(() => [...new Set((q.data?.rows ?? []).map((r) => r.industry).filter(Boolean))].sort(), [q.data])

  // 統計目前股票池中各技術訊號的觸發檔數
  const techCounts = useMemo(() => {
    const counts: Record<string, number> = {}
    if (!q.data) return counts
    const poolRows = activePool === 'tw50' ? q.data.rows.filter((r) => r.in_tw50) : q.data.rows
    for (const r of poolRows) {
      for (const s of r.tech_signals ?? []) {
        counts[s] = (counts[s] ?? 0) + 1
      }
    }
    return counts
  }, [q.data, activePool])

  const qc = useQueryClient()
  const wl = useQuery({ queryKey: ['watchlist'], queryFn: watchlistApi.get })
  const addWl = useMutation({
    mutationFn: (code: string) => watchlistApi.put(addCode(wl.data?.codes ?? [], code)),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['watchlist'] }),
  })

  const setNum = (key: NumericFilterKey, v: string) =>
    setCustom((c) => {
      const next = { ...c }
      if (v.trim() === '' || Number.isNaN(Number(v))) delete next[key]
      else next[key] = Number(v)
      return next
    })

  const toggleTechSignal = (sig: string) =>
    setCustom((c) => {
      const cur = c.techSignals ?? presetFilters.techSignals ?? []
      const next = cur.includes(sig) ? cur.filter((x) => x !== sig) : [...cur, sig]
      return { ...c, techSignals: next }
    })

  const toggleChipSignal = (sig: string) =>
    setCustom((c) => {
      const cur = c.chipSignals ?? presetFilters.chipSignals ?? []
      const next = cur.includes(sig) ? cur.filter((x) => x !== sig) : [...cur, sig]
      return { ...c, chipSignals: next }
    })

  return (
    <div className={styles.page}>
      <header>
        <h1 className={styles.h1}>選股與技術掃描</h1>
        <p className={styles.muted}>
          {q.data
            ? `上市普通股，${fmtDateLong(q.data.asof)}收盤；技術指標以最近 ${q.data.tech_days ?? 60} 個交易日日 K 計算，法人連續天數以最近 ${q.data.days} 個交易日計算。`
            : '資料載入中…'}
        </p>
      </header>

      <section className={styles.card} aria-label="策略與多因子漏斗">
        <div className={styles.topRow}>
          <div className={styles.presets} role="group" aria-label="常用策略">
            {PRESETS.map((p) => (
              <button
                key={p.key}
                type="button"
                className={styles.chip}
                aria-pressed={preset === p.key}
                title={p.hint}
                onClick={() => {
                  setCustom({})
                  setPreset(preset === p.key ? '' : p.key)
                }}
              >
                {p.label}
              </button>
            ))}
          </div>
          <div className={styles.poolGroup} role="group" aria-label="股票池範圍">
            <button
              type="button"
              className={styles.modeBtn}
              aria-pressed={activePool === 'all'}
              onClick={() => setCustom((c) => ({ ...c, pool: 'all' }))}
            >
              全市場 ({q.data?.rows.length ?? '—'})
            </button>
            <button
              type="button"
              className={styles.modeBtn}
              aria-pressed={activePool === 'tw50'}
              onClick={() => setCustom((c) => ({ ...c, pool: 'tw50' }))}
            >
              台灣 50 權值股
            </button>
          </div>
        </div>
        {preset && <p className={styles.muted}>{PRESETS.find((p) => p.key === preset)?.hint}；下方可繼續勾選技術、籌碼或財報條件疊加。</p>}

        {q.data && (
          <div className={styles.funnel} aria-label="多因子篩選漏斗">
            <div className={styles.funnelStep}>
              <span className={styles.funnelLabel}>母體與基本門檻</span>
              <strong className={`${styles.funnelNum} num`}>{funnel.pool} 檔</strong>
            </div>
            <span className={styles.funnelArrow} aria-hidden="true">→</span>
            <div className={styles.funnelStep}>
              <span className={styles.funnelLabel}>1. 技術面 ({activeTechSignals.length ? activeTechMode : '未設'})</span>
              <strong className={`${styles.funnelNum} num`}>{funnel.afterTech} 檔</strong>
            </div>
            <span className={styles.funnelArrow} aria-hidden="true">→</span>
            <div className={styles.funnelStep}>
              <span className={styles.funnelLabel}>2. 籌碼面 ({activeChipSignals.length ? activeChipMode : '門檻'})</span>
              <strong className={`${styles.funnelNum} num`}>{funnel.afterChip} 檔</strong>
            </div>
            <span className={styles.funnelArrow} aria-hidden="true">→</span>
            <div className={`${styles.funnelStep} ${styles.funnelFinal}`}>
              <span className={styles.funnelLabel}>3. 估值與財報通過</span>
              <strong className={`${styles.funnelNum} num`}>{funnel.final} 檔</strong>
            </div>
          </div>
        )}
      </section>

      <section className={styles.card} aria-label="技術指標掃描">
        <div className={styles.secHead}>
          <div>
            <h2 className={styles.h2}>步驟 1 · 技術指標掃描</h2>
            <p className={styles.muted}>可複選 KD、MACD、RSI、均線、布林通道與量能突破訊號（括號內為目前股票池符合檔數）</p>
          </div>
          <div className={styles.poolGroup} role="group" aria-label="技術條件邏輯">
            <button
              type="button"
              className={styles.modeBtn}
              aria-pressed={activeTechMode === 'OR'}
              onClick={() => setCustom((c) => ({ ...c, techMode: 'OR' }))}
            >
              任一成立 (OR)
            </button>
            <button
              type="button"
              className={styles.modeBtn}
              aria-pressed={activeTechMode === 'AND'}
              onClick={() => setCustom((c) => ({ ...c, techMode: 'AND' }))}
            >
              全部成立 (AND)
            </button>
          </div>
        </div>
        <div className={styles.techGroups}>
          {TECH_GROUPS.map((g) => (
            <div key={g.group} className={styles.techGroup}>
              <span className={styles.groupTitle}>{g.group}</span>
              <div className={styles.presets}>
                {g.items.map((item) => {
                  const active = activeTechSignals.includes(item.key)
                  const cnt = techCounts[item.key] ?? 0
                  return (
                    <button
                      key={item.key}
                      type="button"
                      className={styles.techChip}
                      aria-pressed={active}
                      onClick={() => toggleTechSignal(item.key)}
                    >
                      <span>{item.label}</span>
                      <span className={`${styles.badgeCount} num`}>{cnt}</span>
                    </button>
                  )
                })}
              </div>
            </div>
          ))}
        </div>
      </section>

      <section className={styles.card} aria-label="籌碼與財報估值條件">
        <div className={styles.secHead}>
          <div>
            <h2 className={styles.h2}>步驟 2 & 3 · 法人籌碼與估值財報篩選</h2>
            <p className={styles.muted}>勾選法人買超條件並設定本益比、殖利率、股淨比、月營收年增率門檻</p>
          </div>
          <div className={styles.poolGroup} role="group" aria-label="籌碼條件邏輯">
            <button
              type="button"
              className={styles.modeBtn}
              aria-pressed={activeChipMode === 'OR'}
              onClick={() => setCustom((c) => ({ ...c, chipMode: 'OR' }))}
            >
              籌碼 OR
            </button>
            <button
              type="button"
              className={styles.modeBtn}
              aria-pressed={activeChipMode === 'AND'}
              onClick={() => setCustom((c) => ({ ...c, chipMode: 'AND' }))}
            >
              籌碼 AND
            </button>
          </div>
        </div>

        <div className={styles.presets} role="group" aria-label="籌碼快捷條件">
          {CHIP_ITEMS.map((item) => (
            <button
              key={item.key}
              type="button"
              className={styles.techChip}
              aria-pressed={activeChipSignals.includes(item.key)}
              onClick={() => toggleChipSignal(item.key)}
            >
              {item.label}
            </button>
          ))}
        </div>

        <div className={styles.fields}>
          {FIELDS.map((f) => (
            <label key={f.key} className={styles.field}>
              <span>
                {f.label}
                <span className={styles.unit}>{f.unit}</span>
              </span>
              <input
                inputMode="decimal"
                className={styles.input}
                value={custom[f.key] ?? presetFilters[f.key] ?? ''}
                onChange={(e) => setNum(f.key, e.target.value)}
              />
            </label>
          ))}
          <label className={styles.field}>
            <span>產業</span>
            <select
              className={styles.input}
              value={custom.industry ?? ''}
              onChange={(e) => setCustom((c) => ({ ...c, industry: e.target.value || undefined }))}
            >
              <option value="">全部</option>
              {industries.map((i) => (
                <option key={i} value={i}>
                  {i}
                </option>
              ))}
            </select>
          </label>
        </div>
        <button
          type="button"
          className={styles.link}
          onClick={() => {
            setCustom({})
            setPreset('')
          }}
        >
          清除全部條件
        </button>
      </section>

      {q.isError && <p className={styles.muted}>{(q.error as Error).message}，稍後自動重試。</p>}
      {q.data && (
        <section className={styles.card} aria-label="選股結果">
          <div className={styles.resultHead}>
            <strong>符合 {rows.length} 檔</strong>
            <span className={styles.muted}>點欄位標題排序；點股票代號進入個股頁</span>
          </div>
          <div className={styles.tableBox}>
            <table className={styles.table}>
              <thead>
                <tr>
                  <th scope="col">股票</th>
                  <th scope="col">產業</th>
                  <th scope="col">技術訊號</th>
                  {COLS.map((c) => (
                    <th key={c.key} scope="col" aria-sort={sort.key === c.key ? (sort.desc ? 'descending' : 'ascending') : 'none'}>
                      <button
                        type="button"
                        className={styles.sortBtn}
                        onClick={() => setSort((s) => ({ key: c.key, desc: s.key === c.key ? !s.desc : true }))}
                      >
                        {c.label}
                        {sort.key === c.key ? (sort.desc ? ' ▼' : ' ▲') : ''}
                      </button>
                    </th>
                  ))}
                  <th scope="col">
                    <span className="sr-only">加入自選</span>
                  </th>
                </tr>
              </thead>
              <tbody>
                {rows.slice(0, limit).map((r) => {
                  const sigs = r.tech_signals ?? []
                  // 優先顯示使用者有勾選的訊號，再補其餘訊號（最多顯示 3 個標籤以免撐寬表格）
                  const orderedSigs = [
                    ...sigs.filter((s) => activeTechSignals.includes(s)),
                    ...sigs.filter((s) => !activeTechSignals.includes(s)),
                  ]
                  return (
                    <tr key={r.code}>
                      <td>
                        <Link to={`/stock/${r.code}`} className={styles.stock}>
                          <span className={`${styles.code} num`}>{r.code}</span>
                          {r.name}
                        </Link>
                      </td>
                      <td className={styles.muted}>{r.industry}</td>
                      <td className={styles.sigCell}>
                        {orderedSigs.length === 0 ? (
                          <span className={styles.muted}>—</span>
                        ) : (
                          <div className={styles.sigList}>
                            {orderedSigs.slice(0, 3).map((s) => {
                              const meta = TECH_ITEM_MAP[s]
                              return (
                                <span
                                  key={s}
                                  className={`${styles.sigBadge} ${
                                    meta?.tone === 'up' ? styles.sigUp : meta?.tone === 'down' ? styles.sigDown : ''
                                  }`}
                                >
                                  {meta?.shortLabel ?? s}
                                </span>
                              )
                            })}
                            {orderedSigs.length > 3 && <span className={styles.muted}>+{orderedSigs.length - 3}</span>}
                          </div>
                        )}
                      </td>
                      <td className="num">{fmtPrice(r.close)}</td>
                      <td className={`num ${direction(r.change_pct)}`}>{fmtPct(r.change_pct)}</td>
                      <td className="num">{fmtFixed(r.value_e8)}</td>
                      <td className="num">{r.vol_ratio != null ? `${fmtFixed(r.vol_ratio, 1)}x` : '—'}</td>
                      <td className="num">{r.rsi14 != null ? fmtFixed(r.rsi14, 1) : '—'}</td>
                      <td className="num">
                        {r.k != null && r.d != null ? `${fmtFixed(r.k, 0)} / ${fmtFixed(r.d, 0)}` : '—'}
                      </td>
                      <td className="num">{r.pe != null ? fmtFixed(r.pe) : '—'}</td>
                      <td className="num">{r.dividend_yield != null ? fmtFixed(r.dividend_yield) : '—'}</td>
                      <td className={`num ${direction(r.rev_yoy ?? 0)}`}>
                        {r.rev_yoy != null ? fmtPct(r.rev_yoy) : '—'}
                      </td>
                      <td className={`num ${direction(r.foreign)}`}>{fmtSigned(r.foreign)}</td>
                      <td className={`num ${direction(r.trust)}`}>{fmtSigned(r.trust)}</td>
                      <td className={`num ${direction(r.foreign_streak)}`}>{streakText(r.foreign_streak)}</td>
                      <td className={`num ${direction(r.trust_streak)}`}>{streakText(r.trust_streak)}</td>
                      <td>
                        {wl.data?.codes.includes(r.code) ? (
                          <span className={styles.muted}>已在自選</span>
                        ) : (
                          <button
                            type="button"
                            className={styles.addBtn}
                            onClick={() => addWl.mutate(r.code)}
                            disabled={addWl.isPending}
                          >
                            ＋自選
                          </button>
                        )}
                      </td>
                    </tr>
                  )
                })}
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
