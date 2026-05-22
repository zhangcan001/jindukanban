<template>
  <main class="page-shell workbench-shell">
    <section class="workbench-hero">
      <div>
        <p class="eyebrow">workbench</p>
        <h1>工程进度工作台</h1>
        <p class="intro">把导入、看板、滞后项和报表放到第一屏，日常巡检从这里开始。</p>
      </div>
      <div class="project-picker">
        <span>当前项目</span>
        <el-select
          v-if="projects.length"
          v-model="selectedProjectId"
          placeholder="选择项目"
          size="large"
          @change="handleProjectChange"
        >
          <el-option v-for="project in projects" :key="project.id" :label="project.name" :value="project.id" />
        </el-select>
        <div v-else class="stacked-actions">
          <el-button type="primary" size="large" @click="router.push('/projects/new')">新建项目</el-button>
          <el-button size="large" @click="createDemo">创建示例项目</el-button>
        </div>
      </div>
    </section>

    <el-alert v-if="errorMessage" :title="errorMessage" type="error" show-icon :closable="false" />
    <el-empty v-if="!loading && !projects.length" description="当前还没有项目，请先创建项目或使用示例项目体验系统。">
      <div class="stacked-actions">
        <el-button type="primary" @click="router.push('/projects/new')">创建新项目</el-button>
        <el-button @click="createDemo">创建示例项目</el-button>
        <el-button @click="router.push('/getting-started')">查看新手引导</el-button>
        <el-button @click="createDemo">导入示例数据</el-button>
      </div>
    </el-empty>

    <template v-else>
      <section class="shortcut-grid">
        <button class="shortcut-card shortcut-primary" type="button" @click="goImport">
          <span class="shortcut-icon">↥</span>
          <strong>导入 Excel</strong>
          <small>上传周报、选择 Sheet、确认表头</small>
        </button>
        <button class="shortcut-card" type="button" @click="goProjectPage('dashboard')">
          <span class="shortcut-icon">▦</span>
          <strong>查看进度看板</strong>
          <small>总体进度、计划对比和趋势</small>
        </button>
        <button class="shortcut-card" type="button" @click="goProjectPage('warnings')">
          <span class="shortcut-icon">!</span>
          <strong>查看滞后项</strong>
          <small>严重滞后任务和预警记录</small>
        </button>
        <button class="shortcut-card" type="button" @click="goProjectPage('reports')">
          <span class="shortcut-icon">⇩</span>
          <strong>导出报表</strong>
          <small>总览、滞后、专业和明细报表</small>
        </button>
      </section>

      <section class="dashboard-card-grid">
        <div class="metric-card">
          <span>最近项目</span>
          <strong class="metric-name">{{ currentProject?.name ?? '-' }}</strong>
        </div>
        <div class="metric-card">
          <span>当前项目</span>
          <strong class="metric-name">{{ currentProject?.name ?? '-' }}</strong>
        </div>
        <div class="metric-card">
          <span>最新数据日期</span>
          <strong>{{ projectOverview?.data_date ?? latestBatch?.data_date ?? '-' }}</strong>
        </div>
        <div class="metric-card">
          <span>项目总体完成率</span>
          <strong>{{ percentText(projectOverview?.project_actual_percent) }}</strong>
        </div>
        <div class="metric-card">
          <span>应完成率</span>
          <strong>{{ percentText(projectOverview?.project_planned_percent) }}</strong>
        </div>
        <div class="metric-card">
          <span>进度偏差</span>
          <strong :class="deviationClass">{{ signedPercentText(projectOverview?.project_deviation) }}</strong>
        </div>
        <div class="metric-card">
          <span>预警数</span>
          <strong class="metric-danger">{{ severeDelayedCount }}</strong>
        </div>
        <div class="metric-card">
          <span>整改未关闭数</span>
          <strong>{{ openRectificationCount }}</strong>
        </div>
        <div class="metric-card">
          <span>最近导出报表</span>
          <strong class="metric-date">{{ latestReportText }}</strong>
        </div>
        <div class="metric-card">
          <span>最近导入时间</span>
          <strong class="metric-date">{{ formatDateTime(latestBatch?.created_at) }}</strong>
        </div>
        <div class="metric-card">
          <span>发布状态</span>
          <strong class="metric-name">{{ latestBatch?.status === 'published' ? '已发布' : latestBatch?.status ?? '-' }}</strong>
        </div>
      </section>

      <section class="table-surface">
        <div class="section-title">
          <div>
            <h2>最近项目</h2>
            <p>常用入口放在项目卡片上，适合现场快速操作。</p>
          </div>
          <el-button text type="primary" @click="router.push('/projects')">查看全部项目</el-button>
        </div>
        <div class="recent-project-grid">
          <article v-for="project in recentProjects" :key="project.id" class="recent-project-card">
            <div>
              <strong>{{ project.name }}</strong>
              <span>{{ project.project_type || '未填写类型' }}</span>
            </div>
            <div class="actions-row">
              <el-button size="small" type="primary" @click="openProject(project.id, 'dashboard')">进入看板</el-button>
              <el-button size="small" @click="openProject(project.id, 'import')">导入 Excel</el-button>
              <el-button size="small" @click="openProject(project.id, 'reports')">报表中心</el-button>
              <el-button size="small" @click="openProject(project.id, 'rectifications')">整改闭环</el-button>
              <el-button size="small" @click="router.push('/maintenance')">系统维护</el-button>
            </div>
          </article>
        </div>
      </section>

      <section v-if="projectOverview && !projectOverview.empty" class="form-surface project-overview-scope">
        <div class="section-title">
          <div>
            <h2>项目总进度统计范围</h2>
            <p>{{ projectOverview.scope_label || aggregateScopeText }}</p>
          </div>
          <div class="overview-actions">
            <el-select v-model="selectedCalculationMethod" placeholder="自动推荐" @change="loadProjectSummary">
              <el-option label="自动推荐" value="" />
              <el-option
                v-for="method in projectCalculationMethods"
                :key="method.code"
                :label="method.name"
                :value="method.code"
                :disabled="!method.available"
              >
                <span>{{ method.name }}</span>
                <el-tag v-if="method.recommended" size="small" type="success" style="margin-left: 8px">推荐</el-tag>
                <span v-if="method.warning" class="muted-text" style="margin-left: 8px">{{ method.warning }}</span>
              </el-option>
            </el-select>
            <el-tag type="success">{{ projectOverview.included_batch_count }} 个 Sheet</el-tag>
          </div>
        </div>
        <div class="scope-meta-grid">
          <div><span>当前统计口径</span><strong>{{ projectOverview.calculation_method_name || projectOverview.statistics_label || '-' }}</strong></div>
          <div><span>推荐原因</span><strong>{{ projectOverview.recommendation_reason || '-' }}</strong></div>
          <div><span>是否混合单位</span><strong>{{ projectOverview.mixed_units ? '是' : '否' }}</strong></div>
          <div><span>单位列表</span><strong>{{ projectOverview.unit_list?.length ? projectOverview.unit_list.join('、') : '未识别' }}</strong></div>
          <div><span>当前范围权重合计</span><strong>{{ weightPercentText(projectOverview.weight_sum) }}</strong></div>
        </div>
        <div class="scope-batch-list">
          <el-tag v-for="batch in projectOverview.included_batches" :key="batch.batch_id" type="info">
            {{ batch.sheet_name || `批次 ${batch.batch_id}` }}
          </el-tag>
        </div>
        <p v-if="projectOverview.warning" class="scope-warning">{{ projectOverview.warning }}</p>
      </section>

      <el-empty
        v-if="!loading && selectedProjectId && (!projectOverview || projectOverview.empty) && !recentImports.length"
        description="当前项目还没有导入进度数据，请先导入 Excel 进度表。"
      >
        <el-button type="primary" @click="goImport">导入 Excel</el-button>
      </el-empty>

      <section class="workbench-grid">
        <div class="table-surface">
          <div class="section-title">
            <div>
              <h2>最近导入记录</h2>
              <p>最近 5 条导入批次</p>
            </div>
            <el-button text type="primary" @click="goImport">继续导入</el-button>
          </div>
          <el-table v-loading="loading" :data="recentImports" empty-text="暂无导入记录">
            <el-table-column prop="status" label="状态" width="110">
              <template #default="{ row }">
                <el-tag :type="statusTag(row.status)">{{ statusText(row.status) }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="data_date" label="数据日期" width="120" />
            <el-table-column label="导入时间" min-width="160">
              <template #default="{ row }">{{ formatDateTime(row.created_at) }}</template>
            </el-table-column>
            <el-table-column label="发布" width="90">
              <template #default="{ row }">{{ row.status === 'published' ? '是' : '否' }}</template>
            </el-table-column>
            <el-table-column label="冻结" width="120">
              <template #default="{ row }">
                <el-tag v-if="row.is_frozen" type="warning">已冻结</el-tag>
                <span v-else>-</span>
              </template>
            </el-table-column>
            <el-table-column label="操作" width="160">
              <template #default="{ row }">
                <el-button v-if="row.status === 'published' && !row.is_frozen" text type="warning" @click="freezeBatch(row.id)">冻结</el-button>
                <el-button v-if="row.is_frozen" text type="success" @click="unfreezeBatch(row.id)">取消冻结</el-button>
              </template>
            </el-table-column>
          </el-table>
        </div>

        <div class="table-surface">
          <div class="section-title">
            <div>
              <h2>滞后项摘要</h2>
              <p>前 5 条严重滞后任务</p>
            </div>
            <el-button text type="primary" @click="goProjectPage('dashboard')">打开看板</el-button>
          </div>
          <el-table v-loading="loading" :data="delayedRows" empty-text="暂无严重滞后任务">
            <el-table-column prop="task_name" label="任务名称" min-width="150" />
            <el-table-column prop="discipline" label="专业" width="100" />
            <el-table-column label="实际%" width="90">
              <template #default="{ row }">{{ percentText(row.actual_percent) }}</template>
            </el-table-column>
            <el-table-column label="应完成%" width="90">
              <template #default="{ row }">{{ percentText(row.planned_percent) }}</template>
            </el-table-column>
            <el-table-column label="偏差" width="90">
              <template #default="{ row }">
                <span class="metric-negative">{{ signedPercentText(row.progress_deviation) }}</span>
              </template>
            </el-table-column>
          </el-table>
        </div>
      </section>
    </template>
  </main>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useRouter } from 'vue-router'

