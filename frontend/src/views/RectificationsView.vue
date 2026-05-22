<template>
  <main class="page-shell">
    <section class="page-heading">
      <div>
        <p class="eyebrow">rectification</p>
        <h1>整改闭环</h1>
      </div>
      <div class="toolbar">
        <el-button @click="router.push(`/projects/${projectId}/dashboard`)">返回看板</el-button>
        <el-button type="primary" :disabled="creating" @click="openCreateDialog">新增整改项</el-button>
        <el-button type="primary" :loading="exporting" :disabled="exporting || total === 0" @click="openExportPreview">导出整改跟踪表</el-button>
      </div>
    </section>

    <el-alert v-if="errorMessage" :title="errorMessage" type="error" show-icon :closable="false" />

    <section class="dashboard-card-grid">
      <div
        v-for="card in summaryCards"
        :key="card.label"
        class="metric-card"
        :class="{ active: isCardActive(card.filter), danger: card.danger }"
        @click="applyCardFilter(card.filter)"
      >
        <span>{{ card.label }}</span>
        <strong :class="card.danger ? 'danger-text' : ''">{{ card.value }}</strong>
      </div>
    </section>

    <section class="form-surface filter-panel">
      <el-form label-width="88px">
        <div class="filter-grid">
          <el-form-item label="状态">
            <el-select v-model="filters.status" clearable placeholder="全部">
              <el-option label="未开始" value="open" />
              <el-option label="整改中" value="in_progress" />
              <el-option label="已完成" value="completed" />
              <el-option label="已关闭" value="closed" />
              <el-option label="已忽略" value="ignored" />
            </el-select>
          </el-form-item>
          <el-form-item label="滞后等级">
            <el-select v-model="filters.delay_level" clearable placeholder="全部">
              <el-option label="严重滞后" value="seriously_delayed" />
              <el-option label="明显滞后" value="delayed" />
              <el-option label="轻微滞后" value="slightly_delayed" />
            </el-select>
          </el-form-item>
          <el-form-item label="专业"><el-select v-model="filters.discipline" clearable filterable><el-option v-for="item in disciplineOptions" :key="item" :label="item" :value="item" /></el-select></el-form-item>
          <el-form-item label="楼栋"><el-select v-model="filters.building" clearable filterable><el-option v-for="item in buildingOptions" :key="item" :label="item" :value="item" /></el-select></el-form-item>
          <el-form-item label="楼层"><el-select v-model="filters.floor" clearable filterable><el-option v-for="item in floorOptions" :key="item" :label="item" :value="item" /></el-select></el-form-item>
          <el-form-item label="责任人"><el-input v-model="filters.responsible_person" clearable /></el-form-item>
          <el-form-item label="责任单位"><el-input v-model="filters.responsible_unit" clearable /></el-form-item>
          <el-form-item label="是否逾期">
            <el-select v-model="overdueFilter" clearable placeholder="全部">
              <el-option label="是" value="true" />
              <el-option label="否" value="false" />
            </el-select>
          </el-form-item>
          <el-form-item label="来源">
            <el-select v-model="filters.source_type" clearable placeholder="全部">
              <el-option label="滞后项" value="progress_item" />
              <el-option label="预警记录" value="warning" />
              <el-option label="手动创建" value="manual" />
            </el-select>
          </el-form-item>
          <el-form-item label="关键词"><el-input v-model="filters.keyword" clearable placeholder="施工项、问题描述、责任人、责任单位、备注" /></el-form-item>
        </div>
      </el-form>
      <div class="active-filter-bar">
        <span>当前筛选：</span>
        <el-tag v-if="!activeFilterTags.length" type="info">全部整改项</el-tag>
        <el-tag v-for="tag in activeFilterTags" :key="tag" closable @close="removeFilterTag(tag)">{{ tag }}</el-tag>
      </div>
      <div class="filter-actions">
        <span>筛选结果：{{ total }} 条</span>
        <el-button @click="resetFilters">重置筛选</el-button>
      </div>
    </section>

    <section class="form-surface batch-panel">
      <span>已选 {{ selectedIds.length }} 项</span>
      <el-button :disabled="!selectedIds.length" @click="batchStatus('in_progress')">批量整改中</el-button>
      <el-button :disabled="!selectedIds.length" @click="batchStatus('completed')">批量已完成</el-button>
      <el-button :disabled="!selectedIds.length" type="danger" plain @click="batchStatus('closed', true)">批量关闭</el-button>
      <el-button :disabled="!selectedIds.length" type="warning" plain @click="batchStatus('ignored', true)">批量忽略</el-button>
      <el-button :disabled="!selectedIds.length" @click="openBatchDialog">批量设置责任信息</el-button>
    </section>

    <section class="form-surface">
      <el-empty v-if="!loading && total === 0" description="当前没有整改项，可从滞后项或预警记录生成整改项。">
        <el-button @click="router.push(`/projects/${projectId}/dashboard`)">去 Dashboard</el-button>
        <el-button @click="router.push(`/projects/${projectId}/warnings`)">去预警记录</el-button>
        <el-button type="primary" @click="openCreateDialog">新增整改项</el-button>
      </el-empty>
      <el-table
        v-else
        v-loading="loading"
        :data="items"
        row-key="id"
        border
        @selection-change="selectedRows = $event"
        @sort-change="handleSortChange"
      >
        <el-table-column type="selection" width="42" />
        <el-table-column prop="status_label" label="状态" width="96" sortable="custom">
          <template #default="{ row }"><el-tag :type="statusTag(row.status)">{{ statusText(row.status, row.status_label) }}</el-tag></template>
        </el-table-column>
        <el-table-column prop="delay_level_label" label="滞后等级" width="118" sortable="custom">
          <template #default="{ row }"><el-tag :type="delayTag(row.delay_level)">{{ delayText(row.delay_level, row.delay_level_label) }}</el-tag></template>
        </el-table-column>
        <el-table-column prop="discipline" label="专业" width="100" />
        <el-table-column prop="building" label="楼栋" width="90" />
        <el-table-column prop="floor" label="楼层" width="90" />
        <el-table-column prop="system_name" label="系统" width="140" show-overflow-tooltip />
        <el-table-column prop="task_name" label="施工项" min-width="180" show-overflow-tooltip />
        <el-table-column prop="issue_description" label="问题描述" min-width="220" show-overflow-tooltip />
        <el-table-column prop="responsible_person" label="责任人" width="110" show-overflow-tooltip>
          <template #default="{ row }">{{ row.responsible_person || '-' }}</template>
        </el-table-column>
        <el-table-column prop="responsible_unit" label="责任单位" width="140" show-overflow-tooltip>
          <template #default="{ row }">{{ row.responsible_unit || '-' }}</template>
        </el-table-column>
        <el-table-column prop="planned_finish_date" label="计划完成时间" width="150" sortable="custom">
          <template #default="{ row }">
            <div class="deadline-cell">
              <span>{{ row.planned_finish_date || '-' }}</span>
              <el-tag v-if="row.is_overdue" type="danger" size="small">逾期</el-tag>
              <el-tag v-else-if="isDueSoon(row)" type="warning" size="small">即将到期</el-tag>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="是否逾期" width="92">
          <template #default="{ row }"><el-tag :type="row.is_overdue ? 'danger' : 'info'">{{ row.is_overdue ? '是' : '否' }}</el-tag></template>
        </el-table-column>
        <el-table-column prop="source_label" label="来源" width="104">
          <template #default="{ row }">{{ sourceText(row.source_type, row.source_label) }}</template>
        </el-table-column>
        <el-table-column prop="created_at" label="创建时间" width="160" sortable="custom" />
        <el-table-column prop="updated_at" label="更新时间" width="160" sortable="custom" />
        <el-table-column label="操作" width="130" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" @click="openDetail(row)">详情</el-button>
          </template>
        </el-table-column>
      </el-table>
      <el-pagination
        v-model:current-page="page"
        v-model:page-size="pageSize"
        layout="total, sizes, prev, pager, next"
        :total="total"
        :page-sizes="[10, 20, 50, 100]"
      />
    </section>

    <el-drawer v-model="detailVisible" title="整改项详情" size="560px">
      <template v-if="currentItem">
        <el-form label-width="110px">
          <h3 class="detail-section-title">基本信息</h3>
          <el-form-item label="施工项"><span class="detail-text">{{ currentItem.task_name || '-' }}</span></el-form-item>
          <el-form-item label="问题描述"><span class="detail-text">{{ currentItem.issue_description || '-' }}</span></el-form-item>
          <el-form-item label="来源"><span class="detail-text">{{ sourceText(currentItem.source_type, currentItem.source_label) }}</span></el-form-item>
          <el-form-item label="来源批次"><span class="detail-text">{{ currentItem.source_batch_label || '-' }}</span></el-form-item>
          <el-form-item label="计划基线"><span class="detail-text">{{ currentItem.source_baseline_plan_name || '未配置计划基线' }}</span></el-form-item>
          <h3 class="detail-section-title">责任信息</h3>
          <el-form-item label="责任人"><el-input v-model="editForm.responsible_person" /></el-form-item>
          <el-form-item label="责任单位"><el-input v-model="editForm.responsible_unit" /></el-form-item>
          <el-form-item label="计划完成"><el-date-picker v-model="editForm.planned_finish_date" type="date" value-format="YYYY-MM-DD" /></el-form-item>
          <h3 class="detail-section-title">进度信息</h3>
          <el-form-item label="状态">
            <el-select v-model="editForm.status">
              <el-option label="未开始" value="open" />
              <el-option label="整改中" value="in_progress" />
              <el-option label="已完成" value="completed" />
              <el-option label="已关闭" value="closed" />
              <el-option label="已忽略" value="ignored" />
            </el-select>
          </el-form-item>
          <el-form-item label="滞后等级"><span class="detail-text">{{ delayText(currentItem.delay_level, currentItem.delay_level_label) }}</span></el-form-item>
          <el-form-item label="实际 / 计划"><span class="detail-text">{{ percentText(currentItem.actual_percent) }} / {{ percentText(currentItem.planned_percent) }}</span></el-form-item>
          <el-form-item label="偏差"><span class="detail-text">{{ percentText(currentItem.progress_deviation) }}</span></el-form-item>
          <el-form-item label="复查结果"><el-input v-model="editForm.review_result" type="textarea" :autosize="{ minRows: 3, maxRows: 6 }" /></el-form-item>
          <el-form-item label="备注"><el-input v-model="editForm.remark" type="textarea" :autosize="{ minRows: 3, maxRows: 6 }" /></el-form-item>
          <el-form-item>
            <el-button :loading="aiSuggestionLoading" @click="handleAiSuggestion">AI 生成整改建议</el-button>
            <el-button v-if="aiSuggestionText" @click="applyAiSuggestion">采用建议</el-button>
            <el-button type="primary" @click="saveDetail">保存</el-button>
          </el-form-item>
          <el-alert
            v-if="aiSuggestionText"
            class="ai-suggestion-alert"
            title="AI辅助生成：以下建议仅供参考，请结合现场情况复核。"
            type="warning"
            show-icon
            :closable="false"
          />
          <el-input
            v-if="aiSuggestionText"
            :model-value="aiSuggestionText"
            type="textarea"
            :autosize="{ minRows: 4, maxRows: 8 }"
            readonly
          />
        </el-form>
        <el-divider />
        <h3 class="detail-section-title">操作记录</h3>
        <el-timeline>
          <el-timeline-item v-for="log in logs" :key="log.id" :timestamp="formatDateTime(log.created_at)">
            <strong>{{ log.action_label }}</strong>
            <p>{{ log.content || '-' }}</p>
            <span v-if="log.from_status_label || log.to_status_label">{{ statusText(log.from_status || '', log.from_status_label) }} → {{ statusText(log.to_status || '', log.to_status_label) }}</span>
          </el-timeline-item>
        </el-timeline>
      </template>
    </el-drawer>

    <el-dialog v-model="batchDialogVisible" title="批量设置责任信息" width="520px">
      <el-form label-width="110px">
        <el-alert
          :title="`已选择 ${selectedIds.length} 项。已关闭 / 已忽略项如不允许更新，将由后端自动跳过。`"
          type="info"
          show-icon
          :closable="false"
        />
        <el-form-item label="责任人"><el-input v-model="batchResponsiblePerson" clearable /></el-form-item>
        <el-form-item label="责任单位"><el-input v-model="batchResponsibleUnit" clearable /></el-form-item>
        <el-form-item label="计划完成"><el-date-picker v-model="batchPlannedDate" type="date" value-format="YYYY-MM-DD" /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="batchDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="batchUpdating" :disabled="!canSubmitBatchDialog" @click="submitBatchDialog">确认设置</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="exportPreviewVisible" title="整改跟踪表导出预览" width="560px">
      <div class="export-preview">
        <div><span>当前筛选条件</span><strong>{{ activeFilterTags.length ? activeFilterTags.join('、') : '全部整改项' }}</strong></div>
        <div><span>预计导出数量</span><strong>{{ total }} 条</strong></div>
        <div><span>操作记录摘要</span><strong>{{ includeLogSummary ? '包含' : '不包含' }}</strong></div>
      </div>
      <el-checkbox v-model="includeLogSummary">包含操作记录摘要</el-checkbox>
      <template #footer>
        <el-button @click="exportPreviewVisible = false">取消</el-button>
        <el-button type="primary" :loading="exporting" :disabled="exporting || total === 0" @click="handleExport">确认导出</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="createVisible" title="新增整改项" width="560px">
      <el-form label-width="110px">
        <el-form-item label="施工项"><el-input v-model="createForm.task_name" /></el-form-item>
        <el-form-item label="问题描述"><el-input v-model="createForm.issue_description" type="textarea" :autosize="{ minRows: 3, maxRows: 6 }" /></el-form-item>
        <el-form-item label="责任人"><el-input v-model="createForm.responsible_person" /></el-form-item>
        <el-form-item label="责任单位"><el-input v-model="createForm.responsible_unit" /></el-form-item>
        <el-form-item label="计划完成"><el-date-picker v-model="createForm.planned_finish_date" type="date" value-format="YYYY-MM-DD" /></el-form-item>
        <el-form-item label="备注"><el-input v-model="createForm.remark" type="textarea" :autosize="{ minRows: 2, maxRows: 5 }" /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="createVisible = false">取消</el-button>
        <el-button type="primary" :loading="creating" :disabled="creating || !createForm.task_name" @click="saveCreate">保存</el-button>
      </template>
    </el-dialog>
  </main>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useRoute, useRouter } from 'vue-router'

