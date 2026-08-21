import { Utils } from '../common/utils'

/**
 * 计算两条元素路径自尾部(元素自身)向上的最长公共 tag 后缀长度。
 * 后缀内 tag 逐层相同即停止于首个不匹配层。
 */
function commonSuffixLength(prePathDirs: Array<ElementDirectory>, currentPathDirs: Array<ElementDirectory>) {
  let i = 0
  while (i < prePathDirs.length && i < currentPathDirs.length) {
    const preDir = prePathDirs[prePathDirs.length - 1 - i]
    const curDir = currentPathDirs[currentPathDirs.length - 1 - i]
    if (preDir.tag !== curDir.tag) {
      break
    }
    i++
  }
  return i
}

/**
 * Determine whether elements are similar based on the element information.
 * If they are similar, return the information of similar elements
 */
export function getSimilarElement(preElementInfo: ElementInfo, currentElementInfo: ElementInfo) {
  if (!isSimilarElement(preElementInfo, currentElementInfo)) {
    return false
  }

  // 增量折叠: 参照携带 similarSampleCount 即为已泛化结果, 本轮在其上继续求交集
  const preGeneralized = preElementInfo.similarSampleCount !== undefined
  const pathDirs = generateSimilarPathDirs(preElementInfo.pathDirs, currentElementInfo.pathDirs, preGeneralized)
  if (!pathDirs) {
    return false
  }
  const xpath = Utils.generateXPath(pathDirs)
  let cssSelector = ''
  if (!preElementInfo.shadowRoot) {
    cssSelector = Utils.generateCssSelector(pathDirs)
  }
  else {
    cssSelector = generateSimilarSelector(preElementInfo.cssSelector, currentElementInfo.cssSelector)
  }

  // 样本计数递增: 旧数据缺省按 1(首次折叠后为 2)
  const similarElementInfo = { ...preElementInfo, xpath, cssSelector, pathDirs, similarSampleCount: (preElementInfo.similarSampleCount ?? 1) + 1 }
  return similarElementInfo
}

/**
 * 判定两个元素是否相似(对齐影刀的宽松语义)。
 *
 * 必要条件:
 * - `url`: 页面一致。
 * - `shadowRoot` / `isFrame`: 所属文档环境一致。
 *
 * 结构条件(放宽): 不再要求 DOM 深度与每层 tag 完全一致,
 * 只要求自元素自身向上的最长公共 tag 后缀 ≥ 1(即两元素自身 tag 相同)。
 * 结构差异通过 {@link generateSimilarPathDirs} 丢弃非公共祖先层来泛化,
 * 生成的 xpath 为 `//` 后代匹配, 可命中全部相似元素。
 *
 * @param preElementInfo - The reference element information.
 * @param currentElementInfo - The element information to compare against the reference.
 * @returns `true` if the elements are considered similar; otherwise, `false`.
 */
function isSimilarElement(preElementInfo: ElementInfo, currentElementInfo: ElementInfo) {
  const { pathDirs } = preElementInfo
  const { pathDirs: currentPathDirs } = currentElementInfo

  if (preElementInfo.url !== currentElementInfo.url) {
    return false
  }

  if (preElementInfo.shadowRoot !== currentElementInfo.shadowRoot) {
    return false
  }

  if (preElementInfo.isFrame !== currentElementInfo.isFrame) {
    return false
  }

  // 自身 tag 不同(公共后缀为 0)才判定不相似; 深度/中间层差异交由泛化处理
  return commonSuffixLength(pathDirs, currentPathDirs) >= 1
}

/**
 * Generates a similar CSS selector by comparing a previous selector with a current selector.
 * If the selectors are identical, returns the previous selector.
 * Otherwise, iterates through each selector segment and removes specific attributes
 * (such as `:nth-child`, class names, and IDs) from segments that differ between the two selectors.
 *
 * @param preSelector - The previous CSS selector string.
 * @param currentSelector - The current CSS selector string to compare against.
 * @returns A CSS selector string that is similar to the previous selector, with differing attributes removed.
 */
