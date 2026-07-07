/**
 * 生成模型管理（接口文档 21，additive 新增）
 *
 * - GET /models          可选模型注册表 + 当前模型
 * - PUT /models/current  切换当前生成模型（后续讲义/练习等生成即走该模型）
 *
 * 未配 Key 的模型仍可选：后端调用时自动回落默认模型（优雅降级，绝不崩）。
 * USE_REAL_API=false 时返回本地演示数据（与后端注册表同构）。
 */
import { apiGet, apiPut, USE_REAL_API } from './api'

export interface ModelInfo {
  id: string
  label: string
  provider: 'mock' | 'deepseek' | 'modelscope'
  /** 是否已配置该 provider 的 Key（未配也可选，生成时自动回落默认模型） */
  available: boolean
  isCurrent: boolean
}

export interface ModelRegistry {
  models: ModelInfo[]
  current: string
}

/* 纯前端 mock 演示数据（VITE_USE_REAL_API=false 时使用，可本地切换） */
let mockCurrent = 'deepseek-chat'
const MOCK_MODELS: Omit<ModelInfo, 'isCurrent'>[] = [
  { id: 'deepseek-chat', label: 'DeepSeek（官方 · 默认）', provider: 'deepseek', available: true },
  { id: 'ZhipuAI/GLM-4.6', label: 'GLM-4.6（魔搭）', provider: 'modelscope', available: false },
  { id: 'Qwen/Qwen3-32B', label: 'Qwen3-32B（魔搭）', provider: 'modelscope', available: false },
  { id: 'deepseek-ai/DeepSeek-V3.1', label: 'DeepSeek-V3.1（魔搭）', provider: 'modelscope', available: false },
]

const mockRegistry = (): ModelRegistry => ({
  models: MOCK_MODELS.map((m) => ({ ...m, isCurrent: m.id === mockCurrent })),
  current: mockCurrent,
})

/** 拉取可选模型列表 + 当前模型 */
export async function fetchModelRegistry(): Promise<ModelRegistry> {
  if (!USE_REAL_API) return Promise.resolve(mockRegistry())
  return apiGet<ModelRegistry>('/models')
}

/** 切换当前生成模型，返回切换后的注册表快照 */
export async function switchModel(modelId: string): Promise<ModelRegistry> {
  if (!USE_REAL_API) {
    mockCurrent = modelId
    return Promise.resolve(mockRegistry())
  }
  return apiPut<ModelRegistry>('/models/current', { modelId })
}
