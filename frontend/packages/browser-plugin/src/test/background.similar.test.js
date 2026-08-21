import { describe, expect, it } from 'vitest'
import { getSimilarElement, isSameIdStart } from '../background/similar'

/** 构造一层路径目录 */
function dir(tag, attrs = [], checked = true) {
  return {
    tag,
    value: '',
    checked,
    attrs: attrs.map(a => ({
      name: a.name ?? 'index',
      value: a.value ?? '',
      checked: a.checked ?? true,
      type: a.type ?? 1,
    })),
  }
}

/** 构造元素信息 */
function info(pathDirs, overrides = {}) {
  return {
    xpath: '',
    cssSelector: '',
    pathDirs,
    url: 'https://example.com/list',
    shadowRoot: false,
    tag: pathDirs[pathDirs.length - 1]?.tag ?? '',
    ...overrides,
  }
}

describe('similar - getSimilarElement 相似判定与泛化', () => {
  it('同结构兄弟元素: 判定相似且 index/文本属性被泛化', () => {
    // html > body > ul > li[1] > a  vs  html > body > ul > li[2] > a
    const pre = info([
      dir('html'), dir('body'),
      dir('ul', [{ name: 'class', value: 'list' }]),
      dir('li', [{ name: 'index', value: 1 }, { name: 'innertext', value: '第一项' }]),
      dir('a', [{ name: 'href', value: '/detail/1' }]),
    ])
    const cur = info([
      dir('html'), dir('body'),
      dir('ul', [{ name: 'class', value: 'list' }]),
      dir('li', [{ name: 'index', value: 2 }, { name: 'innertext', value: '第二项' }]),
      dir('a', [{ name: 'href', value: '/detail/2' }]),
    ])

    const res = getSimilarElement(pre, cur)
    expect(res).toBeTruthy()
    // index 差异被取消勾选, 公共 class 保留
    const li = res.pathDirs.find(d => d.tag === 'li')
    expect(li.attrs.find(a => a.name === 'index').checked).toBe(false)
    expect(li.attrs.find(a => a.name === 'innertext').checked).toBe(false)
    const ul = res.pathDirs.find(d => d.tag === 'ul')
    expect(ul.attrs.find(a => a.name === 'class').checked).toBe(true)
    // href 值不同 → 取消勾选
    const a = res.pathDirs.find(d => d.tag === 'a')
    expect(a.attrs.find(x => x.name === 'href').checked).toBe(false)
  })

  it('深度不同(影刀兼容场景): 旧版判不相似, 现在按公共后缀泛化', () => {
    // html > body > ul > li > a  vs  html > body > section > ul > li > a (多一层包裹)
    const pre = info([dir('html'), dir('body'), dir('ul'), dir('li'), dir('a')])
    const cur = info([dir('html'), dir('body'), dir('section'), dir('ul'), dir('li'), dir('a')])

    const res = getSimilarElement(pre, cur)
    expect(res).toBeTruthy()
    // 公共后缀 = ul/li/a, 非公共祖先层(html/body/section)被丢弃
    expect(res.pathDirs.map(d => d.tag)).toEqual(['ul', 'li', 'a'])
    // 首层非 html → xpath 应为 // 后代匹配
    expect(res.xpath.startsWith('//')).toBe(true)
  })

  it('中间层 tag 不同: 同样按公共后缀泛化', () => {
    // html > body > ul > li  vs  html > body > ol > li
    const pre = info([dir('html'), dir('body'), dir('ul'), dir('li')])
    const cur = info([dir('html'), dir('body'), dir('ol'), dir('li')])

    const res = getSimilarElement(pre, cur)
    expect(res).toBeTruthy()
    expect(res.pathDirs.map(d => d.tag)).toEqual(['li'])
  })

  it('自身 tag 不同: 判定不相似', () => {
    const pre = info([dir('html'), dir('body'), dir('ul'), dir('li')])
    const cur = info([dir('html'), dir('body'), dir('ul'), dir('div')])

    expect(getSimilarElement(pre, cur)).toBe(false)
  })

  it('url 不同: 判定不相似', () => {
    const pre = info([dir('html'), dir('a')], { url: 'https://a.com' })
    const cur = info([dir('html'), dir('a')], { url: 'https://b.com' })

    expect(getSimilarElement(pre, cur)).toBe(false)
  })

  it('isFrame 不同: 判定不相似', () => {
    const pre = info([dir('html'), dir('a')], { isFrame: false })
    const cur = info([dir('html'), dir('a')], { isFrame: true })

    expect(getSimilarElement(pre, cur)).toBe(false)
  })

  it('完全同结构: 泛化后保留全部层级(兼容旧行为)', () => {
    const mk = () => [dir('html'), dir('body'), dir('ul'), dir('li', [{ name: 'index', value: 1 }])]
    const res = getSimilarElement(info(mk()), info(mk()))
    expect(res.pathDirs.map(d => d.tag)).toEqual(['html', 'body', 'ul', 'li'])
    // 同元素自身对比 index 相同 → 仍保留勾选
    expect(res.pathDirs[3].attrs[0].checked).toBe(true)
  })
})

