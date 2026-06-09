<template>
  <main class="page-shell dashboard-shell">
    <section class="page-heading">
      <div>
        <p class="eyebrow">progress items</p>
        <h1>进度明细</h1>
      </div>
      <div class="toolbar">
        <el-button @click="router.push(`/projects/${projectId}`)">项目详情</el-button>
        <el-button type="primary" :loading="loading" :disabled="loading" @click="loadItems">刷新</el-button>
      </div>
    </section>

    <el-alert v-if="errorMessage" :title="errorMessage" type="error" show-icon :closable="false" />

    <section v-if="scopeInfo" class="form-surface scope-panel">
      <div>
        <span>当前范围</span>
        <strong>{{ scopeTitle }}</strong>
      </div>
      <div v-if="scopeInfo.data_date">
        <span>数据日期</span>
        <strong>{{ scopeInfo.data_date }}</strong>
      </div>
      <div>
        <span>包含 Sheet</span>
        <strong>{{ scopeSheetsText }}</strong>
      </div>
      <div>
        <span>包含批次</span>
        <strong>{{ scopeBatchText }}</strong>
      </div>
      <div>
        <span>任务数</span>
        <strong>{{ scopeInfo.task_count }}</strong>
      </div>
      <p>{{ activeScopeFiltersText }}</p>
    </section>

    <section class="form-surface item-filters">
      <el-form-item label="已发布批次">
        <el-select v-model="selectedBatchId" :disabled="isProjectScope" :placeholder="isProjectScope ? '项目级聚合' : '选择批次'" @change="handleBatchChange">
          <el-option
            v-for="batch in batchOptions"
            :key="batch.batch_id"
            :label="batchLabel(batch)"
            :value="batch.batch_id"
          />
        </el-select>
      </el-form-item>
      <el-form-item label="施工单位">
        <el-select v-model="filters.constructionUnit" clearable placeholder="全部施工单位" @change="handleFilterChange">
          <el-option v-for="unit in constructionUnitOptions" :key="unit" :label="unit" :value="unit" />
        </el-select>
      </el-form-item>
      <el-form-item label="楼栋">
        <el-select v-model="filters.building" clearable placeholder="全部楼栋" @change="handleBuildingFilterChange">
          <el-option v-for="building in buildingOptions" :key="building" :label="building" :value="building" />
        </el-select>
      </el-form-item>
      <el-form-item label="楼层">
        <el-select v-model="filters.floor" clearable placeholder="全部楼层" @change="handleFilterChange">
          <el-option v-for="floor in floorOptions" :key="floor" :label="floor" :value="floor" />
        </el-select>
      </el-form-item>
      <el-form-item label="专业">
        <el-select v-model="filters.discipline" clearable placeholder="全部专业" @change="handleFilterChange">
          <el-option v-for="discipline in disciplineOptions" :key="discipline" :label="discipline" :value="discipline" />
        </el-select>
      </el-form-item>
      <el-form-item label="系统">
        <el-select v-model="filters.systemName" clearable placeholder="全部系统" @change="handleFilterChange">
          <el-option v-for="systemName in systemOptions" :key="systemName" :label="systemName" :value="systemName" />
        </el-select>
      </el-form-item>
      <el-form-item label="状态">
        <el-select v-model="filters.status" clearable placeholder="全部状态" @change="handleFilterChange">
          <el-option v-for="status in statusOptions" :key="status" :label="statusLabel(status)" :value="status" />
        </el-select>
      </el-form-item>
      <el-form-item label="关键词">
        <el-input v-model="filters.keyword" clearable placeholder="任务 / 编码 / 系统" @keyup.enter="handleFilterChange" @clear="handleFilterChange" />
      </el-form-item>
      <div class="filter-actions">
        <el-button type="primary" @click="handleFilterChange">查询</el-button>
        <el-button @click="resetFilters">重置</el-button>
      </div>
    </section>

    <section class="table-surface">
      <div class="section-title">
        <h2>明细列表</h2>
        <span>{{ total }} 条</span>
      </div>
      <el-table :data="items" height="560" v-loading="loading" empty-text="当前筛选条件下暂无进度明细。请调整筛选条件或确认批次已发布。">
        <el-table-column prop="construction_unit" label="施工单位" width="150" fixed show-overflow-tooltip />
        <el-table-column prop="building" label="楼栋" width="100" />
        <el-table-column prop="floor" label="楼层" width="100" />
        <el-table-column prop="discipline" label="专业" width="100" />
        <el-table-column prop="system_name" label="系统" min-width="130" show-overflow-tooltip />
        <el-table-column prop="task_name" label="任务" min-width="220" show-overflow-tooltip />
        <el-table-column label="单位" width="80">
          <template #default="{ row }">{{ emptyText(row.unit) }}</template>
        </el-table-column>
        <el-table-column label="总量" width="100">
          <template #default="{ row }">{{ numberText(row.total_quantity) }}</template>
        </el-table-column>
        <el-table-column label="计划量" width="100">
          <template #default="{ row }">{{ numberText(row.planned_quantity) }}</template>
        </el-table-column>
        <el-table-column label="实际量" width="100">
          <template #default="{ row }">{{ numberText(row.actual_quantity ?? row.cumulative_quantity) }}</template>
        </el-table-column>
        <el-table-column label="实际%" width="100">
          <template #default="{ row }">{{ percentText(row.actual_percent) }}</template>
        </el-table-column>
        <el-table-column label="应完成%" width="100">
          <template #default="{ row }">{{ percentText(row.planned_percent) }}</template>
        </el-table-column>
        <el-table-column label="偏差" width="100">
          <template #default="{ row }">{{ signedPercentText(row.progress_deviation) }}</template>
        </el-table-column>
        <el-table-column label="状态" width="140">
          <template #default="{ row }">{{ statusLabel(row.status) }}</template>
        </el-table-column>
        <el-table-column label="人工修正" width="100">
          <template #default="{ row }">
            <el-tag :type="row.is_manually_edited ? 'warning' : 'info'">{{ row.is_manually_edited ? '是' : '否' }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="240" fixed="right">
          <template #default="{ row }">
            <el-button size="small" @click="openEdit(row)">编辑</el-button>
            <el-button size="small" @click="openHistory(row)">历史</el-button>
            <el-button
              v-if="row.is_manually_edited"
              size="small"
              type="warning"
              :loading="undoingItemId === row.id"
              @click="undoEdit(row)"
            >撤销</el-button>
          </template>
        </el-table-column>
      </el-table>
      <div class="table-actions actions-row">
        <el-pagination
          layout="prev, pager, next, sizes, total"
          :total="total"
          v-model:current-page="page"
          v-model:page-size="pageSize"
          :page-sizes="[20, 50, 100]"
          @change="loadItems"
        />
      </div>
    </section>

    <el-drawer v-model="editVisible" title="人工修正" size="520px">
      <el-form label-position="top">
        <div class="form-grid">
          <el-form-item label="总工程量"><el-input-number v-model="editForm.total_quantity" /></el-form-item>
          <el-form-item label="计划完成量"><el-input-number v-model="editForm.planned_quantity" /></el-form-item>
          <el-form-item label="实际完成量"><el-input-number v-model="editForm.actual_quantity" /></el-form-item>
          <el-form-item label="累计完成量"><el-input-number v-model="editForm.cumulative_quantity" /></el-form-item>
          <el-form-item label="本期完成量"><el-input-number v-model="editForm.period_quantity" /></el-form-item>
          <el-form-item label="实际上报完成率"><el-input-number v-model="editForm.reported_percent" /></el-form-item>
          <el-form-item label="计划开始"><el-date-picker v-model="editForm.planned_start_date" value-format="YYYY-MM-DD" /></el-form-item>
          <el-form-item label="计划完成"><el-date-picker v-model="editForm.planned_finish_date" value-format="YYYY-MM-DD" /></el-form-item>
        </div>
        <el-form-item label="备注"><el-input v-model="editForm.remark" type="textarea" /></el-form-item>
        <el-form-item label="修改原因">
          <el-input v-model="editForm.reason" type="textarea" placeholder="必须填写修改原因" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="editVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="saveEdit">保存并重算</el-button>
      </template>
    </el-drawer>

    <el-drawer v-model="historyVisible" title="修改历史" size="620px">
      <el-table :data="historyRows" height="560">
        <el-table-column prop="field_name" label="字段" width="150" />
        <el-table-column prop="old_value" label="旧值" min-width="130" />
        <el-table-column prop="new_value" label="新值" min-width="130" />
        <el-table-column prop="reason" label="原因" min-width="220" />
        <el-table-column prop="edited_at" label="时间" width="170" />
      </el-table>
    </el-drawer>
  </main>
</template>

<script setup lang="ts">
import { computed, nextTick, onMounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'

import { getAnalyticsTrend } from '../api/analytics'
import { getProgressItemHistory, listProgressItemFilterOptions, listProgressItems, undoLastProgressItemEdit, updateProgressItem } from '../api/progressItems'
import type { AnalyticsTrendPoint } from '../types/analytics'
import type { ProgressItem, ProgressItemEditHistory, ProgressItemFilterOptions, ProgressItemPayload, ProgressItemScopeInfo } from '../types/progressItem'

const route = useRoute()
const router = useRouter()
const projectId = Number(route.params.id)

const batchOptions = ref<AnalyticsTrendPoint[]>([])
const selectedBatchId = ref<number | null>(null)
const queryScope = ref('')
const queryDataDate = ref('')
const queryImportGroupId = ref('')
const queryBatchIds = ref('')
const previousSelectedBatchId = ref<number | null>(null)
const items = ref<ProgressItem[]>([])
const filterOptions = ref<ProgressItemFilterOptions>({
  construction_units: [],
  buildings: [],
  floors: [],
  disciplines: [],
  system_names: [],
  statuses: [],
  floors_by_building: {},
})
const scopeInfo = ref<ProgressItemScopeInfo | null>(null)
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)
const loading = ref(false)
const initializing = ref(true)
const saving = ref(false)
const errorMessage = ref('')
const editVisible = ref(false)
const historyVisible = ref(false)
const currentItem = ref<ProgressItem | null>(null)
const historyRows = ref<ProgressItemEditHistory[]>([])
const undoingItemId = ref<number | null>(null)
const filters = reactive({
  constructionUnit: '',
  building: '',
  floor: '',
  discipline: '',
  systemName: '',
  status: '',
  keyword: '',
})

const editForm = reactive<ProgressItemPayload>({
  reason: '',
})

function batchLabel(batch: AnalyticsTrendPoint) {
  const date = batch.data_date || batch.published_at?.slice(0, 10) || `批次 ${batch.batch_id}`
  const sheet = batch.sheet_name || `#${batch.batch_id}`
  const baseline = batch.baseline_plan_name || '未配置计划基线'
  return `${date}｜${sheet}｜计划基线：${baseline}`
}

const buildingOptions = computed(() => filterOptions.value.buildings)
const constructionUnitOptions = computed(() => filterOptions.value.construction_units)
const floorOptions = computed(() => {
  if (filters.building) {
    return filterOptions.value.floors_by_building[filters.building] ?? []
  }
  return filterOptions.value.floors
})
const disciplineOptions = computed(() => filterOptions.value.disciplines)
const systemOptions = computed(() => filterOptions.value.system_names)
const statusOptions = computed(() => filterOptions.value.statuses)
const isProjectScope = computed(() => queryScope.value === 'project')
const scopeTitle = computed(() => scopeInfo.value?.scope === 'project' ? '项目级聚合明细' : '单批次明细')
const scopeSheetsText = computed(() => safeJoin(scopeInfo.value?.included_sheets))
const scopeBatchText = computed(() => safeJoin((scopeInfo.value?.included_batch_ids ?? []).map(String)))
const activeScopeFiltersText = computed(() => {
  const rows = [
    filters.building && `楼栋 ${filters.building}`,
    filters.floor && `楼层 ${filters.floor}`,
    filters.discipline && `专业 ${filters.discipline}`,
    filters.systemName && `系统 ${filters.systemName}`,
    filters.constructionUnit && `施工单位 ${filters.constructionUnit}`,
    filters.status && `状态 ${statusLabel(filters.status)}`,
  ].filter(Boolean)
  return rows.length ? `筛选条件：${rows.join(' / ')}` : '筛选条件：全部'
})

function floorSortKey(value: string): [number, number, string] {
  if (value === '未填写楼层') return [8, 0, value]
  const undergroundText = value.match(/^地下\s*(\d+)/)
  if (undergroundText) return [0, -Number(undergroundText[1]), value]
  const basementText = value.match(/^[Bb]\s*(\d+)/)
  if (basementText) return [1, -Number(basementText[1]), value]
  const abovegroundText = value.match(/^(\d+)\s*层?$/)
  if (abovegroundText) return [2, Number(abovegroundText[1]), value]
  return [6, 0, value]
}

function compareFloor(a: string, b: string) {
  const left = floorSortKey(a)
  const right = floorSortKey(b)
  return left[0] - right[0] || left[1] - right[1] || left[2].localeCompare(right[2], 'zh-Hans-CN', { numeric: true })
}

function emptyText(value?: string | null) {
  return value || '-'
}

function safeJoin(values?: Array<string | null | undefined>) {
  const rows = (values ?? []).filter((value): value is string => Boolean(value))
  return rows.length ? rows.join('、') : '-'
}

function numberText(value?: number | null) {
  return value === null || value === undefined ? '-' : String(value)
}

function percentText(value?: number | null) {
  return value === null || value === undefined ? '-' : `${Number(value).toFixed(1)}%`
}

function signedPercentText(value?: number | null) {
  if (value === null || value === undefined) return '-'
  return `${value > 0 ? '+' : ''}${Number(value).toFixed(1)}%`
}

function statusLabel(value?: string | null) {
  const labels: Record<string, string> = {
    completed: '已完成',
    ahead: '超前',
    normal: '正常',
    slightly_delayed: '轻微滞后',
    delayed: '明显滞后',
    delayed_or_worse: '明显及以上滞后',
    any_delayed: '全部滞后',
    seriously_delayed: '严重滞后',
    seriously_delay: '严重滞后',
    not_started_by_plan: '未到计划开始',
    missing_plan_dates: '缺少计划日期',
    invalid_plan_dates: '计划日期异常',
    unknown: '未知',
  }
  return labels[value || 'unknown'] ?? value ?? '未知'
}

async function loadInitial() {
  try {
    const trend = await getAnalyticsTrend(projectId)
    batchOptions.value = trend.rows
    const queryBatchId = Number(route.query.batch_id)
    queryScope.value = typeof route.query.scope === 'string' ? route.query.scope : ''
    queryDataDate.value = typeof route.query.data_date === 'string' ? route.query.data_date : ''
    queryImportGroupId.value = typeof route.query.import_group_id === 'string' ? route.query.import_group_id : ''
    queryBatchIds.value = typeof route.query.batch_ids === 'string' ? route.query.batch_ids : ''
    filters.building = typeof route.query.building === 'string' ? route.query.building : ''
    filters.constructionUnit = typeof route.query.construction_unit === 'string' ? route.query.construction_unit : ''
    filters.floor = typeof route.query.floor === 'string' ? route.query.floor : ''
    filters.discipline = typeof route.query.discipline === 'string' ? route.query.discipline : ''
    filters.systemName = typeof route.query.system_name === 'string' ? route.query.system_name : ''
    filters.status = typeof route.query.status === 'string' ? route.query.status : ''
    filters.keyword = typeof route.query.keyword === 'string' ? route.query.keyword : ''
    selectedBatchId.value = isProjectScope.value ? null : Number.isFinite(queryBatchId) && queryBatchId > 0 ? queryBatchId : trend.rows.at(-1)?.batch_id ?? null
    previousSelectedBatchId.value = selectedBatchId.value
    await loadFilterOptions()
    await loadItems()
    await nextTick()
    initializing.value = false
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '进度明细加载失败'
    initializing.value = false
  }
}

async function loadFilterOptions() {
  if (!selectedBatchId.value && !isProjectScope.value) {
    filterOptions.value = {
      construction_units: [],
      buildings: [],
      floors: [],
      disciplines: [],
      system_names: [],
      statuses: [],
      floors_by_building: {},
    }
    return
  }
  const response = await listProgressItemFilterOptions(projectId, {
    batchId: selectedBatchId.value,
    ...scopeParams(),
  })
  filterOptions.value = {
    ...response,
    floors: [...response.floors].sort(compareFloor),
    floors_by_building: Object.fromEntries(
      Object.entries(response.floors_by_building).map(([building, floors]) => [
        building,
        [...floors].sort(compareFloor),
      ]),
    ),
  }
}

async function loadItems() {
  loading.value = true
  errorMessage.value = ''
  try {
    const response = await listProgressItems(projectId, {
      batchId: selectedBatchId.value,
      ...scopeParams(),
      constructionUnit: filters.constructionUnit,
      building: filters.building,
      floor: filters.floor,
      discipline: filters.discipline,
      systemName: filters.systemName,
      status: filters.status,
      keyword: filters.keyword.trim(),
      page: page.value,
      pageSize: pageSize.value,
    })
    items.value = response.items
    total.value = response.total
    scopeInfo.value = response.scope_info ?? null
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '进度明细加载失败'
  } finally {
    loading.value = false
  }
}

function syncQuery() {
  router.replace({
    path: route.path,
    query: {
      ...(selectedBatchId.value ? { batch_id: String(selectedBatchId.value) } : {}),
      ...(queryScope.value ? { scope: queryScope.value } : {}),
      ...(queryDataDate.value ? { data_date: queryDataDate.value } : {}),
      ...(queryImportGroupId.value ? { import_group_id: queryImportGroupId.value } : {}),
      ...(queryBatchIds.value ? { batch_ids: queryBatchIds.value } : {}),
      ...(filters.constructionUnit ? { construction_unit: filters.constructionUnit } : {}),
      ...(filters.building ? { building: filters.building } : {}),
      ...(filters.floor ? { floor: filters.floor } : {}),
      ...(filters.discipline ? { discipline: filters.discipline } : {}),
      ...(filters.systemName ? { system_name: filters.systemName } : {}),
      ...(filters.status ? { status: filters.status } : {}),
      ...(filters.keyword.trim() ? { keyword: filters.keyword.trim() } : {}),
    },
  })
}

async function handleBatchChange() {
  if (isProjectScope.value) return
  if (initializing.value) return
  const queryBatchId = Number(route.query.batch_id)
  const hasQueryFilters = Boolean(route.query.building || route.query.floor || route.query.discipline || route.query.system_name || route.query.status || route.query.keyword)
  if (hasQueryFilters && queryBatchId === selectedBatchId.value) {
    previousSelectedBatchId.value = selectedBatchId.value
    return
  }
  if (selectedBatchId.value === previousSelectedBatchId.value) return
  previousSelectedBatchId.value = selectedBatchId.value
  page.value = 1
  filters.building = ''
  filters.floor = ''
  await loadFilterOptions()
  syncQuery()
  await loadItems()
}

function scopeParams() {
  return {
    scope: queryScope.value || null,
    dataDate: queryDataDate.value || null,
    importGroupId: queryImportGroupId.value || null,
    batchIds: queryBatchIds.value || null,
  }
}

async function handleBuildingFilterChange() {
  page.value = 1
  if (filters.floor && !floorOptions.value.includes(filters.floor)) {
    filters.floor = ''
  }
  syncQuery()
  await loadItems()
}

async function handleFilterChange() {
  page.value = 1
  syncQuery()
  await loadItems()
}

async function resetFilters() {
  Object.assign(filters, {
    building: '',
    constructionUnit: '',
    floor: '',
    discipline: '',
    systemName: '',
    status: '',
    keyword: '',
  })
  page.value = 1
  syncQuery()
  await loadItems()
}

function openEdit(item: ProgressItem) {
  currentItem.value = item
  Object.assign(editForm, {
    reason: '',
    total_quantity: item.total_quantity,
    planned_quantity: item.planned_quantity,
    actual_quantity: item.actual_quantity,
    cumulative_quantity: item.cumulative_quantity,
    period_quantity: item.period_quantity,
    reported_percent: item.reported_percent,
    planned_start_date: item.planned_start_date,
    planned_finish_date: item.planned_finish_date,
    remark: item.remark,
  })
  editVisible.value = true
}

async function saveEdit() {
  if (!currentItem.value) return
  if (!editForm.reason.trim()) {
    errorMessage.value = '必须填写修改原因'
    return
  }
  saving.value = true
  errorMessage.value = ''
  try {
    await updateProgressItem(currentItem.value.id, { ...editForm })
    editVisible.value = false
    await loadItems()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '保存人工修正失败'
  } finally {
    saving.value = false
  }
}

async function openHistory(item: ProgressItem) {
  currentItem.value = item
  historyVisible.value = true
  try {
    historyRows.value = await getProgressItemHistory(item.id)
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '修改历史加载失败'
  }
}

async function undoEdit(item: ProgressItem) {
  // 给一线工程师一个"刚才那次手改填错了，撤回"的安全网——避免他们硬记原值再 PUT 一遍
  try {
    await ElMessageBox.confirm(
      `确定要撤销该明细行最近一次的手动修正吗？撤销后将恢复修改前的数据，并删除对应的历史记录。`,
      '撤销最近一次修改',
      { confirmButtonText: '撤销', cancelButtonText: '取消', type: 'warning' },
    )
  } catch {
    return
  }
  undoingItemId.value = item.id
  try {
    await undoLastProgressItemEdit(item.id)
    ElMessage.success('已撤销最近一次修改。')
    await loadItems()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '撤销失败'
  } finally {
    undoingItemId.value = null
  }
}

onMounted(loadInitial)
</script>

<style scoped>
.scope-panel {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
  gap: 12px;
}

.scope-panel div {
  display: grid;
  gap: 4px;
}

.scope-panel span,
.scope-panel p {
  color: #6b7280;
  font-size: 12px;
}

.scope-panel strong {
  color: #111827;
}

.scope-panel p {
  grid-column: 1 / -1;
  margin: 0;
}
</style>
