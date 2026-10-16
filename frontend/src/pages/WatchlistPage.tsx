import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState, type FormEvent } from 'react'
import { Link } from 'react-router'
import { alertsApi, searchStocks, watchlistApi, type AlertRule, type AlertsResponse, type WatchRow } from '../lib/api'
import { arrow, direction, fmtInt, fmtMonthDay, fmtPct, fmtPrice, fmtSigned } from '../lib/format'
import { taipeiToday } from '../lib/indicators'
import type { Mode } from '../lib/marketMode'
import { useLiveQuotes, type LiveStock } from '../lib/useLiveQuotes'
import { addCode, move, removeCode } from '../lib/watchlistOps'
import styles from './WatchlistPage.module.css'

const PUBLIC_HOST = typeof location !== 'undefined' ? location.hostname : ''

export function WatchlistPage({ mode }: { mode: Mode }) {
  const qc = useQueryClient()
  const wl = useQuery({ queryKey: ['watchlist'], queryFn: watchlistApi.get, refetchInterval: 5 * 60_000 })
  const alerts = useQuery({ queryKey: ['alerts'], queryFn: alertsApi.list })
  const save = useMutation({
    mutationFn: watchlistApi.put,
    onSuccess: () => qc.invalidateQueries({ queryKey: ['watchlist'] }),
  })
  const codes = wl.data?.codes ?? []
  const { data: live } = useLiveQuotes(codes, codes.length > 0)

  return (
    <div className={styles.page}>
      <header className={styles.head}>
        <div>
          <h1 className={styles.h1}>自選股</h1>
          <p className={styles.muted}>
            {mode === 'live' ? '盤中即時更新；開盤前顯示最近收盤。' : '顯示最近收盤；盤中自動切換為即時報價。'}
            {wl.data?.is_default && '（目前為預設清單，加入或移除後會記住你的設定）'}
          </p>
        </div>
        <AddStock onAdd={(code) => save.mutate(addCode(codes, code))} busy={save.isPending} />
      </header>
      {save.isError && <p className={styles.error}>{(save.error as Error).message}</p>}

      <section className={styles.card} aria-label="報價牆">
        {wl.isPending ? (
          <div className={styles.skel} />
        ) : codes.length === 0 ? (
          <p className={styles.empty}>清單是空的，用右上角加入股票。</p>
        ) : (
          <QuoteWall rows={wl.data!.rows} live={live as Record<string, LiveStock>} rules={alerts.data?.rules ?? []}
            onMove={(c, d) => save.mutate(move(codes, c, d))} onRemove={(c) => save.mutate(removeCode(codes, c))} />
        )}
      </section>

      <div className={styles.cols}>
        <AlertsPanel data={alerts.data} codes={codes} names={Object.fromEntries((wl.data?.rows ?? []).map((r) => [r.code, r.name]))} />
        <div className={styles.stack}>
          <EventsPanel />
          <ChannelsPanel channels={alerts.data?.channels} />
        </div>
      </div>
    </div>
  )
}

function AddStock({ onAdd, busy }: { onAdd: (code: string) => void; busy: boolean }) {
  const [text, setText] = useState('')
  const [msg, setMsg] = useState('')
  const sugg = useQuery({ queryKey: ['search', text], queryFn: () => searchStocks(text), enabled: text.trim().length >= 1, staleTime: 60_000 })
  async function submit(e: FormEvent) {
    e.preventDefault()
    const first = text.trim().split(/\s+/)[0]
    if (!first) return
    const hits = await searchStocks(first)
    if (!hits.length) return setMsg(`找不到「${first}」`)
    onAdd(hits[0].code)
    setText('')
    setMsg(`已加入 ${hits[0].code} ${hits[0].name}`)
  }
  return (
    <form className={styles.add} onSubmit={submit}>
      <label htmlFor="wl-add" className="sr-only">
        加入股票
      </label>
      <input id="wl-add" list="wl-sugg" className={styles.input} value={text} onChange={(e) => setText(e.target.value)} placeholder="代號或名稱" autoComplete="off" />
      <datalist id="wl-sugg">
        {(sugg.data ?? []).map((s) => (
          <option key={s.code} value={`${s.code} ${s.name}`} />
        ))}
      </datalist>
      <button className={styles.primary} type="submit" disabled={busy}>
        加入
      </button>
      {msg && <span className={styles.muted} role="status">{msg}</span>}
    </form>
  )
}