import { getAnalyticsDelayedRanking, getAnalyticsTrend, getProjectOverview } from '../api/analytics'
import { freezeImportBatch, listProjectImports, unfreezeImportBatch } from '../api/imports'
import { createDemoProject, listProjects } from '../api/projects'
import { getRectificationSummary } from '../api/rectifications'
import { listReportExports } from '../api/reports'
import type { AnalyticsDelayedItem, ProjectOverviewResponse } from '../types/analytics'
import type { ImportBatch } from '../types/import'
import type { Project } from '../types/project'
import type { ReportExportRecord } from '../types/report'

const router = useRouter()
const loading = ref(false)
const errorMessage = ref('')
const projects = ref<Project[]>([])
const selectedProjectId = ref<number | null>(null)
const imports = ref<ImportBatch[]>([])
const reports = ref<ReportExportRecord[]>([])
const projectOverview = ref<ProjectOverviewResponse | null>(null)
const delayed = ref<AnalyticsDelayedItem[]>([])
const openRectifications = ref(0)
const selectedCalculationMethod = ref('')

const currentProject = computed(() => projects.value.find((project) => project.id === selectedProjectId.value) ?? null)
const recentProjects = computed(() => projects.value.slice(0, 4))
const latestBatch = computed(() => imports.value[0] ?? null)
const recentImports = computed(() => imports.value.slice(0, 5))
const delayedRows = computed(() => delayed.value.slice(0, 5))
const severeDelayedCount = computed(() => delayed.value.length)
const openRectificationCount = computed(() => openRectifications.value)
const latestReportText = computed(() => reports.value[0]?.exported_at ? formatDateTime(reports.value[0].exported_at) : '暂无导出记录')
const deviationClass = computed(() => {
  const value = projectOverview.value?.project_deviation
  if (value === null || value === undefined) return ''
  return value < 0 ? 'metric-negative' : 'metric-positive'
})
const aggregateScopeText = computed(() => {
  if (!projectOverview.value || projectOverview.value.empty) return '暂无项目级汇总数据'
  if (projectOverview.value.included_batch_count === 1) return '当前仅检测到 1 个已发布批次，工作台显示该批次进度。'
  return `最新数据日期 ${projectOverview.value.data_date || '-'}，已聚合 ${projectOverview.value.included_batch_count} 个 Sheet`
})
const projectCalculationMethods = computed(() => {
  return (projectOverview.value?.available_methods ?? []).filter((method) => method.code !== 'auto')
})