import {
  batchUpdateRectifications,
  createRectification,
  exportRectifications,
  listRectificationFilterOptions,
  listRectificationLogs,
  listRectifications,
  getRectificationSummary,
  updateRectification,
} from '../api/rectifications'
import { generateRectificationSuggestion } from '../api/ai'
import type { RectificationActionLog, RectificationFilterOptions, RectificationFilters, RectificationItem, RectificationSummary } from '../types/rectification'

const route = useRoute()
const router = useRouter()
const projectId = Number(route.params.id)

const loading = ref(false)
const exporting = ref(false)
const errorMessage = ref('')
const items = ref<RectificationItem[]>([])
const filterOptions = ref<RectificationFilterOptions>({
  disciplines: [],
  buildings: [],
  floors: [],
  responsible_persons: [],
  responsible_units: [],
  delay_levels: [],
  statuses: [],
  source_types: [],
  floors_by_building: {},
})
const summary = ref<RectificationSummary | null>(null)
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)
const selectedRows = ref<RectificationItem[]>([])
const sortBy = ref('')
const sortOrder = ref<'asc' | 'desc'>('desc')
const overdueFilter = ref('')
const batchDialogVisible = ref(false)
const batchUpdating = ref(false)
const exportPreviewVisible = ref(false)
const includeLogSummary = ref(true)
const filters = reactive<RectificationFilters>({
  scope: typeof route.query.scope === 'string' ? route.query.scope : '',
  data_date: typeof route.query.data_date === 'string' ? route.query.data_date : '',
  import_group_id: typeof route.query.import_group_id === 'string' ? route.query.import_group_id : '',
  batch_ids: typeof route.query.batch_ids === 'string' ? route.query.batch_ids : '',
  batch_id: route.query.batch_id ? Number(route.query.batch_id) : null,
  status: String(route.query.status || ''),
  delay_level: String(route.query.delay_level || ''),
  keyword: String(route.query.keyword || ''),
  building: String(route.query.building || ''),
  floor: String(route.query.floor || ''),
  discipline: String(route.query.discipline || ''),
  responsible_person: String(route.query.responsible_person || ''),
  responsible_unit: String(route.query.responsible_unit || ''),
  source_type: String(route.query.source_type || ''),
})
if (route.query.overdue === 'true') overdueFilter.value = 'true'

