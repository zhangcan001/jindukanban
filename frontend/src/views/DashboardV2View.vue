<template>
  <main class="page-shell dashboard-v2-shell">
    <header class="page-header">
      <div>
        <p class="eyebrow">Dashboard V2</p>
        <h1>新版看板</h1>
        <p class="muted-text">{{ dashboard?.scope.scope_label || '当前筛选范围看板' }}</p>
      </div>
      <div class="header-actions">
        <el-button :disabled="exporting" :loading="exporting" @click="handleExport">导出</el-button>
      </div>
    </header>

    <section class="form-surface v2-filter-bar">
      <el-form label-position="top">
        <div class="v2-filter-grid">
          <el-form-item label="数据日期">
            <el-date-picker v-model="filters.dataDate" value-format="YYYY-MM-DD" type="date" clearable />
          </el-form-item>
          <el-form-item label="统计口径">
            <el-select v-model="filters.calculationMethod" clearable placeholder="自动推荐">
              <el-option label="自动推荐" value="" />
              <el-option label="权重归一化统计" value="weighted_percent" />
              <el-option label="产值加权统计" value="value_weighted_percent" />
              <el-option label="工程量统计" value="quantity_percent" />
              <el-option label="完成率平均" value="percent_average" />
              <el-option label="任务平均" value="task_average" />
            </el-select>
          </el-form-item>
          <el-form-item label="专业">
            <el-select v-model="filters.discipline" clearable filterable>
              <el-option v-for="item in options.disciplines" :key="item" :label="item" :value="item" />
            </el-select>
          </el-form-item>
          <el-form-item label="楼栋">
            <el-select v-model="filters.building" clearable filterable>
              <el-option v-for="item in options.buildings" :key="item" :label="item" :value="item" />
            </el-select>
          </el-form-item>
          <el-form-item label="楼层">
            <el-select v-model="filters.floor" clearable filterable>
              <el-option v-for="item in options.floors" :key="item" :label="item" :value="item" />
            </el-select>
          </el-form-item>
        </div>
        <el-collapse class="v2-advanced">
          <el-collapse-item title="高级筛选" name="advanced">
            <div class="v2-filter-grid">
              <el-form-item label="Sheet / 批次">
                <el-select v-model="filters.batchId" clearable filterable>
                  <el-option v-for="batch in batchOptions" :key="batch.batch_id" :label="batchLabel(batch)" :value="batch.batch_id" />
                </el-select>
              </el-form-item>
              <el-form-item label="计划基线">
                <el-select v-model="filters.baselinePlanId" clearable filterable>
                  <el-option v-for="plan in baselineOptions" :key="plan.id" :label="plan.name" :value="plan.id" />
                </el-select>
              </el-form-item>
              <el-form-item label="状态">
                <el-select v-model="filters.status" clearable filterable>
                  <el-option v-for="item in statusOptions" :key="item.value" :label="item.label" :value="item.value" />
                </el-select>
              </el-form-item>
              <el-form-item label="系统">
                <el-select v-model="filters.systemName" clearable filterable>
                  <el-option v-for="item in options.systems" :key="item" :label="item" :value="item" />
                </el-select>
              </el-form-item>
              <el-form-item label="施工单位">
                <el-select v-model="filters.constructionUnit" clearable filterable>
                  <el-option v-for="item in options.construction_units" :key="item" :label="item" :value="item" />
                </el-select>
              </el-form-item>
            </div>
          </el-collapse-item>
        </el-collapse>
        <div class="v2-filter-actions">
          <span class="scope-summary">当前范围：{{ currentScopeText }}</span>
          <el-tag v-for="item in activeFilterTags" :key="item" effect="plain">{{ item }}</el-tag>
          <el-tag v-if="filters.floor" type="warning" effect="light">已筛选楼层：{{ activeFloorLabel }}</el-tag>
          <el-button v-if="filters.floor" size="small" :disabled="loading" @click="clearFloorFilter">清除楼层</el-button>
          <span class="spacer"></span>
          <el-button type="primary" :loading="loading" @click="loadDashboard">查询</el-button>
          <el-button :disabled="loading" @click="resetFilters">重置全部</el-button>
        </div>
      </el-form>
    </section>

    <el-alert v-if="errorMessage" :title="errorMessage" type="error" show-icon :closable="false" />
    <el-alert v-else-if="dashboard?.scope.message" :title="dashboard.scope.message" type="info" show-icon :closable="false" />
    <el-alert
      v-for="message in adaptationMessages"
      :key="message"
      :title="message"
      type="warning"
      show-icon
      :closable="false"
    />

    <el-tabs v-model="viewMode" class="v2-tabs">
      <el-tab-pane label="总体" name="overview" />
      <el-tab-pane label="专业" name="discipline" />
      <el-tab-pane label="楼栋" name="building" />
    </el-tabs>

    <el-skeleton v-if="loading && !dashboard" :rows="10" animated />
    <template v-else>
      <section class="v2-kpi-grid">
        <article v-for="card in kpiCards" :key="card.label" class="v2-kpi-card">
          <span>{{ card.label }}</span>
          <strong :class="card.className">{{ card.value }}</strong>
        </article>
      </section>

      <section class="v2-main-grid" :class="{ 'is-building-mode': viewMode === 'building' }">
        <article class="form-surface v2-panel v2-wide-panel">
          <header class="v2-panel-header">
            <h2>{{ mainTitle }}</h2>
            <span>{{ overview?.item_count ?? 0 }} 项任务</span>
          </header>

          <div v-if="viewMode === 'overview'" class="overview-visuals">
            <div class="v2-progress-hero">
              <el-progress type="dashboard" :percentage="percentValue(overview?.actual_percent)" />
              <div>
                <span>当前实际进度</span>
                <strong>{{ fmtPercent(overview?.actual_percent) }}</strong>
              </div>
            </div>
            <div class="compare-bars">
              <MetricBar label="当前实际进度" :value="overview?.actual_percent" tone="actual" />
              <MetricBar label="按计划应完成进度" :value="overview?.planned_percent" tone="plan" />
            </div>
            <div class="contribution-list">
              <button v-for="row in disciplineCards" :key="row.name" type="button" @click="selectDiscipline(row.name)">
                <span>{{ row.name }}</span>
                <i :style="{ width: `${percentValue(row.actual_percent)}%` }"></i>
                <strong>{{ fmtPercent(row.actual_percent) }}</strong>
              </button>
            </div>
          </div>

          <div v-else-if="viewMode === 'discipline'" class="discipline-view">
            <el-tooltip
              v-for="row in disciplineCards"
              :key="row.name"
              :content="disciplineTooltip(row)"
              placement="top"
            >
              <button class="progress-row-card" type="button" @click="selectDiscipline(row.name)">
                <header class="discipline-card-header">
                  <span class="status-dot" :class="delayClass(row.progress_deviation)"></span>
                  <strong :title="row.name">{{ row.name }}</strong>
                  <el-tag size="small" :type="statusTagType(row.progress_deviation)">{{ statusLabel(row.progress_deviation) }}</el-tag>
                </header>
                <div class="discipline-progress-row">
                  <div class="discipline-progress-value">
                    <span>当前实际进度</span>
                    <strong>{{ fmtPercent(row.actual_percent) }}</strong>
                  </div>
                  <div class="discipline-progress-value">
                    <span>按计划应完成进度</span>
                    <strong>{{ fmtPercent(row.planned_percent) }}</strong>
                  </div>
                </div>
                <div class="discipline-summary-row">
                  <span :class="delayClass(row.progress_deviation)">偏差 {{ signedPercent(row.progress_deviation) }}</span>
                  <span>任务 {{ row.task_count }}</span>
                  <span>滞后 {{ row.delayed_count }}</span>
                </div>
                <MetricBar label="进度" :value="row.actual_percent" tone="actual" />
              </button>
            </el-tooltip>
          </div>

          <div v-else class="building-view">
            <div class="building-view-toolbar">
              <div class="elevation-legend">
                <span v-for="item in elevationLegend" :key="item.status"><i :class="statusClass(item.status)"></i>{{ item.label }}</span>
              </div>
              <div class="building-view-actions">
                <el-tag v-if="filters.building" type="warning" effect="light">全局筛选：{{ filters.building }}</el-tag>
                <el-tag v-else-if="selectedBuildingName" effect="plain">当前查看：{{ selectedBuildingName }}</el-tag>
                <el-button-group class="delay-quick-actions">
                  <el-tooltip v-for="item in delayQuickFilters" :key="item.value" :content="item.tip" placement="top">
                    <el-button
                      size="small"
                      :type="filters.status === item.value ? 'primary' : 'default'"
                      :disabled="loading"
                      @click="applyDelayQuickFilter(item.value)"
                    >
                      {{ item.label }}
                    </el-button>
                  </el-tooltip>
                  <el-button v-if="filters.status" size="small" :disabled="loading" @click="clearDelayFilter">清除滞后</el-button>
                </el-button-group>
                <el-button v-if="filters.building" size="small" :disabled="loading" @click="clearBuildingFilter">退出楼栋筛选</el-button>
                <el-button v-else-if="selectedBuildingName" size="small" :disabled="loading" @click="applyBuildingFilter(selectedBuildingName)">筛选此楼栋</el-button>
              </div>
            </div>
            <div v-if="options.construction_units?.length" class="construction-unit-bar">
              <span class="construction-unit-label">施工单位</span>
              <el-radio-group v-model="constructionUnitSegment" size="small" :disabled="loading">
                <el-radio-button label="__ALL__">全部</el-radio-button>
                <el-radio-button v-for="unit in options.construction_units" :key="unit" :label="unit">{{ unit }}</el-radio-button>
              </el-radio-group>
              <el-tag v-if="filters.constructionUnit" type="warning" effect="light" size="small">当前仅看：{{ filters.constructionUnit }}</el-tag>
            </div>
            <div v-if="!buildingElevation.length" class="empty-elevation">
              当前筛选范围暂无楼栋楼层数据，请检查楼栋、楼层字段或调整筛选条件。
            </div>
            <div v-else class="building-elevation-layout">
              <el-alert
                v-if="isCompactElevation"
                class="compact-elevation-tip"
                title="楼层较多，已启用紧凑显示。可在立面图区域纵向滚动查看全部楼层。"
                type="info"
                show-icon
                :closable="false"
              />
              <div class="building-view-top">
                <div class="building-cards">
                  <button
                    v-for="row in buildingCards"
                    :key="row.name"
                    class="building-card"
                    type="button"
                    :class="{ active: selectedBuildingName === row.name, filtered: filters.building === row.name }"
                    @click="selectBuilding(row.name)"
                  >
                    <span class="status-dot" :class="delayClass(row.progress_deviation)"></span>
                    <strong :title="row.name">{{ row.name }}</strong>
                    <MetricBar label="当前实际" :value="row.actual_percent" tone="actual" />
                    <small>{{ row.task_count }} 项 / 滞后 {{ row.delayed_count }}</small>
                  </button>
                </div>
                <aside class="building-summary-panel">
                  <h3>{{ selectedElevation?.building || '当前楼栋' }}</h3>
                  <dl v-if="selectedElevation">
                    <div><dt>任务数</dt><dd>{{ selectedElevation.task_count }}</dd></div>
                    <div><dt>实际进度</dt><dd>{{ fmtPercent(selectedElevation.actual_percent) }}</dd></div>
                    <div><dt>应完成进度</dt><dd>{{ fmtPercent(selectedElevation.planned_percent) }}</dd></div>
                    <div><dt>偏差</dt><dd :class="delayClass(selectedElevation.progress_deviation)">{{ signedPercent(selectedElevation.progress_deviation) }}</dd></div>
                    <div><dt>状态</dt><dd>{{ selectedElevation.status_label }}</dd></div>
                  </dl>
                  <p v-else class="muted-text">点击楼栋查看摘要。</p>
                  <div v-if="selectedElevation" class="building-summary-actions">
                    <el-button v-if="!filters.building" size="small" type="primary" @click="applyBuildingFilter(selectedElevation.building)">筛选此楼栋</el-button>
                    <el-button v-else size="small" @click="clearBuildingFilter">查看全部楼栋</el-button>
                  </div>
                </aside>
              </div>
              <div class="building-view-scroll" :style="{ '--elevation-container-max-height': elevationContainerMaxHeight }">
                <div class="building-25d-stage" :class="{ compact: isCompactElevation }">
                  <article v-for="tower in visibleBuildingElevation" :key="tower.building" :class="['building-tower', elevationModeClass(tower.floors.length)]">
                    <button class="tower-title" type="button" :class="{ active: selectedBuildingName === tower.building, filtered: filters.building === tower.building }" @click="selectBuilding(tower.building)">
                      <strong :title="tower.building">{{ tower.building }}</strong>
                      <span>{{ tower.task_count }} 项 · {{ tower.status_label }}</span>
                    </button>
                    <div class="tower-body">
                      <el-tooltip
                        v-for="floor in tower.floors"
                        :key="`${tower.building}-${floor.floor}`"
                        :content="floorTooltip(tower.building, floor)"
                        placement="left"
                      >
                        <button
                          type="button"
                          :class="['floor-slab', statusClass(floor.status), floorDensityClass(tower.floors.length), { selected: selectedBuildingName === tower.building && filters.floor === floor.floor }]"
                          @click="openFloorDetail(tower.building, floor)"
                        >
                          <span :title="floor.floor">{{ floor.floor }}</span>
                          <strong>{{ fmtPercent(floor.actual_percent) }}</strong>
                        </button>
                      </el-tooltip>
                    </div>
                  </article>
                </div>
              </div>
            </div>
            <div class="floor-heatmap">
              <button
                v-for="cell in floorHeatmap"
                :key="`${cell.building}-${cell.floor}`"
                type="button"
                :class="['floor-cell', statusClass(cell.status)]"
                :title="floorCellTitle(cell)"
                @click="applyFloorFilter(cell.building, cell.floor)"
              >
                <strong>{{ cell.building }} {{ cell.floor }}</strong>
                <span>{{ fmtPercent(cell.actual_percent) }}</span>
                <small>{{ floorCellStatusText(cell) }}</small>
              </button>
            </div>
          </div>
        </article>

        <aside class="form-surface v2-panel">
          <header class="v2-panel-header">
            <h2>统计口径说明</h2>
          </header>
          <p class="context-text">当前按 Excel 字段自动推荐统计口径，所有图表均使用当前筛选范围计算。</p>
          <dl class="context-list">
            <div><dt>当前统计口径</dt><dd>{{ contextText('calculation_method_name') }}</dd></div>
            <div><dt>推荐原因</dt><dd>{{ contextText('recommendation_reason') }}</dd></div>
            <div><dt>智能推荐口径</dt><dd>{{ diagnosticText('recommended_calculation_method_name') }}</dd></div>
            <div><dt>诊断推荐原因</dt><dd>{{ diagnosticText('recommended_reason') }}</dd></div>
            <div><dt>权重来源</dt><dd>{{ contextText('weight_source') }}</dd></div>
            <div><dt>当前范围权重合计</dt><dd>{{ contextNumber('weight_total') }}</dd></div>
            <div><dt>是否混合单位</dt><dd>{{ contextBool('mixed_units') }}</dd></div>
            <div><dt>单位列表</dt><dd>{{ unitList }}</dd></div>
            <div><dt>参与统计任务数</dt><dd>{{ contextNumber('participating_task_count') }}</dd></div>
            <div><dt>权重任务数</dt><dd>{{ weightDiagnosticText }}</dd></div>
            <div><dt>工程量字段完整率</dt><dd>{{ diagnosticRate('quantity_field_complete_rate') }}</dd></div>
            <div><dt>计划日期完整率</dt><dd>{{ diagnosticRate('plan_date_complete_rate') }}</dd></div>
            <div><dt>实际完成率完整率</dt><dd>{{ diagnosticRate('actual_percent_complete_rate') }}</dd></div>
          </dl>
          <div class="capability-list">
            <div v-for="item in capabilityRows" :key="item.key">
              <el-tag :type="item.available ? 'success' : 'warning'">{{ item.label }}：{{ item.available ? '可用' : '不可用' }}</el-tag>
              <span>{{ item.reason }}</span>
            </div>
          </div>
        </aside>
      </section>

      <section class="v2-lower-grid">
        <article class="form-surface v2-panel">
          <header class="v2-panel-header"><h2>滞后状态分布</h2></header>
          <div class="delay-distribution">
            <MetricBar v-for="row in delayDistribution" :key="row.status" :label="row.status_label" :value="delayPercent(row.count)" :tone="row.status" />
          </div>
        </article>
        <article class="form-surface v2-panel">
          <header class="v2-panel-header"><h2>滞后重点列表</h2></header>
          <el-table :data="delayedItems" size="small" height="280">
            <el-table-column prop="discipline" label="专业" width="90" />
            <el-table-column prop="building" label="楼栋" width="80" />
            <el-table-column prop="floor" label="楼层" width="80" />
            <el-table-column prop="task_name" label="任务" min-width="160" />
            <el-table-column label="进度偏差" width="100">
              <template #default="{ row }">{{ signedPercent(row.progress_deviation) }}</template>
            </el-table-column>
          </el-table>
        </article>
        <article class="form-surface v2-panel">
          <header class="v2-panel-header"><h2>整改摘要</h2></header>
          <div class="rectification-summary">
            <span>未关闭 {{ openRectificationCount }}</span>
            <span>打开 {{ rectificationSummary.open }}</span>
            <span>整改中 {{ rectificationSummary.in_progress }}</span>
            <span>逾期 {{ rectificationSummary.overdue }}</span>
          </div>
        </article>
      </section>
    </template>
  </main>

  <el-dialog v-model="floorDetailVisible" :title="floorDetailTitle" width="760px">
    <div v-if="selectedFloorDetail" class="floor-detail">
      <dl class="floor-detail-grid">
        <div><dt>楼栋</dt><dd>{{ selectedFloorBuilding }}</dd></div>
        <div><dt>楼层</dt><dd>{{ selectedFloorDetail.floor }}</dd></div>
        <div><dt>任务数</dt><dd>{{ selectedFloorDetail.task_count }}</dd></div>
        <div><dt>实际进度</dt><dd>{{ fmtPercent(selectedFloorDetail.actual_percent) }}</dd></div>
        <div><dt>应完成进度</dt><dd>{{ fmtPercent(selectedFloorDetail.planned_percent) }}</dd></div>
        <div><dt>偏差</dt><dd :class="statusClass(selectedFloorDetail.status)">{{ signedPercent(selectedFloorDetail.progress_deviation) }}</dd></div>
        <div><dt>滞后任务数</dt><dd>{{ selectedFloorDetail.delayed_count + selectedFloorDetail.serious_delayed_count }}</dd></div>
        <div><dt>未到计划开始</dt><dd>{{ selectedFloorDetail.not_started_count }}</dd></div>
      </dl>
      <h3>主要滞后任务</h3>
      <el-table :data="selectedFloorDetail.major_delayed_tasks" size="small" height="220" empty-text="当前楼层暂无明显或严重滞后任务">
        <el-table-column prop="discipline" label="专业" width="90" />
        <el-table-column prop="task_name" label="任务" min-width="180" />
        <el-table-column prop="delay_level_label" label="状态" width="100" />
        <el-table-column label="偏差" width="90">
          <template #default="{ row }">{{ signedPercent(row.progress_deviation) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="110">
          <template #default="{ row }">
            <el-button link type="primary" @click="goProgressItem(row)">查看明细</el-button>
          </template>
        </el-table-column>
      </el-table>
      <div class="floor-detail-actions">
        <el-button type="primary" @click="applySelectedFloorFilter">筛选此楼层</el-button>
        <el-button @click="applyFloorDelayFilter('delayed_or_worse')">只看明显及以上</el-button>
        <el-button @click="applyFloorDelayFilter('seriously_delayed')">只看严重滞后</el-button>
        <el-button @click="goProgressItemsForFloor">查看进度明细</el-button>
        <el-button @click="goRectificationsForFloor">查看整改闭环</el-button>
        <el-button :loading="exporting" @click="handleExportSelectedFloor">导出当前楼层看板</el-button>
        <el-button @click="closeFloorDetail">关闭</el-button>
      </div>
    </div>
  </el-dialog>
