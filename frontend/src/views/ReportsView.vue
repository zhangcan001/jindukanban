<template>
  <main class="page-shell dashboard-shell">
    <section class="page-heading">
      <div>
        <p class="eyebrow">reports</p>
        <h1>报表中心</h1>
      </div>
      <div class="toolbar">
        <el-button @click="router.push(`/projects/${projectId}/dashboard`)">返回看板</el-button>
        <el-button @click="router.push(`/projects/${projectId}`)">项目详情</el-button>
        <el-button @click="scrollToSettings">报表设置</el-button>
        <el-button type="primary" :loading="loading" :disabled="loading" @click="loadAll">刷新</el-button>
      </div>
    </section>

    <el-alert v-if="errorMessage" :title="errorMessage" type="error" show-icon :closable="false" />

    <el-tabs v-model="activeTab" class="reports-tabs" @tab-change="handleTabChange">
      <el-tab-pane label="生成与预览" name="export">
        <section class="form-surface dashboard-controls" v-loading="loading">
      <el-form-item label="发布批次">
        <el-select v-model="selectedBatchId" placeholder="最近发布批次" clearable>
          <el-option v-for="batch in batchOptions" :key="batch.batch_id" :label="batchLabel(batch)" :value="batch.batch_id" />
        </el-select>
      </el-form-item>
      <el-form-item label="统计口径">
        <el-select v-model="selectedProfileId" placeholder="项目默认口径" clearable>
          <el-option v-for="profile in profiles" :key="profile.id" :label="profile.name" :value="profile.id" />
        </el-select>
      </el-form-item>
      <el-form-item label="计划基线">
        <el-select v-if="baselines.length" v-model="selectedBaselineId" placeholder="批次默认基线" clearable>
          <el-option v-for="baseline in baselines" :key="baseline.id" :label="baseline.name" :value="baseline.id" />
        </el-select>
        <span v-else class="muted-text">未配置计划基线</span>
      </el-form-item>
    </section>

    <section class="report-grid">
      <div v-for="report in reportCards" :key="report.type" class="form-surface report-item">
        <div>
          <h2>{{ report.label }}</h2>
          <p>{{ report.description }}</p>
          <p class="report-scene">适用场景：{{ report.scene }}</p>
          <span class="muted-text">最近导出：{{ latestExportTime(report.type) }}</span>
          <span class="muted-text">最近文件：{{ latestExportName(report.type) }}</span>
          <span class="muted-text">用途：{{ report.use }}</span>
        </div>
        <div class="report-actions">
          <el-button
            :loading="previewLoading === report.type"
            :disabled="Boolean(previewLoading) || Boolean(exporting)"
            @click="openPreview(report.type)"
          >
            预览
          </el-button>
          <el-button
            type="primary"
            :loading="exporting === report.type"
            :disabled="Boolean(exporting) || requiresBatch(report.type) && !selectedBatchId"
            @click="openExportPreview(report.type)"
          >
            导出
          </el-button>
          <el-button @click="scrollToHistory(report.type)">查看历史</el-button>
          <el-switch
            v-if="report.type === 'weekly_word' && aiConfig.enabled"
            v-model="useAiWeeklyText"
            active-text="使用 AI 优化周报文字"
            inactive-text="使用 AI 优化周报文字"
          />
        </div>
      </div>
      <div class="form-surface report-item report-history-card">
        <div>
          <h2>报表历史</h2>
          <p>集中查看当前项目所有导出记录，适合追溯会议材料和定位本地文件。</p>
          <p class="report-scene">适用场景：会后归档、复查导出文件、复制文件路径。</p>
          <span class="muted-text">当前记录：{{ exports.length }} 条</span>
          <span class="muted-text">最近导出：{{ exports[0]?.exported_at ?? '暂无导出记录。' }}</span>
        </div>
        <div class="report-actions">
          <el-button type="primary" @click="scrollToHistory()">查看历史</el-button>
          <el-button @click="loadHistory">刷新历史</el-button>
        </div>
      </div>
    </section>

    <section class="form-surface report-preview" v-loading="Boolean(previewLoading)">
      <div class="section-title">
        <h2>{{ preview?.title || '报表预览' }}</h2>
        <span>轻量摘要</span>
      </div>
      <el-empty v-if="!preview" description="选择报表卡片中的预览，查看导出前摘要。" />
        <div v-else class="preview-grid">
          <div v-for="item in preview.items" :key="item.label">
            <span>{{ item.label }}</span>
            <strong>{{ previewValue(item.value) }}</strong>
          </div>
        </div>
      </section>
      </el-tab-pane>

      <el-tab-pane label="报表配置" name="config">
      <section ref="settingsSection" class="form-surface report-settings">
      <div class="section-title">
        <h2>报表设置</h2>
        <span>项目级</span>
      </div>
      <el-form v-if="reportConfig" label-width="210px">
        <el-form-item label="Word 周报包含进阶图表分析">
          <el-switch v-model="reportConfig.include_advanced_chart_analysis" />
        </el-form-item>
        <el-form-item label="使用 AI 优化周报文字">
          <el-switch v-model="reportConfig.use_ai_weekly_text" />
        </el-form-item>
        <el-form-item label="Word 周报滞后项最大条数">
          <el-input-number v-model="reportConfig.weekly_delayed_item_limit" :min="0" :max="200" />
        </el-form-item>
        <el-form-item label="Word 周报矩阵摘要最大条数">
          <el-input-number v-model="reportConfig.weekly_matrix_summary_limit" :min="0" :max="50" />
        </el-form-item>
        <el-form-item label="显示数据质量章节">
          <el-switch v-model="reportConfig.show_data_quality_section" />
        </el-form-item>
        <el-form-item label="显示整改闭环摘要">
          <el-switch v-model="reportConfig.show_rectification_summary" />
        </el-form-item>
        <el-form-item label="默认导出格式">
          <el-segmented v-model="reportConfig.default_export_format" :options="['xlsx', 'docx']" />
        </el-form-item>
        <el-form-item label="文件名包含项目名称">
          <el-switch v-model="reportConfig.file_name_include_project_name" />
        </el-form-item>
        <el-form-item label="文件名包含数据日期">
          <el-switch v-model="reportConfig.file_name_include_data_date" />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" :loading="savingConfig" :disabled="savingConfig" @click="saveReportConfig">保存设置</el-button>
        </el-form-item>
      </el-form>
    </section>
      </el-tab-pane>

      <el-tab-pane label="AI 配置" name="ai">
      <section class="table-surface">
      <div class="section-title">
        <h2>AI 提示词模板</h2>
        <span>内置模板可复制后修改</span>
      </div>
      <el-alert v-if="aiConfig.enabled" :title="aiSafetyNotice" type="warning" show-icon :closable="false" />
      <div class="actions-row" style="margin: 12px 0;">
        <el-button :loading="templatesLoading" :disabled="templatesLoading" @click="loadTemplates">刷新模板</el-button>
        <el-button type="primary" @click="openTemplateEditor()">新建模板</el-button>
      </div>
      <el-table v-loading="templatesLoading" :data="promptTemplates" empty-text="暂无模板记录。可从内置模板复制后再调整。">
        <el-table-column prop="name" label="名称" min-width="180" />
        <el-table-column prop="code" label="代码" width="160" />
        <el-table-column prop="description" label="说明" min-width="220" show-overflow-tooltip />
        <el-table-column label="类型" width="110">
          <template #default="{ row }">
            <el-tag :type="row.is_builtin ? 'info' : 'success'">{{ row.is_builtin ? '内置' : '自定义' }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="row.is_active ? 'success' : 'warning'">{{ row.is_active ? '启用' : '停用' }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="260">
          <template #default="{ row }">
            <el-button link type="primary" @click="copyTemplate(row)">复制</el-button>
            <el-button link @click="openTemplateEditor(row)">编辑</el-button>
            <el-button link type="danger" :disabled="row.is_builtin" @click="removeTemplate(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </section>

    <section class="form-surface report-settings">
      <div class="section-title">
        <h2>AI 辅助设置</h2>
        <span>{{ aiStatusText }}</span>
      </div>
      <el-alert
        v-if="!aiConfig.enabled"
        title="AI 辅助当前关闭。周报会使用系统规则化分析，不影响报表导出。"
        type="info"
        show-icon
        :closable="false"
      />
      <el-alert
        v-else-if="!aiConfig.api_key_set"
        title="AI 已开启但未配置 API Key，周报会自动回退到规则化分析。"
        type="warning"
        show-icon
        :closable="false"
      />
      <el-form label-width="160px">
        <el-form-item label="是否启用 AI">
          <el-switch v-model="aiConfig.enabled" />
        </el-form-item>
        <el-form-item label="API Base URL">
          <el-input v-model="aiConfig.api_base_url" placeholder="例如：https://api.example.com" />
        </el-form-item>
        <el-form-item label="API Key">
          <el-input v-model="apiKeyDraft" type="password" show-password :placeholder="aiConfig.api_key_set ? '已配置，留空则保留现有密钥' : '未配置 API Key'" />
        </el-form-item>
        <el-form-item label="最近一次测试">
          <span>{{ aiConfig.last_test_result || '暂无测试记录' }}</span>
        </el-form-item>
        <el-form-item label="最近一次调用">
          <span>{{ aiConfig.last_call_at || '暂无调用记录' }}</span>
        </el-form-item>
        <el-form-item label="Model">
          <el-input v-model="aiConfig.model" placeholder="例如：gpt-4o-mini 或兼容模型名" />
        </el-form-item>
        <el-form-item label="超时时间">
          <el-input-number v-model="aiConfig.timeout_seconds" :min="1" :max="120" />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" :loading="savingAiConfig" :disabled="savingAiConfig" @click="saveAiConfig">保存 AI 设置</el-button>
          <el-button :loading="testingAiConfig" :disabled="testingAiConfig || savingAiConfig" @click="handleTestAiConnection">测试连接</el-button>
          <el-button :loading="savingAiConfig" :disabled="savingAiConfig || !aiConfig.api_key_set" @click="clearAiKey">清空 API Key</el-button>
        </el-form-item>
      </el-form>
    </section>
      </el-tab-pane>

      <el-tab-pane label="导出历史" name="history">
      <section ref="historySection" class="table-surface">
      <div class="section-title">
        <h2>最近导出记录</h2>
        <span>{{ visibleExports.length }} / {{ exports.length }} 条</span>
      </div>
      <div class="history-filters">
        <el-select v-model="historyFilter" placeholder="报表类型" clearable @change="loadHistory">
          <el-option v-for="report in reportCards" :key="report.type" :label="report.label" :value="report.type" />
        </el-select>
        <el-input v-model="historyProjectName" placeholder="项目" clearable @keyup.enter="loadHistory" />
        <el-date-picker v-model="historyDateRange" type="daterange" start-placeholder="开始日期" end-placeholder="结束日期" value-format="YYYY-MM-DD" />
        <el-input v-model="historyKeyword" placeholder="关键词" clearable @keyup.enter="loadHistory" />
        <el-button type="primary" :loading="historyLoading" :disabled="historyLoading" @click="loadHistory">筛选</el-button>
        <el-button :disabled="historyLoading" @click="resetHistoryFilters">重置</el-button>
      </div>
      <el-empty v-if="!historyLoading && !exports.length" description="当前还没有导出记录，导出报表后会显示在这里。" />
      <el-table v-else v-loading="historyLoading" :data="pagedExports" height="420" empty-text="当前筛选条件下暂无报表历史。">
        <el-table-column prop="exported_at" label="导出时间" width="180" />
        <el-table-column label="报表类型" width="170">
          <template #default="{ row }">{{ reportTypeLabel(row.report_type) }}</template>
        </el-table-column>
        <el-table-column prop="file_name" label="文件名" min-width="280" show-overflow-tooltip />
        <el-table-column prop="file_path" label="文件路径" min-width="320" show-overflow-tooltip />
        <el-table-column prop="data_date" label="数据日期" width="120" />
        <el-table-column label="所属项目" width="160">
          <template #default>{{ projectName }}</template>
        </el-table-column>
        <el-table-column label="操作" width="220" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" @click="copyPath(row.file_path)">复制路径</el-button>
            <el-button link type="primary" @click="detailRecord = row">查看详情</el-button>
            <el-button link type="primary" @click="openFolder(row.file_path)">打开目录</el-button>
          </template>
        </el-table-column>
      </el-table>
      <el-pagination
        v-if="visibleExports.length"
        v-model:current-page="historyPage"
        v-model:page-size="historyPageSize"
        class="table-pagination"
        layout="total, sizes, prev, pager, next"
        :total="visibleExports.length"
        :page-sizes="[20, 50, 100]"
      />
    </section>
      </el-tab-pane>
    </el-tabs>

    <el-dialog v-model="detailVisible" title="导出详情" width="560px">
      <div v-if="detailRecord" class="preview-grid">
        <div><span>导出时间</span><strong>{{ detailRecord.exported_at }}</strong></div>
        <div><span>报表类型</span><strong>{{ reportTypeLabel(detailRecord.report_type) }}</strong></div>
        <div><span>项目名称</span><strong>{{ projectName }}</strong></div>
        <div><span>数据日期</span><strong>{{ detailRecord.data_date || '-' }}</strong></div>
        <div><span>文件名</span><strong>{{ detailRecord.file_name || '-' }}</strong></div>
        <div><span>文件路径</span><strong>{{ detailRecord.file_path || '-' }}</strong></div>
      </div>
    </el-dialog>

    <el-dialog v-model="previewDialogVisible" :title="previewDialogTitle" width="720px">
      <el-alert
        v-if="previewMode === 'export'"
        title="请确认预览信息无误后导出。导出成功后可在报表历史中查看记录。"
        type="info"
        show-icon
        :closable="false"
      />
      <div v-loading="Boolean(previewLoading)" class="preview-dialog-body">
        <el-empty v-if="!preview" description="暂无预览信息。" />
        <div v-else class="preview-grid">
          <div v-for="item in enhancedPreviewItems" :key="item.label">
            <span>{{ item.label }}</span>
            <strong>{{ previewValue(item.value) }}</strong>
          </div>
        </div>
      </div>
      <template #footer>
        <el-button @click="previewDialogVisible = false">关闭</el-button>
        <el-button
          v-if="previewMode === 'export' && previewReportType"
          type="primary"
          :loading="exporting === previewReportType"
          :disabled="Boolean(exporting) || !canExportPreview"
          @click="download(previewReportType)"
        >
          确认导出
        </el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="weeklyPreviewVisible" title="Word 周报 AI 预览" width="760px">
      <el-alert v-if="aiConfig.enabled" :title="aiSafetyNotice" type="warning" show-icon :closable="false" />
      <pre class="preview-ai-text">{{ weeklyPreviewText }}</pre>
      <template #footer>
        <el-button @click="weeklyPreviewVisible = false">取消</el-button>
        <el-button type="primary" @click="confirmWeeklyDownload">确认导出</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="templateEditorVisible" title="AI 提示词模板" width="720px">
      <el-form label-width="120px">
        <el-form-item label="名称"><el-input v-model="templateForm.name" /></el-form-item>
        <el-form-item label="代码"><el-input v-model="templateForm.code" :disabled="Boolean(templateForm.id && !templateForm.is_builtin)" /></el-form-item>
        <el-form-item label="说明"><el-input v-model="templateForm.description" type="textarea" :autosize="{ minRows: 2, maxRows: 4 }" /></el-form-item>
        <el-form-item label="提示词">
          <el-input v-model="templateForm.prompt_template" type="textarea" :autosize="{ minRows: 6, maxRows: 12 }" />
        </el-form-item>
        <el-form-item label="启用">
          <el-switch v-model="templateForm.is_active" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="templateEditorVisible = false">取消</el-button>
        <el-button type="primary" :loading="savingTemplate" @click="saveTemplate">保存</el-button>
      </template>
    </el-dialog>
  </main>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'

import { getAnalyticsTrend } from '../api/analytics'
import {
  createAiPromptTemplate,
  copyAiPromptTemplate,
  deleteAiPromptTemplate,
  generateWeeklyAiPreview,
  getAiConfig,
  listAiPromptTemplates,
  testAiConnection,
  updateAiConfig,
  updateAiPromptTemplate,
} from '../api/ai'
import { listBaselinePlans } from '../api/baselinePlans'
import { listCalculationProfiles } from '../api/calculationProfiles'
import { exportReportWithBaseline, getReportConfig, listReportExports, previewReport, updateReportConfig } from '../api/reports'
import { useProjectStore } from '../stores/useProjectStore'
import type { AnalyticsTrendPoint } from '../types/analytics'
import type { BaselinePlan } from '../types/baselinePlan'
import type { CalculationProfile } from '../types/calculationProfile'
import type { ReportConfig, ReportExportRecord, ReportPreview, ReportType } from '../types/report'
import type { AiConfigPayload, AiPromptTemplate } from '../types/ai'

const route = useRoute()
const router = useRouter()
const projectId = Number(route.params.id)
const projectStore = useProjectStore()

const activeTab = ref<'export' | 'config' | 'ai' | 'history'>('export')
const aiTabLoaded = ref(false)
const historyTabLoaded = ref(false)

const batchOptions = ref<AnalyticsTrendPoint[]>([])
const profiles = ref<CalculationProfile[]>([])
const baselines = ref<BaselinePlan[]>([])
const exports = ref<ReportExportRecord[]>([])
const projectName = ref('')
const selectedBatchId = ref<number | null>(null)
const selectedProfileId = ref<number | null>(null)
const selectedBaselineId = ref<number | null>(null)
const exporting = ref<ReportType | ''>('')
const loading = ref(false)
const historyLoading = ref(false)
const templatesLoading = ref(false)
const previewLoading = ref<ReportType | ''>('')
const errorMessage = ref('')
const reportConfig = ref<ReportConfig | null>(null)
const savingConfig = ref(false)
const savingAiConfig = ref(false)
const testingAiConfig = ref(false)
const useAiWeeklyText = ref(false)
const historyFilter = ref<ReportType | ''>('')
const historyProjectName = ref('')
const historyDateRange = ref<[string, string] | null>(null)
const historyKeyword = ref('')
const historyPage = ref(1)
const historyPageSize = ref(20)
const historySection = ref<HTMLElement | null>(null)
const settingsSection = ref<HTMLElement | null>(null)
const preview = ref<ReportPreview | null>(null)
const previewDialogVisible = ref(false)
const previewMode = ref<'view' | 'export'>('view')
const previewReportType = ref<ReportType | null>(null)
const apiKeyDraft = ref('')
const promptTemplates = ref<AiPromptTemplate[]>([])
const weeklyPreviewVisible = ref(false)
const weeklyPreviewText = ref('')
const pendingWeeklyDownload = ref(false)
const templateEditorVisible = ref(false)
const savingTemplate = ref(false)
const templateForm = reactive<Partial<AiPromptTemplate>>({
  name: '',
  code: 'dashboard_summary',
  description: '',
  prompt_template: '',
  is_active: true,
})
const aiConfig = reactive({
  enabled: false,
  api_base_url: '',
  api_key_set: false,
  model: '',
  timeout_seconds: 20,
  last_test_result: '',
  last_test_at: '',
  last_call_at: '',
})
const aiSafetyNotice = 'AI 辅助生成内容仅供参考，请结合现场实际复核。请勿上传敏感数据或涉密工程资料到外部 AI 服务。'
const detailRecord = ref<ReportExportRecord | null>(null)
const detailVisible = computed({
  get: () => Boolean(detailRecord.value),
  set: (value: boolean) => {
    if (!value) detailRecord.value = null
  },
})

const reportCards: Array<{ type: ReportType; label: string; description: string; scene: string; use: string }> = [
  { type: 'dashboard_excel', label: '当前看板 Excel', description: '汇总 Dashboard 原模块、整改摘要和进阶图表 Sheet。', scene: '周例会前快速固化当前看板数据。', use: '适合数据核对和内部分析。' },
  { type: 'weekly_word', label: 'Word 周报', description: '生成会议汇报用周报，包含进度说明和进阶图表分析。', scene: '项目周会、甲方汇报、内部例会材料。', use: '适合会议汇报和监理周报。' },
  { type: 'weekly_pdf', label: 'PDF 周报', description: '生成适合打印、归档和传阅的进度周报 PDF。', scene: '项目周会归档、纸质签批、对外报送材料。', use: '适合归档和打印。' },
  { type: 'rectification_tracking', label: '整改跟踪表', description: '导出整改闭环跟踪明细、责任人、计划完成时间和逾期状态。', scene: '现场整改跟踪、责任派发、闭环复盘。', use: '适合跟踪问题闭环。' },
  { type: 'delay_rectification_excel', label: '整改清单', description: '按当前批次输出滞后项整改清单，便于现场派发。', scene: '滞后任务专项梳理和现场整改派单。', use: '适合下发施工单位。' },
]

const visibleExports = computed(() => (historyFilter.value ? exports.value.filter((item) => normalizeReportType(item.report_type) === historyFilter.value) : exports.value))
const pagedExports = computed(() => visibleExports.value.slice((historyPage.value - 1) * historyPageSize.value, historyPage.value * historyPageSize.value))
const aiStatusText = computed(() => (aiConfig.enabled && aiConfig.api_key_set ? 'AI 辅助已配置' : '未启用 AI 辅助'))
const selectedBatch = computed(() => batchOptions.value.find((batch) => batch.batch_id === selectedBatchId.value) ?? null)
const selectedBaseline = computed(() => baselines.value.find((baseline) => baseline.id === selectedBaselineId.value) ?? null)
const previewDialogTitle = computed(() => preview.value?.title || (previewMode.value === 'export' ? '导出预览' : '报表预览'))
const enhancedPreviewItems = computed(() => {
  const items = [...(preview.value?.items ?? [])]
  const labels = new Set(items.map((item) => item.label))
  if (previewReportType.value === 'weekly_word' || previewReportType.value === 'weekly_pdf') {
    if (!labels.has('Sheet 名称')) items.splice(2, 0, { label: 'Sheet 名称', value: selectedBatch.value?.sheet_name || '-' })
    if (!labels.has('是否包含数据质量章节')) items.push({ label: '是否包含数据质量章节', value: reportConfig.value?.show_data_quality_section ?? false })
    if (previewReportType.value === 'weekly_word' && !labels.has('是否使用 AI 辅助')) items.push({ label: '是否使用 AI 辅助', value: useAiWeeklyText.value })
    if (!labels.has('主要滞后项条数')) items.push({ label: '主要滞后项条数', value: reportConfig.value?.weekly_delayed_item_limit ?? '-' })
    if (!labels.has('矩阵摘要条数')) items.push({ label: '矩阵摘要条数', value: reportConfig.value?.weekly_matrix_summary_limit ?? '-' })
  }
  if (previewReportType.value === 'dashboard_excel') {
    if (!labels.has('当前计划基线')) items.push({ label: '当前计划基线', value: selectedBaseline.value?.name || selectedBatch.value?.baseline_plan_name || '未配置计划基线' })
  }
  if (previewReportType.value === 'rectification_tracking') {
    if (!labels.has('是否包含操作记录摘要')) items.push({ label: '是否包含操作记录摘要', value: true })
  }
  return items
})
const canExportPreview = computed(() => {
  if (!previewReportType.value) return false
  if (requiresBatch(previewReportType.value) && !selectedBatchId.value) return false
  const countItem = enhancedPreviewItems.value.find((item) => item.label.includes('数量') || item.label.includes('条数'))
  if (previewReportType.value === 'rectification_tracking' && Number(countItem?.value ?? 0) <= 0) return false
  return true
})

function batchLabel(batch: AnalyticsTrendPoint) {
  const date = batch.data_date || batch.published_at?.slice(0, 10) || `批次 ${batch.batch_id}`
  const sheet = batch.sheet_name || `#${batch.batch_id}`
  const baseline = batch.baseline_plan_name || '未配置计划基线'
  return `${date}｜${sheet}｜计划基线：${baseline}`
}

async function loadAll() {
  loading.value = true
  errorMessage.value = ''
  try {
    // 核心:导出 tab 所需数据先拉齐。AI 模板 / 历史 tab 仍延迟到激活时再拉。
    const [trend, loadedProfiles, loadedBaselines, project, config, loadedAiConfig] = await Promise.all([
      getAnalyticsTrend(projectId),
      listCalculationProfiles(projectId),
      listBaselinePlans(projectId),
      projectStore.loadProject(projectId),
      getReportConfig(projectId),
      getAiConfig(projectId),
    ])
    batchOptions.value = trend.rows
    profiles.value = loadedProfiles
    baselines.value = loadedBaselines
    if (!project) {
      throw new Error(projectStore.state.lastError ?? '项目信息加载失败')
    }
    projectName.value = project.name
    reportConfig.value = config
    Object.assign(aiConfig, loadedAiConfig)
    if (!aiConfig.enabled) useAiWeeklyText.value = false
    selectedBatchId.value ||= trend.rows.at(-1)?.batch_id ?? null
    selectedProfileId.value ||= loadedProfiles.find((profile) => profile.is_default)?.id ?? null
    selectedBaselineId.value ||= loadedBaselines.find((baseline) => baseline.is_default)?.id ?? null
    // 当前激活 tab 的延迟数据(刷新时重新拉一遍当前 tab 内容,避免点"刷新"按钮后看到旧数据)
    if (activeTab.value === 'ai') {
      await loadAiTab(true)
    } else if (activeTab.value === 'history') {
      await loadHistoryTab(true)
    }
  } catch (error) {
    errorMessage.value = friendlyReportError(error, '报表中心加载失败')
  } finally {
    loading.value = false
  }
}

async function loadAiTab(force = false) {
  if (aiTabLoaded.value && !force) return
  try {
    const [loadedAiConfig, loadedTemplates] = await Promise.all([
      getAiConfig(projectId),
      listAiPromptTemplates(projectId),
    ])
    Object.assign(aiConfig, loadedAiConfig)
    if (!aiConfig.enabled) useAiWeeklyText.value = false
    promptTemplates.value = loadedTemplates
    apiKeyDraft.value = ''
    aiTabLoaded.value = true
  } catch (error) {
    errorMessage.value = friendlyReportError(error, 'AI 配置加载失败')
  }
}

async function loadHistoryTab(force = false) {
  if (historyTabLoaded.value && !force) return
  await loadHistory()
  historyTabLoaded.value = true
}

function handleTabChange(name: string | number) {
  const tab = String(name) as typeof activeTab.value
  if (tab === 'ai') {
    void loadAiTab()
  } else if (tab === 'history') {
    void loadHistoryTab()
  }
}

function aiConfigPayload(): AiConfigPayload {
  const payload: AiConfigPayload = {
    enabled: aiConfig.enabled,
    api_base_url: aiConfig.api_base_url || null,
    model: aiConfig.model || null,
    timeout_seconds: aiConfig.timeout_seconds,
  }
  if (apiKeyDraft.value.trim()) payload.api_key = apiKeyDraft.value.trim()
  return payload
}

async function saveAiConfig() {
  savingAiConfig.value = true
  try {
    const updated = await updateAiConfig(projectId, aiConfigPayload())
    Object.assign(aiConfig, updated)
    if (!aiConfig.enabled) useAiWeeklyText.value = false
    apiKeyDraft.value = ''
    ElMessage.success('AI 设置已保存')
  } catch (error) {
    errorMessage.value = friendlyReportError(error, '保存 AI 设置失败，请稍后重试。')
  } finally {
    savingAiConfig.value = false
  }
}

async function clearAiKey() {
  savingAiConfig.value = true
  try {
    const updated = await updateAiConfig(projectId, { ...aiConfigPayload(), api_key: '' })
    Object.assign(aiConfig, updated)
    apiKeyDraft.value = ''
    ElMessage.success('API Key 已清空')
  } catch (error) {
    errorMessage.value = friendlyReportError(error, '清空 API Key 失败，请稍后重试。')
  } finally {
    savingAiConfig.value = false
  }
}

async function handleTestAiConnection() {
  testingAiConfig.value = true
  try {
    const result = await testAiConnection(projectId, aiConfigPayload())
    if (result.success) ElMessage.success(result.message)
    else ElMessage.warning(result.message || 'AI 连接测试失败，请检查配置。')
    const updated = await getAiConfig(projectId)
    Object.assign(aiConfig, updated)
  } catch (error) {
    ElMessage.error(`AI 连接测试失败：${error instanceof Error ? error.message : '请检查配置。'}`)
  } finally {
    testingAiConfig.value = false
  }
}

async function loadTemplates() {
  templatesLoading.value = true
  try {
    promptTemplates.value = await listAiPromptTemplates(projectId)
  } catch (error) {
    errorMessage.value = `模板加载失败：${error instanceof Error ? error.message : '请稍后重试。'}`
  } finally {
    templatesLoading.value = false
  }
}

async function copyTemplate(template: AiPromptTemplate) {
  await copyAiPromptTemplate(projectId, template.id)
  ElMessage.success('模板已复制，可继续编辑。')
  await loadTemplates()
}

function openTemplateEditor(template?: AiPromptTemplate) {
  Object.assign(templateForm, template ? { ...template } : {
    id: undefined,
    name: '',
    code: 'dashboard_summary',
    description: '',
    prompt_template: '',
    is_active: true,
    is_builtin: false,
  })
  templateEditorVisible.value = true
}

async function saveTemplate() {
  if (!templateForm.name || !templateForm.code || !templateForm.prompt_template) {
    ElMessage.warning('请填写模板名称、代码和提示词。')
    return
  }
  savingTemplate.value = true
  try {
    if (templateForm.id && !templateForm.is_builtin) {
      await updateAiPromptTemplate(projectId, templateForm.id, templateForm)
    } else {
      await createAiPromptTemplate(projectId, templateForm)
    }
    templateEditorVisible.value = false
    await loadTemplates()
    ElMessage.success('模板已保存')
  } catch (error) {
    ElMessage.error(`保存模板失败：${error instanceof Error ? error.message : '请稍后重试。'}`)
  } finally {
    savingTemplate.value = false
  }
}

async function removeTemplate(template: AiPromptTemplate) {
  await deleteAiPromptTemplate(projectId, template.id)
  ElMessage.success('模板已删除')
  await loadTemplates()
}

async function loadHistory() {
  historyLoading.value = true
  try {
    exports.value = await listReportExports(projectId, {
      reportType: historyFilter.value || null,
      projectName: historyProjectName.value || null,
      dateFrom: historyDateRange.value?.[0] ?? null,
      dateTo: historyDateRange.value?.[1] ?? null,
      keyword: historyKeyword.value || null,
    })
    historyPage.value = 1
  } catch (error) {
    errorMessage.value = friendlyReportError(error, '导出历史加载失败，请稍后重试。')
  } finally {
    historyLoading.value = false
  }
}

function reportCard(reportType: ReportType) {
  return reportCards.find((report) => report.type === reportType)
}

function reportTypeLabel(value: string) {
  const labels: Record<string, string> = {
    overview: '进度总览报表',
    'delayed-ranking': '滞后项报表',
    'discipline-summary': '专业进度报表',
    'progress-items': '进度明细报表',
    dashboard_excel: '当前看板 Excel',
    weekly_word: 'Word 周报',
    weekly_pdf: 'PDF 周报',
    delay_rectification_excel: '滞后项整改清单',
    delay_rectification: '滞后项整改清单',
    rectification_excel: '滞后项整改清单',
    delay_rectification_xlsx: '滞后项整改清单',
    rectification_tracking: '整改跟踪表',
    maintenance_report: '数据维护报告',
  }
  return labels[value] ?? '未知报表类型'
}

function normalizeReportType(value: string): ReportType | '' {
  const aliases: Record<string, ReportType> = {
    dashboard_excel: 'dashboard_excel',
    weekly_word: 'weekly_word',
    weekly_pdf: 'weekly_pdf',
    delay_rectification_excel: 'delay_rectification_excel',
    delay_rectification: 'delay_rectification_excel',
    rectification_excel: 'delay_rectification_excel',
    delay_rectification_xlsx: 'delay_rectification_excel',
    rectification_tracking: 'rectification_tracking',
    maintenance_report: 'maintenance_report',
  }
  return aliases[value] ?? ''
}

function latestExportTime(reportType: ReportType) {
  const record = exports.value.find((item) => normalizeReportType(item.report_type) === reportType)
  return record?.exported_at ?? '暂无'
}

function latestExportName(reportType: ReportType) {
  const record = exports.value.find((item) => normalizeReportType(item.report_type) === reportType)
  return record?.file_name || '暂无导出记录。'
}

function previewValue(value: string | number | boolean | string[] | null) {
  if (Array.isArray(value)) return value.join('、')
  if (typeof value === 'boolean') return value ? '是' : '否'
  return value ?? '-'
}

async function loadPreview(reportType: ReportType) {
  previewLoading.value = reportType
  errorMessage.value = ''
  previewReportType.value = reportType
  try {
    preview.value = await previewReport(projectId, reportType, selectedBatchId.value, selectedProfileId.value, selectedBaselineId.value)
  } catch (error) {
    errorMessage.value = friendlyReportError(error, '预览失败，请稍后重试。')
  } finally {
    previewLoading.value = ''
  }
}

async function openPreview(reportType: ReportType) {
  previewMode.value = 'view'
  previewDialogVisible.value = true
  await loadPreview(reportType)
}

async function openExportPreview(reportType: ReportType) {
  if (requiresBatch(reportType) && !selectedBatchId.value) {
    ElMessage.warning('当前暂无可导出数据。')
    return
  }
  previewMode.value = 'export'
  previewDialogVisible.value = true
  await loadPreview(reportType)
}

function scrollToHistory(reportType?: ReportType) {
  historyFilter.value = reportType ?? ''
  activeTab.value = 'history'
  void loadHistoryTab()
  void loadHistory()
}

function scrollToSettings() {
  activeTab.value = 'config'
}

function resetHistoryFilters() {
  historyFilter.value = ''
  historyProjectName.value = ''
  historyDateRange.value = null
  historyKeyword.value = ''
  loadHistory()
}

async function saveReportConfig() {
  if (!reportConfig.value) return
  savingConfig.value = true
  try {
    reportConfig.value = await updateReportConfig(projectId, reportConfig.value)
    ElMessage.success('报表设置已保存')
  } catch (error) {
    errorMessage.value = `保存失败：${error instanceof Error ? error.message : '请稍后重试。'}`
  } finally {
    savingConfig.value = false
  }
}

async function copyPath(path?: string | null) {
  if (!path) {
    ElMessage.warning('当前记录没有文件路径。')
    return
  }
  await navigator.clipboard.writeText(path)
  ElMessage.success('文件路径已复制。')
}

async function openFolder(path?: string | null) {
  if (!path) {
    ElMessage.warning('当前记录没有文件路径。')
    return
  }
  await navigator.clipboard.writeText(path)
  ElMessage.warning('浏览器可能限制打开本地目录，已复制文件路径，可在资源管理器中粘贴打开。')
}

async function download(reportType: ReportType) {
  if (requiresBatch(reportType) && !selectedBatchId.value) {
    ElMessage.warning('请先选择已发布批次，再导出该报表。')
    return
  }
  if (reportType === 'weekly_word' && useAiWeeklyText.value && !pendingWeeklyDownload.value) {
    await previewWeeklyAiText()
    return
  }
  exporting.value = reportType
  errorMessage.value = ''
  try {
    const fileName = await exportReportWithBaseline(
      projectId,
      reportType,
      selectedBatchId.value,
      selectedProfileId.value,
      selectedBaselineId.value,
      reportType === 'weekly_word' && useAiWeeklyText.value,
    )
    await loadAll()
    previewDialogVisible.value = false
    ElMessage.success(`报表已导出：${fileName}，可在报表历史中查看。`)
  } catch (error) {
    errorMessage.value = `导出失败：${friendlyReportError(error, '报表生成失败，请查看诊断日志。')}`
  } finally {
    exporting.value = ''
    pendingWeeklyDownload.value = false
  }
}

async function previewWeeklyAiText() {
  if (!selectedBatchId.value) {
    ElMessage.warning('请先选择发布批次。')
    return
  }
  exporting.value = 'weekly_word'
  try {
    const result = await generateWeeklyAiPreview(projectId, {
      batch_id: selectedBatchId.value,
      calculation_profile_id: selectedProfileId.value,
      baseline_plan_id: selectedBaselineId.value,
    })
    weeklyPreviewText.value = result.generated_text || result.fallback_text
    weeklyPreviewVisible.value = true
    if (result.source !== 'ai') ElMessage.warning(result.error_message || 'AI 生成失败，已显示规则化分析。')
  } catch (error) {
    ElMessage.error(`AI 周报预览失败：${error instanceof Error ? error.message : '请稍后重试。'}`)
  } finally {
    exporting.value = ''
  }
}

async function confirmWeeklyDownload() {
  weeklyPreviewVisible.value = false
  pendingWeeklyDownload.value = true
  exporting.value = 'weekly_word'
  try {
    const fileName = await exportReportWithBaseline(
      projectId,
      'weekly_word',
      selectedBatchId.value,
      selectedProfileId.value,
      selectedBaselineId.value,
      true,
    )
    await loadAll()
    previewDialogVisible.value = false
    ElMessage.success(`报表已导出：${fileName}，可在报表历史中查看。`)
  } catch (error) {
    errorMessage.value = `导出失败：${friendlyReportError(error, '报表生成失败，请查看诊断日志。')}`
  } finally {
    exporting.value = ''
    pendingWeeklyDownload.value = false
  }
}

function requiresBatch(reportType: ReportType) {
  return reportType !== 'maintenance_report'
}

function friendlyReportError(error: unknown, fallback: string) {
  const message = error instanceof Error ? error.message : fallback
  const text = message || fallback
  if (/failed to fetch|network|fetch/i.test(text)) return '后端服务不可用，请确认系统已启动。'
  if (/traceback|stack trace|exception/i.test(text)) return '系统处理失败，请查看诊断日志。'
  if (/Published import batch not found|NO_PUBLISHED_BATCH/i.test(text)) return '当前暂无可导出数据。'
  if (/NO_RECTIFICATIONS_FOR_FILTER/i.test(text)) return '当前筛选条件下暂无整改项。'
  if (/REPORT_TYPE_NOT_FOUND/i.test(text)) return '报表类型不存在或未注册。'
  if (/BATCH_FROZEN/i.test(text)) return '当前批次已冻结，无法覆盖。'
  if (/FIELD_MAPPINGS_EMPTY/i.test(text)) return '当前数据缺少必要字段，请检查字段映射。'
  return text.replace(/\bNone\b|\bnull\b|\bundefined\b/g, '-')
}

onMounted(loadAll)

onMounted(() => {
  if (route.path.endsWith('/reports/history')) {
    activeTab.value = 'history'
  }
  const batchId = Number(route.query.batch_id)
  if (Number.isFinite(batchId) && batchId > 0) {
    selectedBatchId.value = batchId
  }
})
</script>
