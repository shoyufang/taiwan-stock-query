import { describe, expect, it } from 'vitest'
import { parseSse, toolLabel } from './aiChat'

describe('parseSse', () => {
  it('切出完整事件並保留未完成的片段', () => {
    const a = parseSse('data: {"type":"status","text":"思考中…"}\n\ndata: {"type":"tool","na')
    expect(a.events).toEqual([{ type: 'status', text: '思考中…' }])
    const b = parseSse(a.rest + 'me":"site_stock","args":{"code":"2330"}}\n\n')
    expect(b.events).toEqual([{ type: 'tool', name: 'site_stock', args: { code: '2330' } }])
    expect(b.rest).toBe('')
  })
  it('略過壞掉的事件', () => {
    expect(parseSse('data: {oops\n\n').events).toEqual([])
  })
})

describe('toolLabel', () => {
  it('中文名稱與代號', () => {
    expect(toolLabel('site_stock', { code: '2330' })).toBe('查詢個股資料（2330）')
    expect(toolLabel('unknown_tool', {})).toBe('查詢unknown_tool')
  })
})
