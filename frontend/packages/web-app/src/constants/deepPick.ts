// 深度捕获面板窗口(影刀式独立窗口): 主窗口与面板窗口间的常量约定;
// 宽度容纳双栏(左控件树 + 右属性面板)
export const DEEP_PICK_WIDTH = 640
export const DEEP_PICK_HEIGHT = 640

// 面板与主窗口间的 w2w 事件
export enum DEEP_PICK_EVENT {
  TREE_UPDATE = 'deep-pick-tree-update', // 主窗口 → 面板: 实时控件树增量推送(含 {frozen} 状态帧)
  CANCEL = 'deep-pick-cancel', // 面板 → 主窗口: 用户关闭面板取消捕获
  FINISH = 'deep-pick-finish', // 主窗口 → 面板: 捕获结束, 面板自毁
  TREE_PICK = 'deep-pick-tree-pick', // 面板 → 主窗口: 树节点点选捕获(携带节点属性链)
  TREE_PICK_RESULT = 'deep-pick-tree-pick-result', // 主窗口 → 面板: 点选 ack(定位失败解锁重试; 成功随 FINISH 关窗)
  TREE_PROPS = 'deep-pick-tree-props', // 面板 → 主窗口: 查询选中节点 UIA 属性(携带节点属性链)
  TREE_PROPS_RESULT = 'deep-pick-tree-props-result', // 主窗口 → 面板: 属性查询结果({props} 或 null=定位失败)
  READY = 'deep-pick-ready', // 面板 → 主窗口: 面板挂载就绪, 请求重发当前树快照(首帧可能先于面板监听注册到达而被丢弃)
  AI_SEARCH = 'deep-pick-ai-search', // 面板 → 主窗口: AI 查找元素(携带自然语言描述, 主窗口代理调云端 AI)
  AI_SEARCH_RESULT = 'deep-pick-ai-search-result', // 主窗口 → 面板: AI 查找结果(命中节点 key 或 null=未找到/失败)
}
