<template>
  <main class="print-page" v-loading="loading">
    <div class="print-actions">
      <el-button type="primary" @click="printPage">打印</el-button>
      <el-button @click="router.push(`/projects/${projectId}/dashboard`)">返回 Dashboard</el-button>
    </div>

    <el-alert v-if="errorMessage" :title="errorMessage" type="error" show-icon :closable="false" />

    <section class="print-title">
      <p>工程进度看板打印版</p>
      <h1>{{ projectName || '项目进度看板' }}</h1>
      <div class="print-meta">
        <span>数据日期：{{ currentBatch?.data_date || '-' }}</span>
        <span>当前批次：{{ currentBatchLabel }}</span>
        <span>计划基线：{{ baselineName }}</span>
      </div>
    </section>

    <section class="print-section">
      <h2>总体指标</h2>
      <div class="metric-grid">
        <div>
          <span>实际进度</span>
          <strong>{{ percentText(overview?.actual_percent) }}</strong>
        </div>
        <div>
          <span>应完成进度</span>
          <strong>{{ percentText(overview?.planned_percent) }}</strong>
        </div>
        <div>
          <span>进度偏差</span>
          <strong>{{ signedPercentText(overview?.progress_deviation) }}</strong>
        </div>
        <div>
          <span>任务数量</span>
          <strong>{{ overview?.task_count ?? '-' }}</strong>
        </div>
        <div>
          <span>批次状态</span>
          <strong>{{ overview?.batch_status_label || (overview?.batch_is_frozen ? '已冻结' : '正常') }}</strong>
        </div>
        <div>
          <span>数据质量</span>
          <strong>{{ dataQuality?.data_quality_score ?? '-' }}</strong>
        </div>
      </div>
    </section>

    <section class="print-section">
      <h2>进度分析说明</h2>
      <p>{{ insight?.overview_summary || '暂无总体进度说明。' }}</p>
      <div class="summary-grid">
        <div>
          <h3>专业</h3>
          <p>{{ insight?.discipline_summary || '-' }}</p>
        </div>
        <div>
          <h3>楼层</h3>
          <p>{{ insight?.floor_summary || '-' }}</p>
        </div>
        <div>
          <h3>楼栋楼层</h3>
          <p>{{ insight?.building_floor_summary || '-' }}</p>
        </div>
        <div>
          <h3>数据质量</h3>
          <p>{{ insight?.quality_summary || '-' }}</p>
        </div>
      </div>
    </section>

    <section class="print-section">
      <h2>主要滞后项</h2>
      <table>
        <thead>
          <tr>
            <th>专业</th>
            <th>楼栋</th>
            <th>楼层</th>
            <th>施工项</th>
            <th>实际</th>
            <th>计划</th>
            <th>偏差</th>
            <th>状态</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="row in delayedRows" :key="row.id">
            <td>{{ row.discipline || '-' }}</td>
            <td>{{ row.building || '-' }}</td>
            <td>{{ row.floor || '-' }}</td>
            <td>{{ row.task_name || '-' }}</td>
            <td>{{ percentText(row.actual_percent) }}</td>
            <td>{{ percentText(row.planned_percent) }}</td>
            <td>{{ signedPercentText(row.progress_deviation) }}</td>
            <td>{{ row.delay_level_label || statusLabel(row.delay_level) }}</td>
          </tr>
          <tr v-if="!delayedRows.length">
            <td colspan="8">当前批次暂无滞后项。</td>
          </tr>
        </tbody>
      </table>
    </section>

    <section class="print-section">
      <h2>整改闭环摘要</h2>
      <div class="metric-grid compact">
        <div>
          <span>全部整改项</span>
          <strong>{{ rectificationSummary?.total ?? 0 }}</strong>
        </div>
        <div>
          <span>整改中</span>
          <strong>{{ rectificationSummary?.in_progress ?? 0 }}</strong>
        </div>
        <div>
          <span>已完成</span>
          <strong>{{ rectificationSummary?.completed ?? 0 }}</strong>
        </div>
        <div>
          <span>已关闭</span>
          <strong>{{ rectificationSummary?.closed ?? 0 }}</strong>
        </div>
        <div>
          <span>逾期</span>
          <strong>{{ rectificationSummary?.overdue ?? 0 }}</strong>
        </div>
      </div>
    </section>

    <section class="print-section">
      <h2>专业统计</h2>
      <table>
        <thead>
          <tr>
            <th>专业</th>
            <th>任务数</th>
            <th>实际进度</th>
            <th>应完成进度</th>
            <th>进度偏差</th>
            <th>滞后任务数</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="row in disciplineRows" :key="row.dimension_value || row.name || 'blank'">
            <td>{{ row.dimension_value || row.name || '-' }}</td>
            <td>{{ row.count }}</td>
            <td>{{ percentText(row.actual_percent) }}</td>
            <td>{{ percentText(row.planned_percent) }}</td>
            <td>{{ signedPercentText(row.progress_deviation) }}</td>
            <td>{{ row.delayed_count ?? 0 }}</td>
          </tr>
        </tbody>
      </table>
    </section>

    <section class="print-section">
      <h2>楼层统计</h2>
      <table>
        <thead>
          <tr>
            <th>楼层</th>
            <th>任务数</th>
            <th>实际进度</th>
            <th>应完成进度</th>
            <th>进度偏差</th>
            <th>滞后任务数</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="row in floorRows" :key="row.dimension_value || row.floor || 'blank'">
            <td>{{ row.dimension_value || row.floor || '-' }}</td>
            <td>{{ row.count }}</td>
            <td>{{ percentText(row.actual_percent) }}</td>
            <td>{{ percentText(row.planned_percent) }}</td>
            <td>{{ signedPercentText(row.progress_deviation) }}</td>
            <td>{{ row.delayed_count ?? 0 }}</td>
          </tr>
        </tbody>
      </table>
    </section>
  </main>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  getAnalyticsDataQuality,
  getAnalyticsDelayedRanking,
  getAnalyticsGroupBy,
  getAnalyticsInsight,
  getAnalyticsOverviewWithBaseline,
  getAnalyticsTrend,
} from '../api/analytics'
import { getProject } from '../api/projects'
import { getRectificationSummary } from '../api/rectifications'
import type {
  AnalyticsDataQualityResponse,
  AnalyticsDelayedItem,
  AnalyticsGroupRow,
  AnalyticsInsightResponse,
  AnalyticsOverviewResponse,
  AnalyticsTrendPoint,
} from '../types/analytics'
import type { RectificationSummary } from '../types/rectification'

