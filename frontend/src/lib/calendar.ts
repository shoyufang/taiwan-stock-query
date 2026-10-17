export type EventKind = 'dividend' | 'conference' | 'deadline'

export interface CalEvent {
  date: string
  end_date?: string
  kind: EventKind
  code?: string
  name?: string
  title: string
  detail: string
  place?: string
}

export interface CalendarData {
  generated_at: string
  today: string
  start: string
  end: string
  events: CalEvent[]
  sources: string[]
  note: string
}

export const KIND_LABEL: Record<EventKind, string> = { dividend: '除權息', conference: '法說會', deadline: '公布期限' }

export interface Filter {
  kinds: Set<EventKind>
  watchOnly: boolean
  showPast: boolean
}

/** 篩選後依日期分組（日期遞增）。期限類事件與個股無關，「只看自選股」時仍保留；跨日法說會以 end_date 判斷是否已結束。 */
export function groupEvents(events: CalEvent[], f: Filter, watch: Set<string>, today: string): [string, CalEvent[]][] {
  const out = new Map<string, CalEvent[]>()
  for (const e of events) {
    if (!f.kinds.has(e.kind)) continue
    if (!f.showPast && (e.end_date ?? e.date) < today) continue
    if (f.watchOnly && e.code && !watch.has(e.code)) continue
    const list = out.get(e.date) ?? []
    list.push(e)
    out.set(e.date, list)
  }
  return [...out.entries()].sort(([a], [b]) => (a < b ? -1 : 1))
}

const WEEK = ['日', '一', '二', '三', '四', '五', '六']

export function dayLabel(iso: string, today: string): string {
  const [y, m, d] = iso.split('-').map(Number)
  const wd = WEEK[new Date(Date.UTC(y, m - 1, d)).getUTCDay()]
  const base = `${m}/${d}（${wd}）`
  return iso === today ? `今天 ${base}` : base
}
