<template>
  <main class="page-shell dashboard-shell">
    <section class="page-heading">
      <div>
        <p class="eyebrow">warnings</p>
        <h1>预警中心</h1>
      </div>
      <div class="toolbar">
        <el-button @click="router.push(`/projects/${projectId}`)">项目详情</el-button>
        <el-button :loading="exporting" :disabled="exporting || !selectedBatchId" @click="exportCurrentWarnings">导出预警</el-button>
        <el-button type="primary" :loading="running" :disabled="running || !selectedBatchId" @click="runCurrentWarnings">运行预警</el-button>
      </div>
    </section>

    <el-alert v-if="errorMessage" :title="errorMessage" type="error" show-icon :closable="false" />

    <section class="form-surface dashboard-controls warning-filters">
      <el-form-item label="发布批次">
        <el-select v-model="selectedBatchId" placeholder="最近发布批次" clearable @change="handleBatchChange">
          <el-option v-for="batch in batchOptions" :key="batch.batch_id" :label="batchLabel(batch)" :value="batch.batch_id" />
        </el-select>
      </el-form-item>
      <el-form-item label="专业">
        <el-select v-model="filters.discipline" clearable placeholder="全部专业" @change="loadRecords">
          <el-option v-for="item in disciplineOptions" :key="item" :label="item" :value="item" />
        </el-select>
      </el-form-item>
      <el-form-item label="楼栋">
        <el-select v-model="filters.building" clearable placeholder="全部楼栋" @change="handleBuildingChange">
          <el-option v-for="item in buildingOptions" :key="item" :label="item" :value="item" />
        </el-select>
      </el-form-item>
      <el-form-item label="楼层">
        <el-select v-model="filters.floor" clearable placeholder="全部楼层" @change="loadRecords">
          <el-option v-for="item in filteredFloorOptions" :key="item" :label="item" :value="item" />
        </el-select>
      </el-form-item>
      <el-form-item label="预警级别">
        <el-select v-model="filters.level" clearable placeholder="全部级别" @change="loadRecords">
          <el-option label="严重预警" value="critical" />
          <el-option label="一般预警" value="warning" />
          <el-option label="提示" value="info" />
        </el-select>
      </el-form-item>
      <el-form-item label="处理状态">
        <el-select v-model="filters.status" clearable placeholder="全部状态" @change="loadRecords">
          <el-option label="未处理" value="open" />
          <el-option label="已处理" value="handled" />
          <el-option label="已忽略" value="ignored" />
        </el-select>
      </el-form-item>
      <el-form-item label="关键词">
        <el-input v-model="filters.keyword" clearable placeholder="施工项 / 预警说明" @keyup.enter="loadRecords" @clear="loadRecords" />
      </el-form-item>
      <el-form-item label="只看未处理">
        <el-switch v-model="unresolvedOnly" @change="loadRecords" />
      </el-form-item>
      <el-button type="primary" :loading="loading" :disabled="loading" @click="loadRecords">查询</el-button>
      <el-button :disabled="loading" @click="resetFilters">重置</el-button>
    </section>

    <section class="table-surface">
      <div class="section-title">
        <h2>预警规则</h2>
        <span>{{ rules.length }} 条</span>
      </div>
      <el-table :data="rules" height="300">
        <el-table-column prop="name" label="规则" min-width="220" />
        <el-table-column prop="rule_type" label="类型" min-width="190" />
        <el-table-column label="级别" width="120">
          <template #default="{ row }">{{ levelLabel(row.level) }}</template>
        </el-table-column>
        <el-table-column prop="threshold_value" label="阈值" width="110" />
        <el-table-column label="启用" width="110">
          <template #default="{ row }">
            <el-switch v-model="row.is_enabled" @change="toggleRule(row)" />
          </template>
        </el-table-column>
      </el-table>
    </section>

    <section class="table-surface">
      <div class="section-title">
        <h2>预警记录</h2>
        <span>{{ records.length }} 条</span>
      </div>
      <el-empty v-if="!loading && !records.length" description="当前没有预警记录，说明当前筛选范围内暂无明显进度风险。">
        <el-button type="primary" :loading="running" :disabled="running || !selectedBatchId" @click="runCurrentWarnings">运行预警</el-button>
        <el-button @click="router.push(`/projects/${projectId}/dashboard`)">返回 Dashboard</el-button>
      </el-empty>
      <template v-else>
        <div class="batch-panel">
          <span>已选 {{ selectedRows.length }} 项</span>
          <el-button :disabled="!selectedRows.length || batchUpdating" :loading="batchUpdating" type="primary" @click="batchMarkResolution('handled')">
            批量标记已处理
          </el-button>
          <el-button :disabled="!selectedRows.length || batchUpdating" :loading="batchUpdating" type="warning" plain @click="batchMarkResolution('ignored')">
            批量忽略
          </el-button>
          <el-button :disabled="!batchCreatableRows.length || batchCreating" :loading="batchCreating" type="primary" plain @click="batchCreateRectifications">
            批量生成整改项（{{ batchCreatableRows.length }}）
          </el-button>
          <el-button :disabled="!selectedRows.length" @click="clearSelection">清除选择</el-button>
          <span v-if="selectedRows.length && batchCreatableRows.length < selectedRows.length" class="hint">
            {{ selectedRows.length - batchCreatableRows.length }} 项已存在整改项，将跳过
          </span>
        </div>
        <el-table ref="recordsTableRef" v-loading="loading" :data="records" height="560" empty-text="当前没有预警记录，说明当前筛选范围内暂无明显进度风险。" @row-click="openDetail" @selection-change="selectedRows = $event">
        <el-table-column type="selection" width="42" />
        <el-table-column label="级别" width="110">
          <template #default="{ row }">
            <el-tag :type="row.level_label === '严重预警' ? 'danger' : row.level_label === '提示' ? 'info' : 'warning'">
              {{ row.level_label ?? levelLabel(row.level) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="statusTagType(row.status)" effect="plain">{{ row.status_label ?? statusLabel(row.status) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="discipline" label="专业" width="120" />
        <el-table-column prop="building" label="楼栋" width="110" />
        <el-table-column prop="floor" label="楼层" width="110" />
        <el-table-column prop="system_name" label="系统" min-width="140" show-overflow-tooltip />
        <el-table-column prop="task_name" label="施工项" min-width="180" show-overflow-tooltip />
        <el-table-column label="实际%" width="100">
          <template #default="{ row }">{{ percentText(row.actual_percent) }}</template>
        </el-table-column>
        <el-table-column label="应完成%" width="100">
          <template #default="{ row }">{{ percentText(row.planned_percent) }}</template>
        </el-table-column>
        <el-table-column label="偏差" width="100">
          <template #default="{ row }">{{ percentText(row.progress_deviation) }}</template>
        </el-table-column>
        <el-table-column label="预警说明" min-width="360" show-overflow-tooltip>
          <template #default="{ row }">{{ row.warning_message || row.message || '-' }}</template>
        </el-table-column>
        <el-table-column label="触发时间" width="170">
          <template #default="{ row }">{{ formatDateTime(row.created_at) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="210" fixed="right">
          <template #default="{ row }">
            <el-button v-if="row.status === 'open'" size="small" @click.stop="markResolution(row, 'handled')">处理</el-button>
            <el-button v-else size="small" plain @click.stop="markResolution(row, null)">取消处理</el-button>
            <el-button v-if="row.has_rectification" size="small" type="primary" @click.stop="router.push(`/projects/${projectId}/rectifications?keyword=${encodeURIComponent(row.task_name || '')}`)">查看整改项</el-button>
            <el-button v-else size="small" @click.stop="createFromWarning(row)">生成整改项</el-button>
          </template>
        </el-table-column>
      </el-table>
      <el-pagination
        v-if="totalRecords"
        v-model:current-page="page"
        v-model:page-size="pageSize"
        class="table-pagination"
        layout="total, sizes, prev, pager, next"
        :total="totalRecords"
        :page-sizes="[20, 50, 100, 200]"
        @current-change="loadRecords"
        @size-change="onPageSizeChange"
      />
      </template>
    </section>

    <el-dialog v-model="detailVisible" title="预警详情" width="720px">
      <div v-if="selectedRecord" class="warning-detail">
        <div><span>预警级别：</span><strong>{{ selectedRecord.level_label }}</strong></div>
        <div><span>处理状态：</span><strong>{{ selectedRecord.status_label }}</strong></div>
        <div><span>专业：</span><strong>{{ selectedRecord.discipline || '未填写专业' }}</strong></div>
        <div><span>楼栋：</span><strong>{{ selectedRecord.building || '未填写楼栋' }}</strong></div>
        <div><span>楼层：</span><strong>{{ selectedRecord.floor || '未填写楼层' }}</strong></div>
        <div><span>系统：</span><strong>{{ selectedRecord.system_name || '未填写系统' }}</strong></div>
        <div><span>施工项：</span><strong>{{ selectedRecord.task_name || '未填写施工项' }}</strong></div>
        <div><span>实际完成率：</span><strong>{{ percentText(selectedRecord.actual_percent) }}</strong></div>
        <div><span>应完成率：</span><strong>{{ percentText(selectedRecord.planned_percent) }}</strong></div>
        <div><span>进度偏差：</span><strong>{{ percentText(selectedRecord.progress_deviation) }}</strong></div>
        <div><span>预警规则：</span><strong>{{ selectedRecord.rule_name || '-' }}</strong></div>
        <div class="detail-wide"><span>预警说明：</span><p>{{ selectedRecord.warning_message || selectedRecord.message || '-' }}</p></div>
        <div><span>触发时间：</span><strong>{{ formatDateTime(selectedRecord.created_at) }}</strong></div>
        <div class="detail-wide"><span>处理备注：</span><p>{{ selectedRecord.remark || '-' }}</p></div>
      </div>
    </el-dialog>
  </main>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'

import { getAnalyticsTrend } from '../api/analytics'
import { createRectificationFromWarning } from '../api/rectifications'
import {
  batchUpdateWarnings,
  exportWarnings,
  listWarningFilterOptions,
  listWarningRules,
  listWarningsPage,
  runWarnings,
  updateWarningRule,
  updateWarningStatus,
} from '../api/warnings'
import type { AnalyticsTrendPoint } from '../types/analytics'
import type { WarningFilterOptions, WarningFilters, WarningRecord, WarningResolutionType, WarningRule } from '../types/warning'

const route = useRoute()
const router = useRouter()
const projectId = Number(route.params.id)

const batchOptions = ref<AnalyticsTrendPoint[]>([])
const selectedBatchId = ref<number | null>(null)
const unresolvedOnly = ref(false)
const rules = ref<WarningRule[]>([])
const records = ref<WarningRecord[]>([])
const totalRecords = ref(0)
const filterOptions = ref<WarningFilterOptions>({
  disciplines: [],
  buildings: [],
  floors: [],
  floors_by_building: {},
})
const loading = ref(false)
const running = ref(false)
const exporting = ref(false)
const page = ref(1)
const pageSize = ref(20)
const errorMessage = ref('')
const detailVisible = ref(false)
const selectedRecord = ref<WarningRecord | null>(null)
const selectedRows = ref<WarningRecord[]>([])
const batchCreating = ref(false)
const batchUpdating = ref(false)
const recordsTableRef = ref<{ clearSelection: () => void } | null>(null)
const filters = reactive<WarningFilters>({
  discipline: '',
  building: '',
  floor: '',
  level: '',
  status: '',
  keyword: '',
})

const disciplineOptions = computed(() => filterOptions.value.disciplines)
const buildingOptions = computed(() => filterOptions.value.buildings)
const filteredFloorOptions = computed(() => {
  if (filters.building) {
    return filterOptions.value.floors_by_building[filters.building] ?? []
  }
  return filterOptions.value.floors
})
const pagedRecords = computed(() => records.value)
const batchCreatableRows = computed(() => selectedRows.value.filter((row) => !row.has_rectification))

function batchLabel(batch: AnalyticsTrendPoint) {
  const date = batch.data_date || batch.published_at?.slice(0, 10) || `批次 ${batch.batch_id}`
  const sheet = batch.sheet_name || `#${batch.batch_id}`
  const baseline = batch.baseline_plan_name || '未配置计划基线'
  return `${date}｜${sheet}｜计划基线：${baseline}`
}

async function loadAll() {
  try {
    const [trend, loadedRules] = await Promise.all([getAnalyticsTrend(projectId), listWarningRules(projectId)])
    batchOptions.value = trend.rows
    selectedBatchId.value = trend.rows.at(-1)?.batch_id ?? null
    rules.value = loadedRules
    await loadOptionRecords()
    await loadRecords()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '预警中心加载失败'
  }
}

async function loadOptionRecords() {
  filterOptions.value = await listWarningFilterOptions(projectId, selectedBatchId.value)
}

async function handleBatchChange() {
  await Promise.all([loadOptionRecords(), loadRecords()])
}

async function loadRecords() {
  loading.value = true
  try {
    const result = await listWarningsPage(projectId, {
      batchId: selectedBatchId.value,
      unresolvedOnly: unresolvedOnly.value,
      filters,
      limit: pageSize.value,
      offset: (page.value - 1) * pageSize.value,
    })
    records.value = result.records
    totalRecords.value = result.total
    if (page.value > 1 && !result.records.length && result.total > 0) {
      page.value = 1
      await loadRecords()
    }
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '预警记录加载失败'
  } finally {
    loading.value = false
  }
}

function onPageSizeChange(size: number) {
  pageSize.value = size
  page.value = 1
  void loadRecords()
}

async function runCurrentWarnings() {
  running.value = true
  errorMessage.value = ''
  try {
    await runWarnings(projectId, selectedBatchId.value)
    await Promise.all([loadOptionRecords(), loadRecords()])
    ElMessage.success('预警规则已运行')
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '运行预警失败'
  } finally {
    running.value = false
  }
}

async function toggleRule(rule: WarningRule) {
  try {
    await updateWarningRule(rule.id, { is_enabled: rule.is_enabled })
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '规则保存失败'
  }
}

async function exportCurrentWarnings() {
  exporting.value = true
  errorMessage.value = ''
  try {
    const blob = await exportWarnings(projectId, selectedBatchId.value, unresolvedOnly.value, filters)
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = `预警记录_${new Date().toISOString().slice(0, 10)}.xlsx`
    link.click()
    URL.revokeObjectURL(url)
    ElMessage.success('预警记录已导出')
  } catch (error) {
    errorMessage.value = `导出预警记录失败：${error instanceof Error ? error.message : '文件生成异常，请查看诊断日志。'}`
  } finally {
    exporting.value = false
  }
}

function handleBuildingChange() {
  if (filters.floor && !filteredFloorOptions.value.includes(filters.floor)) {
    filters.floor = ''
  }
  loadRecords()
}

function resetFilters() {
  Object.assign(filters, { discipline: '', building: '', floor: '', level: '', status: '', keyword: '' })
  unresolvedOnly.value = false
  page.value = 1
  loadRecords()
}

function openDetail(record: WarningRecord) {
  selectedRecord.value = record
  detailVisible.value = true
}

async function createFromWarning(record: WarningRecord) {
  try {
    const result = await createRectificationFromWarning(projectId, record.id)
    ElMessage.success(result.message)
    router.push(`/projects/${projectId}/rectifications?keyword=${encodeURIComponent(result.item.task_name || '')}`)
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '生成整改项失败'
  }
}

async function batchCreateRectifications() {
  const targets = batchCreatableRows.value
  if (!targets.length) return
  batchCreating.value = true
  errorMessage.value = ''
  try {
    const results = await Promise.allSettled(targets.map((row) => createRectificationFromWarning(projectId, row.id)))
    const ok = results.filter((r) => r.status === 'fulfilled').length
    const fail = results.length - ok
    if (ok && !fail) {
      ElMessage.success(`已批量生成 ${ok} 条整改项`)
    } else if (ok && fail) {
      ElMessage.warning(`成功 ${ok} 条，失败 ${fail} 条`)
    } else {
      ElMessage.error('批量生成整改项失败')
    }
    clearSelection()
    await loadRecords()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '批量生成整改项失败'
  } finally {
    batchCreating.value = false
  }
}

function clearSelection() {
  recordsTableRef.value?.clearSelection()
  selectedRows.value = []
}

async function markResolution(row: WarningRecord, type: WarningResolutionType) {
  try {
    const updated = await updateWarningStatus(projectId, row.id, { resolution_type: type })
    Object.assign(row, updated)
    ElMessage.success(type ? '已更新预警状态' : '已取消处理')
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '更新预警状态失败'
  }
}

async function batchMarkResolution(type: WarningResolutionType) {
  if (!selectedRows.value.length) return
  batchUpdating.value = true
  errorMessage.value = ''
  try {
    const ids = selectedRows.value.map((r) => r.id)
    const result = await batchUpdateWarnings(projectId, { ids, resolution_type: type })
    ElMessage.success(`已更新 ${result.updated_count} 条预警`)
    clearSelection()
    await loadRecords()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '批量更新失败'
  } finally {
    batchUpdating.value = false
  }
}

function statusTagType(status?: string | null) {
  if (status === 'handled') return 'success'
  if (status === 'ignored') return 'info'
  return 'warning'
}

function levelLabel(level?: string | null) {
  const value = (level || '').toLowerCase()
  if (['serious', 'critical', 'high'].includes(value)) return '严重预警'
  if (['warning', 'medium'].includes(value)) return '一般预警'
  if (['info', 'low'].includes(value)) return '提示'
  return '一般预警'
}

function statusLabel(status?: string | null) {
  const value = (status || '').toLowerCase()
  if (['open', 'unhandled'].includes(value)) return '未处理'
  if (value === 'handled') return '已处理'
  if (value === 'ignored') return '已忽略'
  return '未处理'
}

function percentText(value?: number | null) {
  if (value === null || value === undefined) return '-'
  return `${value.toFixed(1)}%`
}

function formatDateTime(value?: string | null) {
  return value ? value.replace('T', ' ').slice(0, 16) : '-'
}

onMounted(loadAll)
</script>

<style scoped>
.warning-filters {
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
}

.batch-panel {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 10px 14px;
  margin-bottom: 12px;
  background: #f8fafc;
  border-radius: 10px;
  font-size: 13px;
  color: #475569;
}

.batch-panel .hint {
  color: #94a3b8;
  font-size: 12px;
  margin-left: auto;
}

.warning-detail {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 14px 20px;
}

.warning-detail div {
  min-width: 0;
}

.warning-detail span {
  color: #64748b;
}

.warning-detail strong {
  color: #0f172a;
  font-weight: 600;
  overflow-wrap: anywhere;
}

.warning-detail p {
  margin: 6px 0 0;
  color: #0f172a;
  line-height: 1.7;
}

.detail-wide {
  grid-column: 1 / -1;
}
</style>
