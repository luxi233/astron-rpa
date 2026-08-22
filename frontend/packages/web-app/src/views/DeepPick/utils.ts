import { WINDOW_NAME } from '@/constants'
import type { DEEP_PICK_EVENT } from '@/constants/deepPick'
import { windowManager } from '@/platform'

export { DEEP_PICK_EVENT, DEEP_PICK_HEIGHT, DEEP_PICK_WIDTH } from '@/constants/deepPick'

export function emitToMain(type: DEEP_PICK_EVENT, data: any = '') {
  windowManager.emitTo({
    type,
    target: WINDOW_NAME.MAIN,
    from: WINDOW_NAME.DEEP_PICK,
    data,
  })
}