function generateSimilarSelector(preSelector: string, currentSelector: string) {
  if (preSelector === currentSelector) {
    return preSelector
  }
  const preSelectorArr = preSelector.split('>')
  const currentSelectorArr = currentSelector.split('>')
  for (let i = 0; i < preSelectorArr.length; i++) {
    // nth-child
    if (preSelectorArr[i] !== currentSelectorArr[i] && preSelectorArr[i].includes(':nth-child')) {
      preSelectorArr[i] = preSelectorArr[i].split(':nth-child')[0]
    }
    // class
    if (preSelectorArr[i] !== currentSelectorArr[i] && preSelectorArr[i].includes('.')) {
      preSelectorArr[i] = preSelectorArr[i].split('.')[0]
    }
    // id #
    if (preSelectorArr[i] !== currentSelectorArr[i] && preSelectorArr[i].includes('#')) {
      preSelectorArr[i] = preSelectorArr[i].split('#')[0]
    }
  }
  const selector = preSelectorArr.join('>')
  return selector
}

/**
 * 生成相似元素的泛化路径目录(对齐影刀语义)。
 *
 * 仅保留两条路径自尾部向上的公共 tag 后缀层(共同结构),
 * 非公共祖先层直接丢弃 —— 生成的 xpath 以 `//` 后代匹配命中全部相似元素。
 * 公共后缀层内, 按属性值差异泛化:
 * - 参照元素独有或值不同的属性: `checked` 置 false(不参与匹配)
 * - 值与类型均相同的属性: 保留双方均勾选的匹配
 * - `innertext`/`text` 属性: 恒不参与匹配(相似元素文本通常不同)
 *
 * 两元素结构完全一致时, 公共后缀即全路径, 行为与旧版精确泛化保持一致。
 *
 * @param prePathDirs - The path directories of the reference element.
 * @param currentPathDirs - The path directories of the element to compare against.
 * @param preGeneralized - 参照是否已是增量折叠的泛化结果; 是则被剔除的层不再复活(单调)
 * @returns The generalized tail-aligned `ElementDirectory` array, or `null` if no common suffix.
 */
function generateSimilarPathDirs(prePathDirs: Array<ElementDirectory>, currentPathDirs: Array<ElementDirectory>, preGeneralized = false) {
  const suffixLen = commonSuffixLength(prePathDirs, currentPathDirs)
  if (suffixLen < 1) {
    return null
  }
  const tailDirs = prePathDirs.slice(-suffixLen)
  const currentTailDirs = currentPathDirs.slice(-suffixLen)
  for (let i = tailDirs.length - 1; i >= 0; i--) {
    const prePathDir = tailDirs[i]
    const currentPathDir = currentTailDirs[i]
    if (prePathDir.checked !== currentPathDir.checked && !preGeneralized) {
      // 首轮保留原有复活逻辑; 已泛化参照保持 false, 避免后续样本复活已剔除的层
      prePathDir.checked = true
    }
    prePathDir.attrs.forEach((attr) => {
      const currentAttr = currentPathDir.attrs.find(item => item.name === attr.name)
      if (!currentAttr) {
        attr.value = ''
        attr.checked = false
      }
      else {
        // handle value comparison and type
        const isSameType = currentAttr.type === attr.type
        const isSameValue = String(attr.value) === String(currentAttr.value) && attr.value !== ''
        // handle checked logic
        if (isSameValue && isSameType) {
          attr.checked = currentAttr.checked && attr.checked // both true to keep true
        }
        else {
          attr.checked = false
        }
        // special handling for text
        if (currentAttr.name === 'innertext' || currentAttr.name === 'text') {
          attr.checked = false
          attr.value = ''
        }
      }
    })
  }
  return tailDirs
}

/**
 * Determines whether the first directory in two arrays of `ElementDirectory` objects
 * have the same checked and non-empty `id` attribute value.
 *
 * @param prePathDirs - The array of previous path directories to compare.
 * @param currentPathDirs - The array of current path directories to compare.
 * @returns `true` if both arrays are non-empty, and their first elements have a checked, non-empty `id` attribute with the same value; otherwise, `false`.
 */
export function isSameIdStart(prePathDirs: Array<ElementDirectory>, currentPathDirs: Array<ElementDirectory>) {
  if (!prePathDirs || !currentPathDirs) {
    return false
  }
  if (prePathDirs.length === 0 || currentPathDirs.length === 0) {
    return false
  }
  const preFirst = prePathDirs[0]
  const currentFirst = currentPathDirs[0]
  const preIdAttr = preFirst.attrs.find(item => item.name === 'id' && item.checked && item.value !== '')
  const currentIdAttr = currentFirst.attrs.find(item => item.name === 'id' && item.checked && item.value !== '')
  if (preIdAttr && currentIdAttr) {
    return preIdAttr.value === currentIdAttr.value
  }
  if (!preIdAttr && !currentIdAttr) {
    return true
  }
  return false
}