const batchResponsiblePerson = ref('')
const batchResponsibleUnit = ref('')
const batchPlannedDate = ref('')
const detailVisible = ref(false)
const createVisible = ref(false)
const creating = ref(false)
const currentItem = ref<RectificationItem | null>(null)
const logs = ref<RectificationActionLog[]>([])
const aiSuggestionLoading = ref(false)
const aiSuggestionText = ref('')
const editForm = reactive<Partial<RectificationItem>>({})
const createForm = reactive<Partial<RectificationItem>>({ source_type: 'manual', status: 'open' })

const selectedIds = computed(() => selectedRows.value.map((item) => item.id))
const summaryCards = computed(() => {
  const data = summary.value
  return [
    { label: '全部整改项', value: data?.total ?? 0, filter: {} },
    { label: '未开始', value: data?.open ?? 0, filter: { status: 'open' } },
    { label: '整改中', value: data?.in_progress ?? 0, filter: { status: 'in_progress' } },
    { label: '已完成', value: data?.completed ?? 0, filter: { status: 'completed' } },
    { label: '已关闭', value: data?.closed ?? 0, filter: { status: 'closed' } },
    { label: '已忽略', value: data?.ignored ?? 0, filter: { status: 'ignored' } },
    { label: '逾期', value: data?.overdue ?? 0, danger: true, filter: { overdue: 'true' } },
    { label: '严重滞后', value: data?.serious ?? 0, danger: true, filter: { delay_level: 'seriously_delayed' } },
  ]
})
const disciplineOptions = computed(() => filterOptions.value.disciplines)
const buildingOptions = computed(() => filterOptions.value.buildings)
const floorOptions = computed(() => {
  if (filters.building) return filterOptions.value.floors_by_building[filters.building] ?? []
  return filterOptions.value.floors
})
const activeFilterTags = computed(() => {
  const tags: string[] = []
  if (filters.scope === 'project') tags.push('范围：项目级聚合')
  if (filters.scope === 'batch') tags.push('范围：单批次')
  if (filters.data_date) tags.push(`数据日期：${filters.data_date}`)
  if (filters.import_group_id) tags.push(`导入组：${filters.import_group_id}`)
  if (filters.batch_ids) tags.push(`批次：${filters.batch_ids}`)
  if (filters.batch_id) tags.push(`批次：${filters.batch_id}`)
  if (filters.status) tags.push(`状态：${statusText(filters.status)}`)
  if (filters.delay_level) tags.push(`滞后等级：${delayText(filters.delay_level)}`)
  if (filters.discipline) tags.push(`专业：${filters.discipline}`)
  if (filters.building) tags.push(`楼栋：${filters.building}`)
  if (filters.floor) tags.push(`楼层：${filters.floor}`)
  if (filters.responsible_person) tags.push(`责任人：${filters.responsible_person}`)
  if (filters.responsible_unit) tags.push(`责任单位：${filters.responsible_unit}`)
  if (overdueFilter.value) tags.push(`是否逾期：${overdueFilter.value === 'true' ? '是' : '否'}`)
  if (filters.source_type) tags.push(`来源：${sourceText(filters.source_type)}`)
  if (filters.keyword) tags.push(`关键词：${filters.keyword}`)
  return tags
})
const canSubmitBatchDialog = computed(() =>
  selectedIds.value.length > 0 && Boolean(batchResponsiblePerson.value || batchResponsibleUnit.value || batchPlannedDate.value),
)