</template>

<script setup lang="ts">
import { computed, defineComponent, h, onMounted, reactive, ref, watch, type PropType } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { getAnalyticsTrend, getDashboardV2 } from '../api/analytics'
import { listBaselinePlans } from '../api/baselinePlans'
import { exportDashboardReport } from '../api/reports'
import type { AnalyticsTrendPoint, DashboardBuildingElevationFloor, DashboardUnifiedMatrixRow, DashboardUnifiedStatRow, DashboardV2Response } from '../types/analytics'
import type { BaselinePlan } from '../types/baselinePlan'

const route = useRoute()
const router = useRouter()
const projectId = Number(route.params.id)
const viewMode = ref<'overview' | 'discipline' | 'building'>((route.query.view as 'overview' | 'discipline' | 'building') || 'overview')
const loading = ref(false)
const exporting = ref(false)
const errorMessage = ref('')
const dashboard = ref<DashboardV2Response | null>(null)
const batchOptions = ref<AnalyticsTrendPoint[]>([])
const baselineOptions = ref<BaselinePlan[]>([])

const filters = reactive({
  dataDate: String(route.query.data_date || ''),
  calculationMethod: String(route.query.calculation_method || ''),
  discipline: String(route.query.discipline || ''),
  building: String(route.query.building || ''),
  floor: String(route.query.floor || ''),
  batchId: route.query.batch_id ? Number(route.query.batch_id) : null as number | null,
  baselinePlanId: route.query.baseline_plan_id ? Number(route.query.baseline_plan_id) : null as number | null,
  status: String(route.query.status || ''),
  systemName: String(route.query.system_name || ''),
  constructionUnit: String(route.query.construction_unit || ''),
})

