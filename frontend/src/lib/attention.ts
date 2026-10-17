import { useQuery } from '@tanstack/react-query'

export interface Disposition {
  code: string
  name: string
  market: string
  announced: string
  start: string
  end: string
  reason: string
  measure: string
  match: string
}

export interface Notice {
  code: string
  name: string
  market: string
  reason: string
  close: number | null
  count: number | null
}

export interface AttentionData {
  generated_at: string
  asof: string
  today: string
  disposition: Disposition[]
  notice: Notice[]
  sources: string[]
  note: string
}

async function fetchAttention(): Promise<AttentionData> {
  const r = await fetch('/api/market/attention')
  if (!r.ok) throw new Error(r.status === 503 ? '資料準備中' : `API ${r.status}`)
  return r.json()
}

export function useAttention() {
  return useQuery({ queryKey: ['attention'], queryFn: fetchAttention, staleTime: 5 * 60_000, retry: 2 })
}

const md = (iso: string) => `${Number(iso.slice(5, 7))}/${Number(iso.slice(8, 10))}`

export function periodText(d: Disposition): string {
  return `${md(d.start)}～${md(d.end)}`
}

/** 個股頁用：這檔目前是否處置中（含已公告未開始）或在最近交易日被列注意。 */
export function statusOf(data: AttentionData | undefined, code: string): { disposition?: Disposition; notice?: Notice } {
  if (!data) return {}
  return { disposition: data.disposition.find((d) => d.code === code), notice: data.notice.find((n) => n.code === code) }
}