function queryFilters(): RectificationFilters {
  return {
    ...filters,
    overdue: overdueFilter.value === '' ? null : overdueFilter.value === 'true',
    page: page.value,
    page_size: pageSize.value,
    sort_by: sortBy.value,
    sort_order: sortOrder.value,
  }
}

async function loadData() {
  loading.value = true
  errorMessage.value = ''
  try {
    const [list, loadedSummary, options] = await Promise.all([
      listRectifications(projectId, queryFilters()),
      getRectificationSummary(projectId, scopeFilters()),
      listRectificationFilterOptions(projectId, scopeFilters()),
    ])
    items.value = list.items
    total.value = list.total
    summary.value = loadedSummary
    filterOptions.value = options
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '整改项加载失败'
  } finally {
    loading.value = false
  }
}

function resetFilters() {
  Object.assign(filters, {
    status: '',
    delay_level: '',
    discipline: '',
    building: '',
    floor: '',
    responsible_person: '',
    responsible_unit: '',
    source_type: '',
    keyword: '',
  })
  overdueFilter.value = ''
  page.value = 1
}

function applyCardFilter(filter: Record<string, string | undefined>) {
  resetFilters()
  Object.entries(filter).forEach(([key, value]) => {
    if (key !== 'overdue') {
      filters[key as keyof RectificationFilters] = value as never
    }
  })
  overdueFilter.value = filter.overdue || ''
}