const MetricBar = defineComponent({
  props: {
    label: { type: String, required: true },
    value: { type: Number as PropType<number | null | undefined>, default: null },
    tone: { type: String, default: 'actual' },
  },
  setup(props) {
    return () =>
      h('div', { class: ['metric-bar', `tone-${props.tone}`] }, [
        h('span', props.label),
        h('i', { style: { width: `${percentValue(props.value)}%` } }),
        h('strong', fmtPercent(props.value)),
      ])
  },
})

const options = computed(() => dashboard.value?.scope.options ?? { construction_units: [], buildings: [], floors: [], disciplines: [], systems: [], statuses: [] })
const overview = computed(() => dashboard.value?.overview ?? null)
const disciplineCards = computed(() => dashboard.value?.discipline_cards ?? [])
const buildingCards = computed(() => dashboard.value?.building_cards ?? [])
const floorHeatmap = computed(() => dashboard.value?.floor_heatmap ?? [])
const buildingElevation = computed(() => dashboard.value?.building_elevation ?? [])
const delayDistribution = computed(() => dashboard.value?.delay_distribution ?? [])
const delayedItems = computed(() => dashboard.value?.delayed_items ?? [])
const rectificationSummary = computed(() => dashboard.value?.rectification_summary ?? emptySummary)
const floorDetailVisible = ref(false)
const selectedFloorBuilding = ref('')
const selectedFloorDetail = ref<DashboardBuildingElevationFloor | null>(null)
const selectedBuilding = ref(filters.building)
const openRectificationCount = computed(() => rectificationSummary.value.open + rectificationSummary.value.in_progress + rectificationSummary.value.completed)
const unitList = computed(() => {
  const value = dashboard.value?.calculation_context.unit_list
  return Array.isArray(value) && value.length ? value.join('、') : '无'
})
const mainTitle = computed(() => ({ overview: '总体视图', discipline: '专业视图', building: '楼栋视图' }[viewMode.value]))
const visibleBuildingElevation = computed(() => (filters.building ? buildingElevation.value.filter((row) => row.building === filters.building) : buildingElevation.value))
const constructionUnitSegment = computed<string>({
  get: () => filters.constructionUnit || '__ALL__',
  set: (value: string) => {
    const next = value === '__ALL__' ? '' : value
    if (next === filters.constructionUnit) return
    filters.constructionUnit = next
  },
})