const route = useRoute()
const router = useRouter()
const projectId = Number(route.params.id)

const loading = ref(false)
const errorMessage = ref('')
const projectName = ref('')
const trend = ref<AnalyticsTrendPoint[]>([])
const selectedBatchId = ref<number | null>(null)
const overview = ref<AnalyticsOverviewResponse | null>(null)
const dataQuality = ref<AnalyticsDataQualityResponse | null>(null)
const insight = ref<AnalyticsInsightResponse | null>(null)
const disciplineRows = ref<AnalyticsGroupRow[]>([])
const floorRows = ref<AnalyticsGroupRow[]>([])
const delayedRows = ref<AnalyticsDelayedItem[]>([])
const rectificationSummary = ref<RectificationSummary | null>(null)

const currentBatch = computed(() => trend.value.find((batch) => batch.batch_id === selectedBatchId.value) ?? null)
const currentBatchLabel = computed(() => {
  const batch = currentBatch.value
  if (!batch) return '-'
  const date = batch.data_date || batch.published_at?.slice(0, 10) || `批次 ${batch.batch_id}`
  return `${date}｜${batch.sheet_name || `#${batch.batch_id}`}`
})
const baselineName = computed(() => overview.value?.current_view_baseline_plan_name || overview.value?.baseline_plan_name || currentBatch.value?.baseline_plan_name || '未配置计划基线')

function percentText(value?: number | null) {
  return value === null || value === undefined ? '-' : `${Number(value).toFixed(1)}%`
}

function signedPercentText(value?: number | null) {
  return value === null || value === undefined ? '-' : `${Number(value) > 0 ? '+' : ''}${Number(value).toFixed(1)}%`
}

function statusLabel(value?: string | null) {
  const labels: Record<string, string> = {
    slightly_delayed: '轻微滞后',
    delayed: '明显滞后',
    seriously_delayed: '严重滞后',
    not_started_by_plan: '未到计划开始',
    missing_plan_dates: '缺少计划日期',
    invalid_plan_dates: '计划日期异常',
    seriously_delay: '严重滞后',
  }
  return labels[value || ''] || '-'
}

