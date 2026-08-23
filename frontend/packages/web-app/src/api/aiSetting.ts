import http from './http'

/** AI 配置项(敏感值经服务端掩码返回, 形如 sk-1***abcd) */
export interface AIConfig {
  AICHAT_BASE_URL: string
  AICHAT_API_KEY: string
  DEFAULT_MODEL: string
  SMART_MODEL: string
  CUA_BASE_URL: string
  CUA_API_KEY: string
  CUA_MODEL: string
}

export interface AIConfigSaveResult {
  saved_keys: string[]
}

export interface AIConfigTestResult {
  ok: boolean
  message?: string
}

// 读取当前生效的 AI 配置(敏感值掩码)
export function apiGetAIConfig() {
  return http.get<AIConfig>('/api/rpa-ai-service/admin/ai-config')
}

// 保存 AI 配置(掩码值原样回传会被服务端跳过, 保存后即时生效无需重启)
export function apiSaveAIConfig(values: Partial<AIConfig>) {
  return http.put<AIConfigSaveResult>('/api/rpa-ai-service/admin/ai-config', { values })
}

// 用当前生效配置向上游发最小请求验证连通性
export function apiTestAIConfig() {
  return http.post<AIConfigTestResult>('/api/rpa-ai-service/admin/ai-config/test', {})
}