let filtersDebounceTimer: ReturnType<typeof setTimeout> | null = null
let skipNextFilterWatch = false
watch(
  () => [
    filters.dataDate,
    filters.calculationMethod,
    filters.discipline,
    filters.building,
    filters.floor,
    filters.batchId,
    filters.baselinePlanId,
    filters.status,
    filters.systemName,
    filters.constructionUnit,
  ],
  () => {
    if (skipNextFilterWatch) {
      skipNextFilterWatch = false
      return
    }
    if (filtersDebounceTimer) clearTimeout(filtersDebounceTimer)
    filtersDebounceTimer = setTimeout(() => {
      filtersDebounceTimer = null
      loadDashboard()
    }, 250)
  },
)
const maxVisibleFloorCount = computed(() => visibleBuildingElevation.value.reduce((max, row) => Math.max(max, row.floors.length), 0))
const isCompactElevation = computed(() => maxVisibleFloorCount.value > 8)
const elevationContainerMaxHeight = computed(() => `${Math.max(420, Math.min(640, Math.round((typeof window === 'undefined' ? 560 : window.innerHeight) - 290)))}px`)
const selectedBuildingName = computed(() => {
  if (filters.building) return filters.building
  if (selectedBuilding.value && buildingElevation.value.some((row) => row.building === selectedBuilding.value)) return selectedBuilding.value
  return buildingElevation.value[0]?.building || ''
})
const selectedElevation = computed(() => {
  if (!buildingElevation.value.length) return null
  return buildingElevation.value.find((row) => row.building === selectedBuildingName.value) ?? buildingElevation.value[0]
})
const floorDetailTitle = computed(() => selectedFloorDetail.value ? `${selectedFloorBuilding.value} ${selectedFloorDetail.value.floor} 楼层详情` : '楼层详情')
const calculationDiagnostics = computed(() => dashboard.value?.calculation_diagnostics ?? {})
const dashboardCapabilities = computed(() => dashboard.value?.dashboard_capabilities ?? {})
const adaptationMessages = computed(() => {
  const rows: string[] = []
  const building = dashboardCapabilities.value.building_view
  const floor = dashboardCapabilities.value.floor_heatmap
  const weighted = dashboardCapabilities.value.weighted_percent
  const quantity = dashboardCapabilities.value.quantity_percent
  if (building && !building.available) rows.push(building.reason)
  if (floor && !floor.available) rows.push(floor.reason)
  if (weighted && !weighted.available) rows.push('当前批次未识别到权重字段，系统已使用百分比平均、工程量统计或任务平均等可用口径。')
  if (quantity?.available && quantity.reason.includes('多种单位')) rows.push(quantity.reason)
  return rows
})
const capabilityRows = computed(() => {
  const labels: Record<string, string> = {
    overview: '总体视图',
    discipline_view: '专业视图',
    building_view: '楼栋视图',
    floor_heatmap: '楼层热力图',
    construction_unit_filter: '施工单位筛选',
    weighted_percent: '权重统计',
    quantity_percent: '工程量统计',
    percent_average: '百分比平均',
  }
  return Object.entries(dashboardCapabilities.value).map(([key, value]) => ({ key, label: labels[key] || key, ...value }))
})
const weightDiagnosticText = computed(() => {
  const value = (calculationDiagnostics.value as any).weight_diagnostics
  if (!value) return '-'
  return `有效 ${value.valid_weight_task_count ?? 0} / 缺失 ${value.missing_weight_task_count ?? 0}`
})

const kpiCards = computed(() => [
  { label: '当前实际进度', value: fmtPercent(overview.value?.actual_percent) },
  { label: '按计划应完成进度', value: fmtPercent(overview.value?.planned_percent) },
  { label: '进度偏差', value: signedPercent(overview.value?.progress_deviation), className: delayClass(overview.value?.progress_deviation) },
  { label: '任务数量', value: String(overview.value?.item_count ?? 0) },
  { label: '滞后任务数', value: String(delayedItems.value.length) },
  { label: '未关闭整改项', value: String(openRectificationCount.value) },
])

