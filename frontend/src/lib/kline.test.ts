import { describe, expect, it } from 'vitest'
import { klineDailyQueryOptions } from './kline'

const range = { start: '2026-01-01', end: '2026-08-18' }

// QK.kline → ['kline', symbol, start, end, extColumns ?? '']
const key = (symbol: string) => ['kline', symbol, range.start, range.end, ''] as const

describe('klineDailyQueryOptions.placeholderData', () => {
  it('同 symbol 保留 prev 数据 (改范围/字段时旧数据可暂显, 不闪)', () => {
    const opts = klineDailyQueryOptions('600519.SH', range)
    const prev = { rows: [{ date: 'x' }] }
    expect(opts.placeholderData(prev, { queryKey: key('600519.SH') })).toBe(prev)
  })

  it('异 symbol 返回 undefined (切股不误显示上一只)', () => {
    const opts = klineDailyQueryOptions('600519.SH', range)
    expect(opts.placeholderData({ rows: [] }, { queryKey: key('000001.SZ') })).toBeUndefined()
  })

  it('无 prevQuery 时返回 undefined', () => {
    const opts = klineDailyQueryOptions('600519.SH', range)
    expect(opts.placeholderData({ rows: [] }, undefined)).toBeUndefined()
  })
})