async function loadWorkbench() {
  loading.value = true
  errorMessage.value = ''
  try {
    projects.value = await listProjects()
    if (!projects.value.length) {
      selectedProjectId.value = null
      return
    }
    const storedId = Number(localStorage.getItem('currentProjectId'))
    const existing = projects.value.find((project) => project.id === storedId)
    selectedProjectId.value = existing?.id ?? projects.value[0].id
    await loadProjectSummary()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '工作台加载失败'
  } finally {
    loading.value = false
  }
}

async function loadProjectSummary() {
  if (!selectedProjectId.value) return
  localStorage.setItem('currentProjectId', String(selectedProjectId.value))
  const projectId = selectedProjectId.value
  const [loadedImports, trend, loadedReports] = await Promise.all([
    listProjectImports(projectId).catch(() => []),
    getAnalyticsTrend(projectId).catch(() => ({ calculation_profile_id: null, rows: [] })),
    listReportExports(projectId).catch(() => []),
  ])
  imports.value = loadedImports
  reports.value = loadedReports
  const batchId = trend.rows.at(-1)?.batch_id ?? null
  projectOverview.value = await getProjectOverview(projectId, null, selectedCalculationMethod.value || null).catch(() => null)
  const rectificationSummary = await getRectificationSummary(projectId, batchId).catch(() => null)
  openRectifications.value = rectificationSummary
    ? rectificationSummary.open + rectificationSummary.in_progress + rectificationSummary.completed
    : 0
  if (!batchId) {
    delayed.value = []
    return
  }
  const loadedDelayed = await getAnalyticsDelayedRanking(projectId, batchId, 5).catch(() => ({ batch_id: batchId, rows: [] }))
  delayed.value = loadedDelayed.rows
}