const activeFilterTags = computed(() => {
  const rows = [
    filters.dataDate && `日期：${filters.dataDate}`,
    filters.calculationMethod && `口径：${filters.calculationMethod}`,
    filters.discipline && `专业：${filters.discipline}`,
    filters.building && `楼栋：${filters.building}`,
    filters.floor && `楼层：${filters.floor}`,
    filters.status && `状态：${statusText(filters.status)}`,
    filters.systemName && `系统：${filters.systemName}`,
    filters.constructionUnit && `施工单位：${filters.constructionUnit}`,
  ]
  return rows.filter(Boolean) as string[]
})
const currentScopeText = computed(() => {
  const rows = [
    dashboard.value?.scope.scope_label || '项目级聚合',
    filters.building,
    filters.floor,
    filters.discipline,
    filters.systemName,
    filters.constructionUnit,
  ].filter(Boolean)
  return rows.join(' / ')
})
const activeFloorLabel = computed(() => [filters.building, filters.floor].filter(Boolean).join(' / '))

const statusOptions = [
  { value: 'ahead', label: '超前' },
  { value: 'normal', label: '正常' },
  { value: 'slightly_delayed', label: '轻微滞后' },
  { value: 'delayed', label: '明显滞后' },
  { value: 'delayed_or_worse', label: '明显及以上滞后' },
  { value: 'any_delayed', label: '全部滞后' },
  { value: 'seriously_delayed', label: '严重滞后' },
  { value: 'not_started_by_plan', label: '计划开始时间未到，暂不纳入滞后判断' },
]

const delayQuickFilters = [
  { value: 'seriously_delayed', label: '严重', tip: '只看严重滞后任务和楼层' },
  { value: 'delayed_or_worse', label: '明显+', tip: '只看明显滞后和严重滞后' },
  { value: 'any_delayed', label: '全部滞后', tip: '包含轻微、明显、严重滞后' },
]

const elevationLegend = [
  { status: 'normal', label: '正常 / 超前' },
  { status: 'slightly_delayed', label: '轻微滞后' },
  { status: 'delayed', label: '明显滞后' },
  { status: 'seriously_delayed', label: '严重滞后' },
  { status: 'not_started_by_plan', label: '未到计划开始' },
  { status: 'no_data', label: '无数据' },
]

const emptySummary = { total: 0, open: 0, in_progress: 0, completed: 0, closed: 0, overdue: 0, unresolved: 0, critical: 0, warning: 0, info: 0 }

watch(viewMode, () => loadDashboard())
watch(buildingElevation, (rows) => {
  if (filters.building) {
    selectedBuilding.value = filters.building
  } else if (selectedBuilding.value && !rows.some((row) => row.building === selectedBuilding.value)) {
    selectedBuilding.value = rows[0]?.building || ''
  } else if (!selectedBuilding.value) {
    selectedBuilding.value = rows[0]?.building || ''
  }
})

onMounted(async () => {
  await Promise.all([
    loadDashboard(),
    getAnalyticsTrend(projectId).then((data) => {
      batchOptions.value = data.rows
    }).catch(() => undefined),
    listBaselinePlans(projectId).then((data) => {
      baselineOptions.value = data
    }).catch(() => undefined),
  ])
})

async function loadDashboard() {
  loading.value = true
  errorMessage.value = ''
  try {
    dashboard.value = await getDashboardV2(projectId, {
      viewMode: viewMode.value,
      dataDate: filters.dataDate || null,
      batchId: filters.batchId,
      constructionUnit: filters.constructionUnit || null,
      building: filters.building || null,
      floor: filters.floor || null,
      discipline: filters.discipline || null,
      systemName: filters.systemName || null,
      status: filters.status || null,
      baselinePlanId: filters.baselinePlanId,
      calculationMethod: filters.calculationMethod || null,
    })
    router.replace({ path: route.path, query: buildRouteQuery() })
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '新版看板加载失败'
  } finally {
    loading.value = false
  }
}

function buildRouteQuery() {
  const query: Record<string, string> = { view: viewMode.value }
  if (filters.dataDate) query.data_date = filters.dataDate
  if (filters.calculationMethod) query.calculation_method = filters.calculationMethod
  if (filters.discipline) query.discipline = filters.discipline
  if (filters.building) query.building = filters.building
  if (filters.floor) query.floor = filters.floor
  if (filters.batchId) query.batch_id = String(filters.batchId)
  if (filters.baselinePlanId) query.baseline_plan_id = String(filters.baselinePlanId)
  if (filters.status) query.status = filters.status
  if (filters.systemName) query.system_name = filters.systemName
  if (filters.constructionUnit) query.construction_unit = filters.constructionUnit
  return query
}

function resetFilters() {
  skipNextFilterWatch = true
  filters.discipline = ''
  filters.building = ''
  filters.floor = ''
  filters.batchId = null
  filters.baselinePlanId = null
  filters.status = ''
  filters.systemName = ''
  filters.constructionUnit = ''
  loadDashboard()
}

function selectDiscipline(name: string) {
  skipNextFilterWatch = true
  if (filters.floor) {
    filters.floor = ''
    ElMessage.info('已切换专业，楼层筛选已清除。')
  }
  filters.discipline = name
  viewMode.value = 'discipline'
  loadDashboard()
}

function selectBuilding(name: string) {
  selectedBuilding.value = name
  viewMode.value = 'building'
}

function applyBuildingFilter(name: string) {
  skipNextFilterWatch = true
  filters.building = name
  filters.floor = ''
  selectedBuilding.value = name
  viewMode.value = 'building'
  loadDashboard()
}

function clearBuildingFilter() {
  skipNextFilterWatch = true
  filters.building = ''
  filters.floor = ''
  viewMode.value = 'building'
  loadDashboard()
}

function applyFloorFilter(building?: string | null, floor?: string | null) {
  skipNextFilterWatch = true
  if (building) {
    filters.building = building
    selectedBuilding.value = building
  }
  if (floor) filters.floor = floor
  viewMode.value = 'building'
  loadDashboard()
}

function applySelectedFloorFilter() {
  if (!selectedFloorDetail.value) return
  applyFloorFilter(selectedFloorBuilding.value, selectedFloorDetail.value.floor)
  floorDetailVisible.value = false
}

function clearFloorFilter() {
  skipNextFilterWatch = true
  filters.floor = ''
  loadDashboard()
}

function applyDelayQuickFilter(status: string) {
  skipNextFilterWatch = true
  filters.status = status
  viewMode.value = 'building'
  loadDashboard()
}

function clearDelayFilter() {
  skipNextFilterWatch = true
  filters.status = ''
  loadDashboard()
}

function applyFloorDelayFilter(status: string) {
  if (!selectedFloorDetail.value) return
  skipNextFilterWatch = true
  filters.building = selectedFloorBuilding.value
  filters.floor = selectedFloorDetail.value.floor
  filters.status = status
  selectedBuilding.value = selectedFloorBuilding.value
  viewMode.value = 'building'
  floorDetailVisible.value = false
  loadDashboard()
}

function closeFloorDetail() {
  floorDetailVisible.value = false
}

function openFloorDetail(building: string, floor: DashboardBuildingElevationFloor) {
  selectedFloorBuilding.value = building
  selectedFloorDetail.value = floor
  floorDetailVisible.value = true
}

function goProgressItemsForFloor() {
  if (!selectedFloorDetail.value) return
  router.push({
    path: `/projects/${projectId}/progress-items`,
    query: buildScopeQuery({
      building: selectedFloorBuilding.value,
      floor: selectedFloorDetail.value.floor,
    }),
  })
}

