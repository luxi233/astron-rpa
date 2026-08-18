import { blob2Text } from '@/utils/common'

import { fileRead, fileWrite } from '@/api/resource'
import type { ITableResponse } from '@/types/normalTable'

import http from './http'
import { getBaseURL } from './http/env'

const useSettingPath = './.setting.json'

export async function getUserSetting() {
  try {
    const { data } = await fileRead({ path: useSettingPath })
    const result = await blob2Text<string>(data)
    return JSON.parse(result || '{}')
  }
  catch {
    return {}
  }
}

export async function setUserSetting(params: RPA.UserSetting) {
  return fileWrite({ path: useSettingPath, mode: 'w', content: JSON.stringify(params) })
}

/**
 * @returns 获取自动启动状态
 */
export async function autoStartStatus() {
  const res = await http.post<{ autostart: boolean }>('/scheduler/window/auto_start/check', null)

  return res.data.autostart
}
/**
 * @returns 设置自动启动
 */
export function autoStartEnable() {
  return http.post('/scheduler/window/auto_start/enable', null)
}
/**
 * @returns 关闭自动启动
 */
export function autoStartDisable() {
  return http.post('/scheduler/window/auto_start/disable', null)
}
/**
 * @returns 检查视频文件是否存在
 */
export function checkVideoPaths(data) {
  return http.post('/scheduler/video/play', data, { toast: false })
}

/**
 * @description: 邮箱短信设置
 */
export function toolsInterfacePost(data) {
  return http.post('/scheduler/alert/test', data)
}

/**
 * @description: 获取Api Key列表数据
 */
export async function getApis(params) {
  const res = await http.get<ITableResponse>('/api/rpa-openapi/api-keys/get', params)
  return res.data || { records: [], total: 0 }
}

/**
 * @description: 统一日志中心(scheduler): 流程日志 + 引擎日志
 */
export interface RunLogItem {
  path: string
  project_id: string
  exec_id: string
  size: number
  mtime: number
}

export async function getRunLogList(projectId?: string) {
  const res = await http.get<{ total: number, list: RunLogItem[] }>('/scheduler/logcenter/list', { category: 'run', project_id: projectId || '' })
  return res.data || { total: 0, list: [] }
}

export function clearRunLog(data: { project_id?: string, before_days?: number }) {
  return http.post<{ removed: number }>('/scheduler/logcenter/clear', { category: 'run', ...data })
}

export function getRunLogDownloadUrl(path: string) {
  return `${getBaseURL()}/scheduler/logcenter/download?category=run&path=${encodeURIComponent(path)}`
}

/**
 * @description: 引擎日志(设计器/执行器/调度器自身日志)查看
 */
export interface EngineLogItem {
  name: string
  size: number
  mtime: number
}

export async function getEngineLogList() {
  const res = await http.get<{ dir: string, total: number, list: EngineLogItem[] }>('/scheduler/logcenter/list', { category: 'engine' })
  return res.data || { dir: '', total: 0, list: [] }
}

export async function readEngineLog(data: { filename: string, tail_lines?: number }) {
  const res = await http.post<{ filename: string, size: number, truncated: boolean, lines: string[] }>('/scheduler/logcenter/read', data)
  return res.data || { filename: data.filename, size: 0, truncated: false, lines: [] as string[] }
}

export function clearEngineLog(data: { before_days?: number }) {
  return http.post<{ removed: number }>('/scheduler/logcenter/clear', { category: 'engine', ...data })
}

export function getEngineLogDownloadUrl(filename: string) {
  return `${getBaseURL()}/scheduler/logcenter/download?category=engine&path=${encodeURIComponent(filename)}`
}

/**
 * @description: 删除API Key
 */
export function deleteAPI(params) {
  return http.post('/api/rpa-openapi/api-keys/remove', params)
}

/**
 * @description: 新增API Key
 */
export async function createAPI(params) {
  const res = await http.post('/api/rpa-openapi/api-keys/create', params)
  return res.data
}

/**
 * @description: 获取Agent Api Key列表数据
 */
export async function getAgentApis(params) {
  const res = await http.get('/api/rpa-openapi/api-keys/get-astron', params)
  return res.data
}

/**
 * @description: 删除Agent API Key
 */
export function deleteAgentAPI(id: number) {
  return http.post('/api/rpa-openapi/api-keys/remove-astron', { id })
}

/**
 * @description: 新增Agent API Key
 */
export async function createAgentAPI<T>(params: T) {
  const res = await http.post<{ id: number }>('/api/rpa-openapi/api-keys/create-astron', params)
  return res.data
}

/**
 * @description: 更新Agent API Key
 * @param params
 * @returns
 */
export async function updateAgentApi<T>(params: T) {
  const res = await http.post<{ id: number }>('/api/rpa-openapi/api-keys/update-astron', params)
  return res.data
}
