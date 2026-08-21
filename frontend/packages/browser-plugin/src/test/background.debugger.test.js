import { describe, it, expect, vi, beforeEach } from 'vitest'
import { Debugger, checkDebuggerDetached } from '../background/debugger'

global.chrome = global.chrome || {};

describe('background/debugger', () => {

  it('checkDebuggerDetached should resolve true if not attached', async () => {
    global.chrome.debugger.getTargets = vi.fn(cb => cb([]));
    await expect(checkDebuggerDetached(1)).resolves.toBe(true);
  });

  it('checkDebuggerDetached should timeout after 10 attempts', async () => {
    global.chrome.debugger.getTargets = vi.fn(cb => cb([{ tabId: 1 }]));
    // 500ms 轮询 × 11 次 ≈ 5.5s，超过 vitest 默认 5s，需显式放宽超时；
    // 错误消息为 i18n 动态文案（errors.debuggerTimeout），断言不绑定具体文案
    await expect(checkDebuggerDetached(1, 11)).rejects.toThrow();
  }, 10000);

  it('Debugger.attachDebugger should resolve true', async () => {
    await expect(Debugger.attachDebugger(1)).resolves.toBe(true);
    Debugger.attached = false
  });
  
  it('Debugger.attachDebugger should resolve true (idempotent) if already attached', async () => {
    // 实现为幂等设计：已附加时静默返回成功，不重复附加
    Debugger.attached = true;
    await expect(Debugger.attachDebugger(1)).resolves.toBe(true);
    Debugger.attached = false;
  });

  it('Debugger.detachDebugger should resolve true', async () => {
    Debugger.attached = true;
    await expect(Debugger.detachDebugger(1)).resolves.toBe(true);
  });

  it('Debugger.enableRuntime should resolve true', async () => {
    await expect(Debugger.enableRuntime(1)).resolves.toBe(true);
  });

  it('Debugger.getFrameTree should resolve', async () => {
    await expect(Debugger.getFrameTree(1)).resolves.toBeDefined();
  });

  it('Debugger.evaluate should throw if no context', async () => {
    Debugger.frameContextIdMap = { 0: [] };
    // 错误文案为 i18n 动态文案(errors.contextNotFound), 断言不绑定具体语言
    await expect(Debugger.evaluate(1, '1+1', 0)).rejects.toThrow();
  });
});