function goProgressItem(row: { task_name?: string | null; task_code?: string | null; wbs_code?: string | null; delay_level?: string | null }) {
  router.push({
    path: `/projects/${projectId}/progress-items`,
    query: buildScopeQuery({
      building: selectedFloorBuilding.value,
      floor: selectedFloorDetail.value?.floor,
      status: row.delay_level || filters.status || undefined,
      keyword: row.task_code || row.wbs_code || row.task_name || undefined,
    }),
  })
}

function goRectificationsForFloor() {
  if (!selectedFloorDetail.value) return
  router.push({
    path: `/projects/${projectId}/rectifications`,
    query: {
      ...buildScopeQuery({
        building: selectedFloorBuilding.value,
        floor: selectedFloorDetail.value.floor,
      }),
      building: selectedFloorBuilding.value,
      floor: selectedFloorDetail.value.floor,
      ...(filters.status ? { delay_level: filters.status } : {}),
    },
  })
}

async function handleExport() {
  await exportCurrentDashboard(filters.building || null, filters.floor || null)
}

async function handleExportSelectedFloor() {
  if (!selectedFloorDetail.value) return
  await exportCurrentDashboard(selectedFloorBuilding.value, selectedFloorDetail.value.floor)
}

async function exportCurrentDashboard(building: string | null, floor: string | null) {
  exporting.value = true
  try {
    const scopeQuery = buildScopeQuery({
      building,
      floor,
    })
    const fileName = await exportDashboardReport(projectId, filters.batchId, null, filters.baselinePlanId, building, {
      constructionUnit: filters.constructionUnit || null,
      discipline: filters.discipline || null,
      floor,
      systemName: filters.systemName || null,
      delayLevel: filters.status || null,
      calculationMethod: filters.calculationMethod || null,
      scope: scopeQuery.scope || null,
      dataDate: scopeQuery.data_date || null,
      importGroupId: scopeQuery.import_group_id || null,
      batchIds: scopeQuery.batch_ids || null,
    })
    ElMessage.success(`已导出：${fileName}`)
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : '导出失败')
  } finally {
    exporting.value = false
  }
}

function buildScopeQuery(overrides: Record<string, string | null | undefined> = {}) {
  const included = overview.value?.included_batches ?? []
  const query: Record<string, string> = {}
  if (filters.batchId) {
    query.scope = 'batch'
    query.batch_id = String(filters.batchId)
  } else {
    query.scope = 'project'
    const dataDate = filters.dataDate || included.find((batch) => batch.data_date)?.data_date || dashboard.value?.scope.filters.data_date || ''
    const groupIds = Array.from(new Set(included.map((batch) => batch.import_group_id).filter(Boolean))) as string[]
    const batchIds = included.map((batch) => batch.batch_id).filter(Boolean)
    if (dataDate) query.data_date = dataDate
    if (groupIds.length === 1) {
      query.import_group_id = groupIds[0]
    } else if (batchIds.length) {
      query.batch_ids = batchIds.join(',')
    }
  }
  if (filters.discipline) query.discipline = filters.discipline
  if (filters.systemName) query.system_name = filters.systemName
  if (filters.status) query.status = filters.status
  if (filters.constructionUnit) query.construction_unit = filters.constructionUnit
  if (filters.calculationMethod) query.calculation_method = filters.calculationMethod
  Object.entries(overrides).forEach(([key, value]) => {
    if (value) query[key] = value
  })
  return query
}

function batchLabel(batch: AnalyticsTrendPoint) {
  const date = batch.data_date || '未填写日期'
  const sheet = batch.sheet_name || `批次 ${batch.batch_id}`
  return `${date} / ${sheet}`
}

function fmtPercent(value?: number | null) {
  return value === null || value === undefined || Number.isNaN(value) ? '-' : `${Number(value).toFixed(1)}%`
}

function signedPercent(value?: number | null) {
  if (value === null || value === undefined || Number.isNaN(value)) return '-'
  return `${value > 0 ? '+' : ''}${Number(value).toFixed(1)}%`
}

function percentValue(value?: number | null) {
  if (value === null || value === undefined || Number.isNaN(value)) return 0
  return Math.max(0, Math.min(100, Number(value)))
}

function delayClass(value?: number | null) {
  if (value === null || value === undefined) return 'is-gray'
  if (value < -20) return 'is-red'
  if (value < -10) return 'is-orange'
  if (value < -5) return 'is-yellow'
  return 'is-green'
}

function statusLabel(value?: number | null) {
  if (value === null || value === undefined) return '未到计划开始'
  if (value < -20) return '严重滞后'
  if (value < -10) return '明显滞后'
  if (value < -5) return '轻微滞后'
  return value > 0 ? '超前' : '正常'
}

function statusText(value?: string | null) {
  return statusOptions.find((item) => item.value === value)?.label || value || '-'
}

function statusTagType(value?: number | null) {
  if (value === null || value === undefined) return 'info'
  if (value < -20) return 'danger'
  if (value < -5) return 'warning'
  return 'success'
}

function statusClass(status?: string | null) {
  if (status === 'seriously_delayed') return 'is-red'
  if (status === 'delayed_or_worse' || status === 'any_delayed') return 'is-orange'
  if (status === 'delayed') return 'is-orange'
  if (status === 'slightly_delayed') return 'is-yellow'
  if (status === 'not_started_by_plan') return 'is-gray'
  if (status === 'no_data' || status === 'unknown') return 'is-light-gray'
  return 'is-green'
}

function floorDensityClass(count: number) {
  if (count > 15) return 'floor-compact'
  if (count > 8) return 'floor-medium'
  return 'floor-comfortable'
}

function elevationModeClass(count: number) {
  if (count > 15) return 'elevation-tight'
  if (count > 8) return 'elevation-medium'
  return 'elevation-comfortable'
}

function disciplineTooltip(row: DashboardUnifiedStatRow) {
  return [
    `专业：${row.name}`,
    `任务数：${row.task_count}`,
    `当前实际进度：${fmtPercent(row.actual_percent)}`,
    `按计划应完成进度：${fmtPercent(row.planned_percent)}`,
    `偏差：${signedPercent(row.progress_deviation)}`,
    `滞后项数量：${row.delayed_count}`,
  ].join(' | ')
}

function floorTooltip(building: string, floor: DashboardBuildingElevationFloor) {
  return [
    `楼栋：${building}`,
    `楼层：${floor.floor}`,
    `任务数：${floor.task_count}`,
    `当前实际进度：${fmtPercent(floor.actual_percent)}`,
    `按计划应完成进度：${fmtPercent(floor.planned_percent)}`,
    `偏差：${signedPercent(floor.progress_deviation)}`,
    `严重滞后数：${floor.serious_delayed_count}`,
    `未到计划开始数：${floor.not_started_count}`,
  ].join(' | ')
}

function floorCellTitle(cell: DashboardUnifiedMatrixRow) {
  return [
    `楼栋：${cell.building || '-'}`,
    `楼层：${cell.floor || '-'}`,
    `任务数：${cell.task_count}`,
    `当前实际进度：${fmtPercent(cell.actual_percent)}`,
    `按计划应完成进度：${fmtPercent(cell.planned_percent)}`,
    `偏差：${signedPercent(cell.progress_deviation)}`,
    `状态：${cell.status_label || statusLabel(cell.progress_deviation)}`,
    `严重滞后数：${cell.serious_delayed_count ?? 0}`,
    `滞后任务数：${cell.delayed_count}`,
    `未到计划开始数：${cell.not_started_count ?? 0}`,
  ].join(' | ')
}

