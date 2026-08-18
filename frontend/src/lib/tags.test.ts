import { describe, expect, it } from 'vitest'
import { splitTags } from './tags'

describe('splitTags', () => {
  it('空串 / undefined / null → 空数组', () => {
    expect(splitTags('')).toEqual([])
    expect(splitTags(undefined)).toEqual([])
    expect(splitTags(null)).toEqual([])
  })

  it('逗号分隔 + 首尾空白 trim + 空项过滤', () => {
    expect(splitTags('白酒, 短期 ,困境反转')).toEqual(['白酒', '短期', '困境反转'])
  })

  it('相邻逗号 / 仅逗号 → 空数组', () => {
    expect(splitTags('a,,b')).toEqual(['a', 'b'])
    expect(splitTags(',,')).toEqual([])
  })
})