describe('similar - 增量折叠(多样本链式泛化)', () => {
  const mkLi = (index, text) => info([
    dir('html'), dir('body'),
    dir('ul', [{ name: 'class', value: 'list' }]),
    dir('li', [{ name: 'index', value: index }, { name: 'innertext', value: text }]),
    dir('a', [{ name: 'href', value: `/detail/${index}` }]),
  ])

  it('三轮链式: 样本计数递增且泛化结果可继续作为参照', () => {
    const g1 = getSimilarElement(mkLi(1, '第一项'), mkLi(2, '第二项'))
    expect(g1.similarSampleCount).toBe(2)
    expect(g1.pathDirs.find(d => d.tag === 'li').attrs.find(a => a.name === 'index').checked).toBe(false)

    const g2 = getSimilarElement(g1, mkLi(3, '第三项'))
    expect(g2.similarSampleCount).toBe(3)
    expect(g2.pathDirs.find(d => d.tag === 'li').attrs.find(a => a.name === 'index').checked).toBe(false)
    // 公共 class 属性仍参与匹配
    expect(g2.pathDirs.find(d => d.tag === 'ul').attrs.find(a => a.name === 'class').checked).toBe(true)
  })

  it('已取消勾选的属性不被后续同值样本复活', () => {
    const g1 = getSimilarElement(mkLi(1, '第一项'), mkLi(2, '第二项'))
    // 第三个样本 index/href 恰好与第一个样本同值 → 不得复活已泛化掉的匹配
    const g2 = getSimilarElement(g1, mkLi(1, '第三项'))
    const li = g2.pathDirs.find(d => d.tag === 'li')
    expect(li.attrs.find(a => a.name === 'index').checked).toBe(false)
    expect(g2.pathDirs.find(d => d.tag === 'a').attrs.find(a => a.name === 'href').checked).toBe(false)
  })

  it('已泛化参照被剔除的层不复活; 未泛化参照保持首轮复活行为', () => {
    // 已泛化参照: ul 层在上一轮被剔除(checked=false)
    const preGeneralized = info([
      dir('html'), dir('body'),
      dir('ul', [], false),
      dir('li'),
    ], { similarSampleCount: 2 })
    const res = getSimilarElement(preGeneralized, info([dir('html'), dir('body'), dir('ul'), dir('li')]))
    expect(res.pathDirs.find(d => d.tag === 'ul').checked).toBe(false)

    // 未泛化参照(首轮): 保留原有复活逻辑
    const preRaw = info([dir('html'), dir('body'), dir('ul', [], false), dir('li')])
    const resRaw = getSimilarElement(preRaw, info([dir('html'), dir('body'), dir('ul'), dir('li')]))
    expect(resRaw.pathDirs.find(d => d.tag === 'ul').checked).toBe(true)
  })
})

describe('similar - isSameIdStart', () => {
  it('双方首层均无 id: 视为一致(返回 true)', () => {
    expect(isSameIdStart([dir('html')], [dir('html')])).toBe(true)
  })

  it('首层 id 相同: 返回 true', () => {
    const a = dir('html', [{ name: 'id', value: 'root' }])
    expect(isSameIdStart([a], [dir('html', [{ name: 'id', value: 'root' }])])).toBe(true)
  })

  it('首层 id 不同: 返回 false', () => {
    expect(isSameIdStart(
      [dir('html', [{ name: 'id', value: 'a' }])],
      [dir('html', [{ name: 'id', value: 'b' }])],
    )).toBe(false)
  })
})