async function handleProjectChange() {
  loading.value = true
  try {
    await loadProjectSummary()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '项目数据加载失败'
  } finally {
    loading.value = false
  }
}

async function createDemo() {
  try {
    const project = await createDemoProject()
    ElMessage.success('示例项目已创建，请导入 sample_data 中的示例 Excel。')
    router.push(`/projects/${project.id}/import`)
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '示例项目创建失败'
  }
}

async function freezeBatch(batchId: number) {
  try {
    await ElMessageBox.confirm('冻结后该批次不能被同日期同 Sheet 替换，也不能修改人工修正。是否继续？', '冻结批次', {
      confirmButtonText: '确认冻结',
      cancelButtonText: '取消',
      type: 'warning',
    })
    await freezeImportBatch(batchId)
    await loadProjectSummary()
  } catch (error) {
    if (error instanceof Error && error.message) errorMessage.value = error.message
  }
}

async function unfreezeBatch(batchId: number) {
  try {
    await ElMessageBox.confirm('取消冻结后该批次可被替换。是否继续？', '二次确认取消冻结', {
      confirmButtonText: '确认取消冻结',
      cancelButtonText: '取消',
      type: 'warning',
    })
    await unfreezeImportBatch(batchId)
    await loadProjectSummary()
  } catch (error) {
    if (error instanceof Error && error.message) errorMessage.value = error.message
  }
}

function goImport() {
  if (!selectedProjectId.value) {
    ElMessage.warning('请先创建项目或示例项目，再导入 Excel。')
    router.push('/getting-started')
    return
  }
  router.push(`/projects/${selectedProjectId.value}/import`)
}

function goProjectPage(module: string) {
  if (!selectedProjectId.value) {
    ElMessage.warning('请先新建项目，再进入该功能。')
    router.push('/projects/new')
    return
  }
  router.push(`/projects/${selectedProjectId.value}/${module}`)
}

function openProject(projectId: number, module: string) {
  selectedProjectId.value = projectId
  localStorage.setItem('currentProjectId', String(projectId))
  router.push(module === 'maintenance' ? '/maintenance' : `/projects/${projectId}/${module}`)
}

function percentText(value?: number | null) {
  return value === null || value === undefined ? '-' : `${Number(value).toFixed(1)}%`
}

function weightPercentText(value?: number | null) {
  if (value === null || value === undefined) return '-'
  return Number(value).toFixed(4)
}

function signedPercentText(value?: number | null) {
  if (value === null || value === undefined) return '-'
  return `${value > 0 ? '+' : ''}${Number(value).toFixed(1)}%`
}

function formatDateTime(value?: string | null) {
  if (!value) return '-'
  return new Date(value).toLocaleString()
}

function statusText(value: string) {
  const labels: Record<string, string> = {
    draft: '草稿',
    parsed: '已解析',
    validated: '已校验',
    imported: '已导入',
    published: '已发布',
  }
  return labels[value] ?? value
}

function statusTag(value: string) {
  if (value === 'published') return 'success'
  if (value === 'imported' || value === 'validated') return 'warning'
  if (value === 'parsed') return 'info'
  return undefined
}

onMounted(loadWorkbench)
</script>

<style scoped>
.project-overview-scope {
  margin-bottom: 16px;
}

.scope-batch-list {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.scope-warning {
  margin: 10px 0 0;
  color: #92400e;
  font-size: 13px;
}

.overview-actions {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.overview-actions .el-select {
  width: 180px;
}

.scope-meta-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: 10px;
  margin-bottom: 12px;
}

.scope-meta-grid span {
  display: block;
  color: #64748b;
  font-size: 13px;
}

.scope-meta-grid strong {
  display: block;
  margin-top: 4px;
  color: #0f172a;
  font-size: 14px;
}

.recent-project-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
  gap: 12px;
}

.recent-project-card {
  border: 1px solid #dde4ee;
  border-radius: 8px;
  padding: 12px;
  display: grid;
  gap: 12px;
}

.recent-project-card strong,
.recent-project-card span {
  display: block;
}

.recent-project-card span {
  margin-top: 4px;
  color: #64748b;
  font-size: 13px;
}
</style>
