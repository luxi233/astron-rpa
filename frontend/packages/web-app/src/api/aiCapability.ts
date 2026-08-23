import http from './http'

/**
 * 调用云端预设 prompt 模板(AI 捕获元素/生成流程等), 返回模型回复文本。
 * prompt_type 白名单由 ai-service 维护(element_search/flow_generate 等)。
 */
export function apiChatPrompt(promptType: string, params: Record<string, string>) {
  return http.post<string>('/api/rpa-ai-service/v1/chat/prompt', {
    prompt_type: promptType,
    params,
    stream: false,
  })
}