function floorCellStatusText(cell: DashboardUnifiedMatrixRow) {
  const status = cell.status_label || statusLabel(cell.progress_deviation)
  const serious = cell.serious_delayed_count ?? 0
  const delayed = cell.delayed_count ?? 0
  if (serious > 0) return `${status} · 严重 ${serious}`
  if (delayed > 0) return `${status} · 滞后 ${delayed}`
  return status
}

function delayPercent(count: number) {
  const total = delayDistribution.value.reduce((sum, row) => sum + row.count, 0)
  return total ? (count / total) * 100 : 0
}

function contextText(key: string) {
  const value = dashboard.value?.calculation_context[key]
  return typeof value === 'string' && value ? value : '-'
}

function contextNumber(key: string) {
  const value = dashboard.value?.calculation_context[key]
  return typeof value === 'number' ? Number(value).toFixed(key.includes('count') ? 0 : 4) : '-'
}

function contextBool(key: string) {
  return dashboard.value?.calculation_context[key] ? '是' : '否'
}

function diagnosticText(key: string) {
  const value = calculationDiagnostics.value[key]
  return typeof value === 'string' && value ? value : '-'
}

function diagnosticRate(key: string) {
  const summary = (calculationDiagnostics.value as any).field_completeness_summary
  const value = summary?.[key]
  return typeof value === 'number' ? `${Math.round(value * 100)}%` : '-'
}
</script>

<style scoped>
.dashboard-v2-shell {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.header-actions,
.v2-filter-actions {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.v2-filter-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
  gap: 12px;
}

.v2-advanced {
  margin-top: 4px;
  border: 0;
}

.v2-filter-actions {
  margin-top: 12px;
}

.scope-summary {
  color: #374151;
  font-size: 13px;
  font-weight: 600;
  max-width: 100%;
}

.spacer {
  flex: 1;
}

.v2-tabs {
  margin-bottom: -8px;
}

.v2-kpi-grid {
  display: grid;
  grid-template-columns: repeat(6, minmax(120px, 1fr));
  gap: 12px;
}

.v2-kpi-card,
.v2-panel {
  border-radius: 8px;
}

.v2-kpi-card {
  background: #ffffff;
  border: 1px solid #dde4ee;
  padding: 14px;
  min-height: 88px;
}

.v2-kpi-card span,
.v2-panel-header span,
.context-list dt,
.progress-row-card small,
.building-card small {
  color: #6b7280;
  font-size: 12px;
}

.v2-kpi-card strong {
  display: block;
  margin-top: 10px;
  font-size: 24px;
  color: #111827;
}

.v2-main-grid,
.v2-lower-grid {
  display: grid;
  grid-template-columns: minmax(0, 1.8fr) minmax(300px, 0.8fr);
  gap: 16px;
}

.v2-main-grid.is-building-mode {
  grid-template-columns: minmax(0, 1fr);
}

.v2-lower-grid {
  grid-template-columns: repeat(3, minmax(0, 1fr));
}

.v2-panel-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}

.v2-panel-header h2 {
  margin: 0;
  font-size: 16px;
}

.overview-visuals,
.building-view {
  display: grid;
  gap: 16px;
}

.v2-progress-hero {
  display: flex;
  align-items: center;
  gap: 20px;
}

.v2-progress-hero strong {
  display: block;
  font-size: 28px;
}

.compare-bars,
.contribution-list,
.discipline-view,
.delay-distribution,
.context-list {
  display: grid;
  gap: 10px;
}

.metric-bar {
  display: grid;
  grid-template-columns: 96px minmax(120px, 1fr) 70px;
  gap: 10px;
  align-items: center;
  min-height: 38px;
}

.metric-bar span,
.metric-bar strong {
  white-space: nowrap;
}

.metric-bar i,
.contribution-list i {
  height: 10px;
  border-radius: 999px;
  background: #2563eb;
}

.tone-plan i {
  background: #64748b;
}

.tone-seriously_delayed i,
.tone-delayed i {
  background: #dc2626;
}

.tone-slightly_delayed i {
  background: #d97706;
}

.tone-normal i,
.tone-ahead i {
  background: #16a34a;
}

.contribution-list button,
.progress-row-card,
.building-card,
.floor-cell,
.floor-slab {
  border: 1px solid #dde4ee;
  background: #ffffff;
  border-radius: 8px;
  cursor: pointer;
}

.contribution-list button {
  display: grid;
  grid-template-columns: 120px minmax(120px, 1fr) 70px;
  gap: 10px;
  align-items: center;
  min-height: 46px;
  padding: 10px;
  text-align: left;
}