function printPage() {
  window.print()
}

async function loadPrintData() {
  loading.value = true
  errorMessage.value = ''
  try {
    const project = await getProject(projectId)
    projectName.value = project.name
    const loadedTrend = await getAnalyticsTrend(projectId)
    trend.value = loadedTrend.rows
    const queryBatchId = Number(route.query.batch_id)
    selectedBatchId.value = Number.isFinite(queryBatchId) && queryBatchId > 0 ? queryBatchId : loadedTrend.rows.at(-1)?.batch_id ?? null
    if (!selectedBatchId.value) {
      errorMessage.value = '当前项目暂无已发布批次，无法生成打印视图。'
      return
    }
    const [loadedOverview, loadedQuality, loadedInsight, disciplineGroup, floorGroup, delayed, rectification] = await Promise.all([
      getAnalyticsOverviewWithBaseline(projectId, selectedBatchId.value, null, null),
      getAnalyticsDataQuality(projectId, selectedBatchId.value),
      getAnalyticsInsight(projectId, { batchId: selectedBatchId.value, calculationProfileId: null, baselinePlanId: null, building: null }).catch(() => null),
      getAnalyticsGroupBy(projectId, { batchId: selectedBatchId.value, dimension: 'discipline', metric: 'actual_percent', aggregation: 'avg' }),
      getAnalyticsGroupBy(projectId, { batchId: selectedBatchId.value, dimension: 'floor', metric: 'actual_percent', aggregation: 'avg' }),
      getAnalyticsDelayedRanking(projectId, selectedBatchId.value, 10, null),
      getRectificationSummary(projectId, selectedBatchId.value).catch(() => null),
    ])
    overview.value = loadedOverview
    dataQuality.value = loadedQuality
    insight.value = loadedInsight
    disciplineRows.value = disciplineGroup.rows
    floorRows.value = floorGroup.rows
    delayedRows.value = delayed.rows
    rectificationSummary.value = rectification
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '打印视图加载失败。'
  } finally {
    loading.value = false
  }
}

onMounted(loadPrintData)
</script>

<style scoped>
.print-page {
  max-width: 980px;
  margin: 0 auto;
  padding: 24px;
  color: #111827;
  background: #ffffff;
}

.print-actions {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  margin-bottom: 16px;
}

.print-title {
  padding-bottom: 16px;
  border-bottom: 2px solid #111827;
}

.print-title p {
  margin: 0 0 6px;
  color: #4b5563;
  font-size: 13px;
}

.print-title h1 {
  margin: 0;
  font-size: 28px;
  line-height: 1.25;
}

.print-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 12px 20px;
  margin-top: 12px;
  color: #374151;
  font-size: 13px;
}

.print-section {
  break-inside: avoid;
  margin-top: 22px;
}

.print-section h2 {
  margin: 0 0 10px;
  font-size: 17px;
}

.print-section h3 {
  margin: 0 0 6px;
  font-size: 13px;
}

.print-section p {
  margin: 0;
  line-height: 1.7;
}

.metric-grid,
.summary-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 10px;
}

.metric-grid div,
.summary-grid div {
  border: 1px solid #111827;
  padding: 10px;
  min-height: 62px;
}

.metric-grid.compact {
  grid-template-columns: repeat(5, minmax(0, 1fr));
}

.metric-grid span {
  display: block;
  color: #4b5563;
  font-size: 12px;
}

.metric-grid strong {
  display: block;
  margin-top: 6px;
  font-size: 20px;
}

table {
  width: 100%;
  border-collapse: collapse;
  font-size: 12px;
}

th,
td {
  border: 1px solid #111827;
  padding: 6px 8px;
  text-align: left;
  vertical-align: top;
}

th {
  background: #f3f4f6;
  font-weight: 700;
}

@media print {
  :global(.layout-sidebar),
  .print-actions {
    display: none !important;
  }

  :global(.layout-main) {
    padding: 0 !important;
    background: #ffffff !important;
  }

  .print-page {
    max-width: none;
    padding: 0;
  }

  body {
    background: #ffffff !important;
  }

  @page {
    size: A4;
    margin: 14mm;
  }
}
</style>
