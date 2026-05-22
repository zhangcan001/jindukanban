/**
 * useProjectStore —— 单例式 currentProject / currentBatch 共享状态
 *
 * 没有引入 Pinia(避免增加一个依赖 + 配置链路),用 Vue 3 reactive() 单例同样能解决问题:
 * 多个组件 import 这个 composable 拿到的是同一份 reactive state,getter 行为和 Pinia 一致。
 *
 * 适用场景:Dashboard / Imports / Reports / Analytics 等多视图同时关心"当前打开的项目"
 * 和"当前选中的批次",过去每个视图各自 getProject() + listBatches(),不仅请求重复,
 * 还会出现"在 Dashboard 改了项目名,Imports 还显示旧名"这种过期数据问题。
 */
import { computed, reactive, readonly } from 'vue'

import { getProject } from '../api/projects'
import type { ImportBatch } from '../types/import'
import type { Project } from '../types/project'

interface ProjectStoreState {
  currentProject: Project | null
  currentBatch: ImportBatch | null
  loadingProject: boolean
  lastLoadedAt: number | null
  lastError: string | null
}

const state = reactive<ProjectStoreState>({
  currentProject: null,
  currentBatch: null,
  loadingProject: false,
  lastLoadedAt: null,
  lastError: null,
})

// 5 秒内重复请求同一项目时走缓存——足以覆盖 router 跳转后多个组件 onMounted 串发的场景
const PROJECT_CACHE_TTL_MS = 5_000

async function loadProject(projectId: number, options: { force?: boolean } = {}): Promise<Project | null> {
  const cached = state.currentProject
  const isFresh =
    cached &&
    cached.id === projectId &&
    state.lastLoadedAt !== null &&
    Date.now() - state.lastLoadedAt < PROJECT_CACHE_TTL_MS
  if (isFresh && !options.force) {
    return cached
  }
  state.loadingProject = true
  state.lastError = null
  try {
    const project = await getProject(projectId)
    state.currentProject = project
    state.lastLoadedAt = Date.now()
    return project
  } catch (error) {
    state.lastError = error instanceof Error ? error.message : String(error)
    state.currentProject = null
    return null
  } finally {
    state.loadingProject = false
  }
}

function setCurrentBatch(batch: ImportBatch | null): void {
  state.currentBatch = batch
}

function clear(): void {
  state.currentProject = null
  state.currentBatch = null
  state.lastLoadedAt = null
  state.lastError = null
}

function invalidate(): void {
  // 强制下次 loadProject 重新请求——用于"修改项目后想立即看到最新值"
  state.lastLoadedAt = null
}

const currentProjectId = computed(() => state.currentProject?.id ?? null)
const currentBatchId = computed(() => state.currentBatch?.id ?? null)
const currentProjectName = computed(() => state.currentProject?.name ?? '')

export function useProjectStore() {
  return {
    state: readonly(state),
    currentProjectId,
    currentBatchId,
    currentProjectName,
    loadProject,
    setCurrentBatch,
    clear,
    invalidate,
  }
}