.contribution-list button span {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.discipline-view {
  grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
  gap: 16px;
}

.progress-row-card {
  display: grid;
  gap: 12px;
  padding: 12px;
  text-align: left;
  min-height: 184px;
  width: 100%;
}

.discipline-card-header {
  display: grid;
  grid-template-columns: 12px minmax(0, 1fr) auto;
  gap: 8px;
  align-items: center;
}

.discipline-card-header strong,
.building-card strong,
.tower-title strong {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.discipline-progress-row,
.discipline-summary-row {
  display: grid;
  gap: 10px;
}

.discipline-progress-row {
  grid-template-columns: repeat(2, minmax(0, 1fr));
}

.discipline-progress-value {
  min-width: 0;
  padding: 10px;
  border: 1px solid #e5e7eb;
  border-radius: 6px;
  background: #f8fafc;
}

.discipline-progress-value span,
.discipline-summary-row span {
  color: #6b7280;
  font-size: 12px;
}

.discipline-progress-value strong {
  display: block;
  margin-top: 6px;
  color: #111827;
  font-size: 20px;
  line-height: 1.1;
  white-space: nowrap;
}

.discipline-summary-row {
  grid-template-columns: repeat(3, minmax(0, 1fr));
}

.discipline-summary-row span {
  padding: 8px 10px;
  border-radius: 6px;
  background: #f8fafc;
  white-space: nowrap;
}

.status-dot {
  width: 10px;
  height: 10px;
  border-radius: 999px;
  display: inline-block;
}

.floor-heatmap {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(130px, 1fr));
  gap: 8px;
}

.floor-cell {
  min-height: 72px;
  padding: 10px;
  text-align: left;
}

.floor-cell span {
  display: block;
  margin-top: 8px;
}

.floor-cell small {
  display: block;
  margin-top: 6px;
  color: currentColor;
  font-size: 12px;
  opacity: 0.82;
}

.is-green {
  color: #166534;
  background-color: #dcfce7;
}

.is-yellow {
  color: #854d0e;
  background-color: #fef3c7;
}

.is-orange {
  color: #9a3412;
  background-color: #ffedd5;
}

.is-red {
  color: #991b1b;
  background-color: #fee2e2;
}

.is-gray {
  color: #4b5563;
  background-color: #f3f4f6;
}

.is-light-gray {
  color: #6b7280;
  background-color: #f8fafc;
}

.building-view-toolbar {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  align-items: center;
  flex-wrap: wrap;
}

.building-view-toolbar small {
  color: #6b7280;
}

.building-view-actions {
  display: inline-flex;
  align-items: center;
  justify-content: flex-end;
  gap: 8px;
  flex-wrap: wrap;
}

.delay-quick-actions {
  display: inline-flex;
  flex-wrap: wrap;
}

.construction-unit-bar {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
  padding: 10px 14px;
  margin-top: 8px;
  border-radius: 12px;
  background: rgba(241, 245, 249, 0.6);
  border: 1px solid rgba(203, 213, 225, 0.4);
}

.construction-unit-label {
  color: #475569;
  font-size: 13px;
  font-weight: 500;
  flex-shrink: 0;
}

.elevation-legend {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
}

.elevation-legend span {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  color: #374151;
  font-size: 12px;
}

.elevation-legend i {
  width: 14px;
  height: 14px;
  border: 1px solid #cbd5e1;
  border-radius: 3px;
}

.empty-elevation {
  padding: 28px;
  border: 1px dashed #cbd5e1;
  border-radius: 8px;
  color: #64748b;
  text-align: center;
}

.building-elevation-layout {
  display: grid;
  gap: 16px;
}

.compact-elevation-tip {
  margin-bottom: 2px;
}

.building-view-top {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(260px, 320px);
  gap: 16px;
  align-items: start;
}

.building-view-scroll {
  max-height: var(--elevation-container-max-height, 560px);
  overflow-x: auto;
  overflow-y: auto;
  padding: 2px 2px 6px;
}

.building-cards {
  display: grid;
  grid-auto-flow: column;
  grid-auto-columns: minmax(180px, 220px);
  align-content: start;
  gap: 10px;
  max-width: 100%;
  overflow-x: auto;
  overflow-y: hidden;
  padding-right: 4px;
}

.building-card {
  display: grid;
  gap: 8px;
  padding: 12px;
  text-align: left;
}

.building-card.active {
  border-color: #2563eb;
  box-shadow: inset 3px 0 0 #2563eb;
}

.building-card.filtered {
  background: #eff6ff;
}

.building-25d-stage {
  display: flex;
  align-items: stretch;
  justify-content: flex-start;
  gap: 24px;
  min-height: 460px;
  max-height: var(--elevation-container-max-height, 560px);
  overflow-x: auto;
  overflow-y: auto;
  padding: 22px 24px 28px;
  background: #f8fafc;
  border: 1px solid #dde4ee;
  border-radius: 8px;
}

.building-25d-stage.compact {
  align-items: flex-start;
}

.building-tower {
  min-width: 160px;
  display: grid;
  gap: 8px;
  align-content: start;
}

.tower-title {
  border: 0;
  background: #ffffff;
  display: grid;
  gap: 3px;
  text-align: center;
  cursor: pointer;
  border-radius: 6px;
  padding: 8px;
  border: 1px solid transparent;
  position: sticky;
  top: 0;
  z-index: 2;
}

.tower-title.active {
  border-color: #2563eb;
  color: #1d4ed8;
}

.tower-title.filtered {
  background: #eff6ff;
}

.tower-title span {
  color: #6b7280;
  font-size: 12px;
}

.tower-body {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 12px 10px 18px;
  background: linear-gradient(90deg, #eef2f7, #ffffff 42%, #e2e8f0);
  border: 1px solid #cbd5e1;
  border-radius: 8px 8px 4px 4px;
}

.floor-slab {
  width: 128px;
  min-height: 40px;
  margin-bottom: -2px;
  padding: 5px 9px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  border: 1px solid rgba(15, 23, 42, 0.16);
  border-radius: 4px;
  box-shadow: 7px 6px 0 rgba(15, 23, 42, 0.1);
  transform: skewX(-10deg);
}

.floor-slab.floor-medium {
  min-height: 34px;
}

.floor-slab.floor-compact {
  min-height: 26px;
  padding-block: 3px;
}

.floor-slab span,
.floor-slab strong {
  transform: skewX(10deg);
  font-size: 12px;
  white-space: nowrap;
}

.floor-slab.selected {
  outline: 3px solid #2563eb;
  outline-offset: 2px;
  z-index: 1;
}

.elevation-comfortable .floor-slab {
  min-height: 42px;
}

.elevation-medium .floor-slab {
  min-height: 34px;
}

.elevation-tight .floor-slab {
  min-height: 26px;
}

.building-summary-panel {
  padding: 14px;
  border: 1px solid #dde4ee;
  border-radius: 8px;
  background: #ffffff;
  position: sticky;
  top: 12px;
}

.building-summary-panel h3,
.floor-detail h3 {
  margin: 0 0 12px;
  font-size: 15px;
}

.building-summary-panel dl,
.floor-detail-grid {
  display: grid;
  gap: 10px;
  margin: 0;
}

.building-summary-panel dl div,
.floor-detail-grid div {
  display: grid;
  grid-template-columns: 92px 1fr;
  gap: 8px;
}

.building-summary-panel dt,
.floor-detail-grid dt {
  color: #6b7280;
}

.building-summary-panel dd,
.floor-detail-grid dd {
  margin: 0;
}

.building-summary-actions {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  margin-top: 12px;
  flex-wrap: wrap;
}

.floor-detail {
  display: grid;
  gap: 14px;
}

.floor-detail-grid {
  grid-template-columns: repeat(2, minmax(0, 1fr));
}

.floor-detail-actions {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  flex-wrap: wrap;
}

.context-text {
  margin: 0 0 10px;
  color: #374151;
}

.context-list {
  margin: 0;
}

.context-list div {
  display: grid;
  grid-template-columns: 120px 1fr;
  gap: 8px;
}

.context-list dd {
  margin: 0;
  color: #111827;
}

.rectification-summary {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 10px;
}

.rectification-summary span {
  padding: 14px;
  border: 1px solid #dde4ee;
  border-radius: 8px;
}

@media (max-width: 1100px) {
  .v2-kpi-grid,
  .v2-main-grid,
  .v2-lower-grid {
    grid-template-columns: 1fr;
  }

  .discipline-view {
    grid-template-columns: 1fr;
  }

  .building-elevation-layout,
  .floor-detail-grid {
    grid-template-columns: 1fr;
  }

  .building-view-top {
    grid-template-columns: 1fr;
  }

  .building-cards {
    grid-auto-flow: column;
    grid-auto-columns: minmax(170px, 220px);
    overflow-x: auto;
    overflow-y: hidden;
  }

  .building-view-scroll {
    max-height: none;
  }
}

@media (max-width: 680px) {
  .discipline-progress-row,
  .discipline-summary-row {
    grid-template-columns: 1fr;
  }

  .metric-bar {
    grid-template-columns: 52px minmax(0, 1fr);
    row-gap: 6px;
  }

  .metric-bar i {
    grid-column: 1 / -1;
  }

  .building-25d-stage {
    max-height: 520px;
    padding: 12px;
  }

  .floor-slab {
    width: 110px;
  }

  .metric-bar strong {
    grid-column: 2;
    grid-row: 1;
    justify-self: end;
  }

  .contribution-list button {
    grid-template-columns: minmax(0, 1fr) 64px;
  }

  .contribution-list button i {
    grid-column: 1 / -1;
    order: 3;
  }
}
</style>