function QuoteWall({ rows, live, rules, onMove, onRemove }: {
  rows: WatchRow[]
  live: Record<string, LiveStock>
  rules: AlertRule[]
  onMove: (code: string, d: -1 | 1) => void
  onRemove: (code: string) => void
}) {
  const today = taipeiToday()
  return (
    <div className={styles.tableBox}>
      <table className={styles.table}>
        <thead>
          <tr>
            <th scope="col">股票</th>
            <th scope="col">成交價</th>
            <th scope="col">漲跌</th>
            <th scope="col">漲跌幅</th>
            <th scope="col">最高</th>
            <th scope="col">最低</th>
            <th scope="col">成交量（張）</th>
            <th scope="col">時間</th>
            <th scope="col">警示</th>
            <th scope="col"><span className="sr-only">操作</span></th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r, i) => {
            const l = live[r.code]
            const isLive = l && l.time?.slice(0, 10) === today
            const price = isLive ? l.close : r.close
            const change = isLive ? l.change : r.change
            const pct = isLive ? l.change_pct : r.change_pct
            const n = rules.filter((x) => x.code === r.code && x.enabled).length
            return (
              <tr key={r.code}>
                <td>
                  <Link to={`/stock/${r.code}`} className={styles.stock}>
                    <span className={`${styles.code} num`}>{r.code}</span>
                    {r.name}
                  </Link>
                </td>
                <td className={`num ${styles.price} ${change != null ? direction(change) : ''}`}>{price != null ? fmtPrice(price) : '—'}</td>
                <td className={`num ${change != null ? direction(change) : ''}`}>{change != null ? `${arrow(change)} ${fmtSigned(change, 2)}` : '—'}</td>
                <td className={`num ${pct != null ? direction(pct) : ''}`}>{pct != null ? fmtPct(pct) : '—'}</td>
                <td className="num">{fmtOpt(isLive ? l.high : r.high)}</td>
                <td className="num">{fmtOpt(isLive ? l.low : r.low)}</td>
                <td className="num">{(isLive ? l.total_volume : r.volume) != null ? fmtInt((isLive ? l.total_volume : r.volume)!) : '—'}</td>
                <td className={`num ${styles.muted}`}>{isLive ? <span className={styles.live}>{l.time.slice(11, 19)}</span> : r.date ? `${fmtMonthDay(r.date)} 收` : '—'}</td>
                <td className="num">{n ? n : ''}</td>
                <td className={styles.ops}>
                  <button type="button" className={styles.icon} onClick={() => onMove(r.code, -1)} disabled={i === 0} aria-label={`${r.name} 上移`}>
                    ↑
                  </button>
                  <button type="button" className={styles.icon} onClick={() => onMove(r.code, 1)} disabled={i === rows.length - 1} aria-label={`${r.name} 下移`}>
                    ↓
                  </button>
                  <button type="button" className={styles.icon} onClick={() => onRemove(r.code)} aria-label={`移除 ${r.name}`}>
                    ✕
                  </button>
                </td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}

function fmtOpt(n: number | undefined | null) {
  return n != null ? fmtPrice(n) : '—'
}

function describe(rule: AlertRule, types: AlertsResponse['types']) {
  const t = types[rule.type]
  if (!t) return rule.type
  return t.unit ? `${t.label} ${rule.value.toLocaleString('en-US')} ${t.unit}` : t.label
}

function AlertsPanel({ data, codes, names }: { data?: AlertsResponse; codes: string[]; names: Record<string, string> }) {
  const qc = useQueryClient()
  const refresh = () => qc.invalidateQueries({ queryKey: ['alerts'] })
  const [code, setCode] = useState('')
  const [type, setType] = useState('price_above')
  const [value, setValue] = useState('')
  const add = useMutation({ mutationFn: () => alertsApi.add(code || codes[0], type, Number(value) || 0), onSuccess: () => { setValue(''); refresh() } })
  const toggle = useMutation({ mutationFn: (r: AlertRule) => alertsApi.toggle(r.id, !r.enabled), onSuccess: refresh })
  const remove = useMutation({ mutationFn: (id: number) => alertsApi.remove(id), onSuccess: refresh })
  if (!data) return <section className={styles.card}><div className={styles.skel} /></section>
  const t = data.types[type]
  const needsValue = !!t?.unit

  return (
    <section className={styles.card} aria-labelledby="al-h">
      <h2 id="al-h" className={styles.h2}>警示規則</h2>
      <form className={styles.ruleForm} onSubmit={(e) => { e.preventDefault(); add.mutate() }}>
        <label>
          <span className={styles.lbl}>股票</span>
          <select value={code || codes[0] || ''} onChange={(e) => setCode(e.target.value)} className={styles.input}>
            {codes.map((c) => (
              <option key={c} value={c}>{c} {names[c] ?? ''}</option>
            ))}
          </select>
        </label>
        <label>
          <span className={styles.lbl}>條件</span>
          <select value={type} onChange={(e) => setType(e.target.value)} className={styles.input}>
            {Object.entries(data.types).map(([k, v]) => (
              <option key={k} value={k}>{v.label}{v.when === 'close' ? '（收盤後）' : '（盤中即時）'}</option>
            ))}
          </select>
        </label>
        {needsValue && (
          <label>
            <span className={styles.lbl}>數值（{t.unit}）</span>
            <input className={styles.input} inputMode="decimal" value={value} onChange={(e) => setValue(e.target.value)} required placeholder={`${t.range[0]}～${t.range[1]}`} />
          </label>
        )}
        <button type="submit" className={styles.primary} disabled={add.isPending || codes.length === 0}>新增</button>
      </form>
      {add.isError && <p className={styles.error}>{(add.error as Error).message}</p>}

      {data.rules.length === 0 ? (
        <p className={styles.muted}>還沒有警示規則。</p>
      ) : (
        <ul className={styles.rules}>
          {data.rules.map((r) => (
            <li key={r.id} className={r.enabled ? '' : styles.disabled}>
              <label className={styles.ruleToggle}>
                <input type="checkbox" checked={r.enabled} onChange={() => toggle.mutate(r)} />
                <span>
                  <span className={`${styles.code} num`}>{r.code}</span>
                  {names[r.code] ?? ''}　{describe(r, data.types)}
                </span>
              </label>
              <span className={`${styles.muted} num`}>{r.last_triggered_date ? `上次 ${fmtMonthDay(r.last_triggered_date)}` : ''}</span>
              <button type="button" className={styles.icon} onClick={() => remove.mutate(r.id)} aria-label="刪除這條警示">✕</button>
            </li>
          ))}
        </ul>
      )}
      <p className={styles.note}>同一條規則一天最多通知一次。盤中規則在交易時段即時判斷；收盤規則於收盤資料更新後判斷。</p>
    </section>
  )
}

function EventsPanel() {
  const ev = useQuery({ queryKey: ['alert-events'], queryFn: alertsApi.events, refetchInterval: 60_000 })
  return (
    <section className={styles.card} aria-labelledby="ev-h">
      <h2 id="ev-h" className={styles.h2}>最近觸發</h2>
      {!ev.data?.events.length ? (
        <p className={styles.muted}>尚無紀錄。</p>
      ) : (
        <ul className={styles.events}>
          {ev.data.events.map((e) => (
            <li key={e.id}>
              <span className={`${styles.muted} num`}>{e.at.slice(5, 16).replace('T', ' ')}</span>
              <Link to={`/stock/${e.code}`}>{e.message}</Link>
            </li>
          ))}
        </ul>
      )}
    </section>
  )
}

function ChannelsPanel({ channels }: { channels?: AlertsResponse['channels'] }) {
  const test = useMutation({ mutationFn: alertsApi.test })
  const label = (ok?: boolean) => (ok ? '已設定' : '未設定')
  return (
    <section className={styles.card} aria-labelledby="ch-h">
      <h2 id="ch-h" className={styles.h2}>通知方式</h2>
      <ul className={styles.channels}>
        <li><span>網頁內提示</span><span className={styles.ok}>已啟用</span></li>
        <li><span>手機推播（ntfy）</span><span className={channels?.ntfy ? styles.ok : styles.muted}>{label(channels?.ntfy)}</span></li>
        <li><span>Telegram</span><span className={channels?.telegram ? styles.ok : styles.muted}>{label(channels?.telegram)}</span></li>
      </ul>
      <button type="button" className={styles.secondary} onClick={() => test.mutate()} disabled={test.isPending}>傳送測試通知</button>
      {test.data && (
        <p className={styles.muted} role="status">
          結果：{Object.entries(test.data.result).map(([k, v]) => `${k} ${v ? '成功' : '失敗'}`).join('、')}
        </p>
      )}
      <details className={styles.howto}>
        <summary>手機推播（ntfy）怎麼設定？</summary>
        <ol>
          <li>手機先裝好並登入 Tailscale（和電腦同一個帳號）。</li>
          <li>安裝免費的 <b>ntfy</b> App（App Store／Google Play 搜尋「ntfy」）。</li>
          <li>在 App 按「+」訂閱，勾選「使用其他伺服器」，伺服器填 <code>http://{PUBLIC_HOST}:8601</code>，主題填 <code>twstock</code>。</li>
          <li>回到這裡按「傳送測試通知」，手機應該會跳出通知。</li>
        </ol>
      </details>
      <details className={styles.howto}>
        <summary>Telegram 怎麼設定？</summary>
        <ol>
          <li>在 Telegram 搜尋 <b>@BotFather</b>，傳送 <code>/newbot</code>，照指示取名，最後會拿到一串 token。</li>
          <li>打開你剛建立的機器人，隨便傳一句話給它。</li>
          <li>請 Claude 幫你開好設定視窗，或自己在終端機執行：<code>ssh -t home "bash ~/apps/twstock/deploy/set-telegram.sh"</code>，貼上 token。</li>
        </ol>
      </details>
    </section>
  )
}