function isCardActive(filter: Record<string, string | undefined>) {
  const keys = Object.keys(filter)
  if (!keys.length) return !activeFilterTags.value.length
  return keys.every((key) => {
    if (key === 'overdue') return overdueFilter.value === filter[key]
    return filters[key as keyof RectificationFilters] === filter[key]
  })
}

function removeFilterTag(tag: string) {
  const [label] = tag.split('：')
  const map: Record<string, () => void> = {
    状态: () => { filters.status = '' },
    范围: () => {},
    数据日期: () => {},
    导入组: () => {},
    批次: () => {},
    滞后等级: () => { filters.delay_level = '' },
    专业: () => { filters.discipline = '' },
    楼栋: () => { filters.building = '' },
    楼层: () => { filters.floor = '' },
    责任人: () => { filters.responsible_person = '' },
    责任单位: () => { filters.responsible_unit = '' },
    是否逾期: () => { overdueFilter.value = '' },
    来源: () => { filters.source_type = '' },
    关键词: () => { filters.keyword = '' },
  }
  map[label]?.()
  page.value = 1
}

function scopeFilters(): RectificationFilters {
  return {
    scope: filters.scope || null,
    data_date: filters.data_date || null,
    import_group_id: filters.import_group_id || null,
    batch_ids: filters.batch_ids || null,
    batch_id: filters.batch_id || null,
  }
}

