import { describe, expect, it } from 'vitest'
import { buildStockExternalUrl } from './stock-external-link'

describe('buildStockExternalUrl', () => {
  it('http/https 模板通过并替换占位符', () => {
    expect(buildStockExternalUrl('https://x.com/{code}/{market}/{symbol}', '000001.SZ')).toBe('https://x.com/000001/sz/000001.SZ')
    expect(buildStockExternalUrl('http://x.com/s/{symbol}', '600036.SH')).toBe('http://x.com/s/600036.SH')
  })

  it('空模板返回 null (关闭外链)', () => {
    expect(buildStockExternalUrl('', '000001.SZ')).toBeNull()
    expect(buildStockExternalUrl('   ', '000001.SZ')).toBeNull()
  })

  it('危险/非 http(s) scheme 返回 null', () => {
    expect(buildStockExternalUrl('javascript:alert(1)', '000001.SZ')).toBeNull()
    expect(buildStockExternalUrl('data:text/html,<script>x</script>', '000001.SZ')).toBeNull()
    expect(buildStockExternalUrl('ftp://x.com/{code}', '000001.SZ')).toBeNull()
    expect(buildStockExternalUrl('//x.com/{code}', '000001.SZ')).toBeNull()
  })

  it('非股票 symbol 返回 null', () => {
    expect(buildStockExternalUrl('https://x.com/{code}', 'sh000001')).toBeNull()
    expect(buildStockExternalUrl('https://x.com/{code}', '000001')).toBeNull()
  })
})
