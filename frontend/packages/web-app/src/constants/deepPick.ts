// 深度捕获面板窗口(影刀式独立窗口): 主窗口与面板窗口间的常量约定
export const DEEP_PICK_WIDTH = 320
export const DEEP_PICK_HEIGHT = 640

// 面板与主窗口间的 w2w 事件
export enum DEEP_PICK_EVENT {
  TREE_UPDATE = 'deep-pick-tree-update', // 主窗口 → 面板: 实时控件树增量推送
  CANCEL = 'deep-pick-cancel', // 面板 → 主窗口: 用户关闭面板取消捕获
  FINISH = 'deep-pick-finish', // 主窗口 → 面板: 捕获结束, 面板自毁
  TREE_PICK = 'deep-pick-tree-pick', // 面板 → 主窗口: 树节点点选捕获(携带节点属性链)
}