function handleSortChange({ prop, order }: { prop: string; order: string | null }) {
  const map: Record<string, string> = { status_label: 'status', delay_level_label: 'delay_level' }
  sortBy.value = order ? map[prop] || prop : ''
  sortOrder.value = order === 'ascending' ? 'asc' : 'desc'
}

async function batchStatus(status: string, confirm = false) {
  if (confirm) {
    try {
      await ElMessageBox.confirm(`确认批量${status === 'closed' ? '关闭' : '忽略'}选中的整改项？`, '批量操作确认')
    } catch {
      return
    }
  }
  await batchPatch({ status })
}

async function batchPatch(payload: Record<string, unknown>) {
  batchUpdating.value = true
  try {
    const result = await batchUpdateRectifications(projectId, { ids: selectedIds.value, ...payload })
    const skippedText = result.skipped_count ? `，跳过 ${result.skipped_count} 项（已关闭 / 已忽略或不存在）` : ''
    ElMessage.success(`已更新 ${result.updated_count} 项${skippedText}`)
    await loadData()
  } finally {
    batchUpdating.value = false
  }
}

function openBatchDialog() {
  batchResponsiblePerson.value = ''
  batchResponsibleUnit.value = ''
  batchPlannedDate.value = ''
  batchDialogVisible.value = true
}

async function submitBatchDialog() {
  const payload: Record<string, unknown> = {}
  if (batchResponsiblePerson.value) payload.responsible_person = batchResponsiblePerson.value
  if (batchResponsibleUnit.value) payload.responsible_unit = batchResponsibleUnit.value
  if (batchPlannedDate.value) payload.planned_finish_date = batchPlannedDate.value
  await batchPatch(payload)
  batchDialogVisible.value = false
}

async function openDetail(item: RectificationItem) {
  currentItem.value = item
  Object.assign(editForm, item)
  logs.value = (await listRectificationLogs(projectId, item.id)).sort((a, b) => b.created_at.localeCompare(a.created_at) || b.id - a.id)
  detailVisible.value = true
}

async function saveDetail() {
  if (!currentItem.value) return
  currentItem.value = await updateRectification(projectId, currentItem.value.id, editForm)
  logs.value = await listRectificationLogs(projectId, currentItem.value.id)
  ElMessage.success('整改项已保存')
  await loadData()
}

async function handleAiSuggestion() {
  if (!currentItem.value) return
  aiSuggestionLoading.value = true
  try {
    const response = await generateRectificationSuggestion(projectId, currentItem.value.id)
    aiSuggestionText.value = response.generated_text || response.fallback_text
    if (response.source === 'ai') {
      ElMessage.success('AI 辅助整改建议已生成。')
    } else if (!response.enabled) {
      ElMessage.warning('当前未启用 AI 辅助，请在系统设置中配置。')
    } else {
      ElMessage.warning(response.error_message || 'AI 生成失败，已显示规则化建议。')
    }
  } catch (error) {
    ElMessage.error(`AI 生成整改建议失败：${error instanceof Error ? error.message : '已保留现有整改项。'}`)
  } finally {
    aiSuggestionLoading.value = false
  }
}

function applyAiSuggestion() {
  if (!aiSuggestionText.value) return
  editForm.remark = aiSuggestionText.value
  ElMessage.success('建议已填入备注，保存后才会写入数据库。')
}

function openCreateDialog() {
  Object.assign(createForm, {
    source_type: 'manual',
    status: 'open',
    task_name: '',
    issue_description: '',
    responsible_person: '',
    responsible_unit: '',
    planned_finish_date: null,
    remark: '',
  })
  createVisible.value = true
}

async function saveCreate() {
  creating.value = true
  try {
    await createRectification(projectId, createForm)
    ElMessage.success('整改项已新增')
    createVisible.value = false
    await loadData()
  } catch (error) {
    ElMessage.error(`新增整改项失败：${error instanceof Error ? error.message : '请稍后重试。'}`)
  } finally {
    creating.value = false
  }
}

function openExportPreview() {
  if (total.value === 0) {
    ElMessage.warning('当前筛选条件下暂无整改项，无法导出整改跟踪表。')
    return
  }
  exportPreviewVisible.value = true
}

async function handleExport() {
  exporting.value = true
  if (total.value === 0) {
    ElMessage.warning('当前筛选条件下暂无整改项，无法导出整改跟踪表。')
    exporting.value = false
    return
  }
  try {
    const fileName = await exportRectifications(projectId, queryFilters())
    exportPreviewVisible.value = false
    ElMessage.success(`整改跟踪表已导出：${fileName}，可在报表历史中查看。`)
  } catch (error) {
    ElMessage.error(`导出整改跟踪表失败：${error instanceof Error ? error.message : '文件生成异常，请查看诊断日志。'}`)
  } finally {
    exporting.value = false
  }
}

function formatDateTime(value?: string | null) {
  return value ? value.replace('T', ' ').slice(0, 16) : '-'
}

function statusText(status?: string | null, fallback?: string | null) {
  return ({
    open: '未开始',
    in_progress: '整改中',
    completed: '已完成',
    closed: '已关闭',
    ignored: '已忽略',
  } as Record<string, string>)[status || ''] ?? fallback ?? '-'
}

function statusTag(status?: string | null) {
  if (status === 'closed' || status === 'completed') return 'success'
  if (status === 'ignored') return 'info'
  if (status === 'in_progress') return 'warning'
  return 'danger'
}

function delayText(level?: string | null, fallback?: string | null) {
  return ({
    seriously_delayed: '严重滞后',
    seriously_delay: '严重滞后',
    critical: '严重滞后',
    delayed: '明显滞后',
    slightly_delayed: '轻微滞后',
  } as Record<string, string>)[level || ''] ?? fallback ?? '-'
}

function delayTag(level?: string | null) {
  if (['seriously_delayed', 'seriously_delay', 'critical'].includes(level || '')) return 'danger'
  if (level === 'delayed') return 'warning'
  return 'info'
}

function sourceText(sourceType?: string | null, fallback?: string | null) {
  return ({
    progress_item: '滞后项',
    warning: '预警记录',
    manual: '手动创建',
  } as Record<string, string>)[sourceType || ''] ?? fallback ?? '-'
}

function isDueSoon(item: RectificationItem) {
  if (!item.planned_finish_date || ['closed', 'ignored', 'completed'].includes(item.status)) return false
  const today = new Date()
  today.setHours(0, 0, 0, 0)
  const date = new Date(item.planned_finish_date)
  date.setHours(0, 0, 0, 0)
  const diffDays = Math.ceil((date.getTime() - today.getTime()) / 86400000)
  return diffDays >= 0 && diffDays <= 3
}

function percentText(value?: number | null) {
  return value === null || value === undefined ? '-' : `${Number(value).toFixed(2)}%`
}

watch([filters, overdueFilter], () => { page.value = 1 }, { deep: true })
watch([filters, overdueFilter, page, pageSize, sortBy, sortOrder], () => loadData(), { deep: true })
watch(() => filters.building, () => { filters.floor = '' })
onMounted(loadData)
</script>

<style scoped>
.filter-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 8px 16px;
}
.filter-actions,
.batch-panel,
.active-filter-bar {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.active-filter-bar {
  margin: 4px 0 12px;
  color: #667085;
}
.danger-text {
  color: #c0392b;
}
.metric-card {
  cursor: pointer;
}
.metric-card.active {
  border-color: #2563eb;
  background: #eff6ff;
  box-shadow: inset 0 0 0 1px rgba(37, 99, 235, 0.2);
}
.metric-card.danger.active {
  border-color: #dc2626;
  background: #fef2f2;
  box-shadow: inset 0 0 0 1px rgba(220, 38, 38, 0.16);
}
.deadline-cell {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
}
.detail-text {
  white-space: pre-wrap;
  overflow-wrap: anywhere;
  line-height: 1.7;
}

.detail-section-title {
  margin: 18px 0 12px;
  font-size: 15px;
  color: #172033;
}

.export-preview {
  display: grid;
  gap: 12px;
  margin-bottom: 14px;
}

.export-preview div {
  display: grid;
  gap: 6px;
  padding: 12px;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  background: #f8fafc;
}

.export-preview span {
  color: #667085;
  font-size: 13px;
}

.export-preview strong {
  color: #172033;
  line-height: 1.5;
}

.ai-suggestion-alert {
  margin-bottom: 12px;
}
</style>
