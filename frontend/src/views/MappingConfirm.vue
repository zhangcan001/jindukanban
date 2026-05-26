<template>
  <main class="page-shell">
    <section class="page-heading">
      <div>
        <p class="eyebrow">field mapping</p>
        <h1>字段映射确认</h1>
      </div>
      <el-button @click="router.back()">返回</el-button>
    </section>

    <el-alert v-if="errorMessage" :title="errorMessage" type="error" show-icon :closable="false" />
    <el-alert
      v-if="nonProgressSheetNotice"
      :title="nonProgressSheetNotice"
      type="warning"
      show-icon
      :closable="false"
    />

    <section v-if="parseResult?.matched_templates.length" class="form-surface">
      <div class="section-title">
        <h2>{{ recommendedTemplate ? `推荐模板：${recommendedTemplate.name}` : '历史模板推荐' }}</h2>
        <span>{{ recommendedTemplate ? `匹配度：${Math.round(recommendedTemplate.match_score * 100)}%` : `${parseResult.matched_templates.length} 个可用模板` }}</span>
      </div>
      <el-alert
        v-if="exactMatchTemplate"
        class="parse-hint"
        :title="`列结构与历史模板「${exactMatchTemplate.name}」完全一致${exactMatchTemplate.match_reason ? '，' + exactMatchTemplate.match_reason : ''}，可一键复用映射并直接校验。`"
        type="success"
        show-icon
        :closable="false"
      />
      <el-alert
        v-else-if="recommendedTemplate"
        class="parse-hint"
        :title="hasHighScoreTemplate ? '推荐模板匹配度较高，可直接一键套用后校验。' : '已找到相似模板，但匹配度不高，套用后建议逐项确认。'"
        :type="hasHighScoreTemplate ? 'success' : 'warning'"
        show-icon
        :closable="false"
      />
      <div class="template-list">
        <div
          v-for="template in parseResult.matched_templates"
          :key="template.id"
          class="template-item"
          :class="{
            'template-item-recommended': template.match_score >= 0.8,
            'template-item-exact': template.is_exact_match,
          }"
        >
          <div>
            <strong>{{ template.name }}</strong>
            <el-tag v-if="template.is_exact_match" type="success" effect="dark" size="small" style="margin-left: 8px;">列结构精确匹配</el-tag>
            <span>相似度 {{ Math.round(template.match_score * 100) }}%</span>
            <div v-if="template.match_reason" class="template-reason">{{ template.match_reason }}</div>
          </div>
          <div class="actions-row">
            <el-button
              v-if="template.is_exact_match"
              type="success"
              @click="applyTemplate(template)"
            >一键复用</el-button>
            <el-button v-else type="primary" @click="applyTemplate(template)">套用模板</el-button>
            <el-button @click="previewTemplate(template)">查看模板映射</el-button>
          </div>
        </div>
      </div>
    </section>

    <section class="table-surface">
      <div class="section-title">
        <h2>字段映射表</h2>
        <div class="actions-row">
          <el-button :loading="validating" @click="validateMappings">校验映射</el-button>
          <el-button type="primary" :loading="importValidating" @click="validateImport">导入校验</el-button>
        </div>
      </div>

      <el-alert
        v-if="unmappedFields.length"
        class="parse-hint"
        :title="`未识别字段 ${unmappedFields.length} 个：${unmappedFields.slice(0, 8).join('、')}`"
        type="warning"
        show-icon
        :closable="false"
      />
      <el-alert
        v-if="missingRequiredFields.length"
        class="parse-hint"
        :title="`必填字段缺失：${missingRequiredFields.join('、')}。请补齐后再导入校验。`"
        type="error"
        show-icon
        :closable="false"
      />
      <el-alert
        class="parse-hint"
        title="施工单位、责任人等非核心统计字段可勾选扩展字段保存到 extra_fields，用于追溯原始信息，不参与进度计算。"
        type="info"
        show-icon
        :closable="false"
      />
      <div v-if="fieldDiagnostics" class="diagnostic-grid">
        <div>
          <span>字段识别质量</span>
          <strong>{{ fieldDiagnostics.field_mapping_quality.label }} / {{ Math.round(fieldDiagnostics.field_mapping_quality.score * 100) }}%</strong>
        </div>
        <div>
          <span>推荐统计口径</span>
          <strong>{{ fieldDiagnostics.recommended_calculation_method_name }}</strong>
        </div>
        <div>
          <span>推荐原因</span>
          <strong>{{ fieldDiagnostics.recommended_reason }}</strong>
        </div>
      </div>
      <div v-if="fieldImpacts.length" class="impact-list">
        <div v-for="impact in fieldImpacts" :key="impact.field">
          <el-tag type="warning">{{ impact.field_label }}</el-tag>
          <span>{{ impact.impact }}</span>
        </div>
      </div>

      <el-table :data="roleGroupedMappings" height="560" row-key="excel_column_name">
        <el-table-column prop="field_role" label="字段角色" width="130" />
        <el-table-column prop="excel_column_name" label="Excel 字段" min-width="160" />
        <el-table-column label="样本值" min-width="220">
          <template #default="{ row }">
            <div v-if="row.sample_values?.length" class="sample-values">
              <el-tag
                v-for="sample in row.sample_values.slice(0, 3)"
                :key="`${row.excel_column_name}:${sample}`"
                size="small"
                effect="plain"
              >
                {{ sample }}
              </el-tag>
            </div>
            <span v-else class="muted-text">-</span>
          </template>
        </el-table-column>
        <el-table-column prop="recommended_field" label="推荐字段" min-width="180">
          <template #default="{ row }">
            <span>{{ row.recommended_field || '未识别' }}</span>
            <el-tag
              v-if="row.needs_review"
              size="small"
              type="danger"
              effect="plain"
              style="margin-left: 6px"
              title="该字段由历史纠错、模糊匹配、AI 或样本值推断得到，建议人工确认"
            >需复核</el-tag>
            <el-tag
              v-if="row.alias_source === 'history-exact'"
              size="small"
              type="info"
              effect="plain"
              style="margin-left: 6px"
              title="根据本项目历史导入记录精确匹配"
            >历史命中</el-tag>
            <el-tag
              v-else-if="row.alias_source === 'history-fuzzy'"
              size="small"
              type="warning"
              effect="plain"
              style="margin-left: 6px"
              :title="`相似度 ${Math.round((row.alias_confidence ?? 0) * 100)}% / 历史模糊匹配，建议核对`"
            >近似 {{ Math.round((row.alias_confidence ?? 0) * 100) }}%</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="识别原因" min-width="260">
          <template #default="{ row }">
            <div class="reason-cell">
              <strong>{{ row.match_type || '未识别' }} / {{ row.confidence || '低' }}</strong>
              <span>{{ row.reason || '未命中字段别名或关键词。' }}</span>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="影响" min-width="180">
          <template #default="{ row }">
            <el-tag v-if="row.is_required" type="danger">必填</el-tag>
            <el-tag v-if="row.affects_statistics" type="success">影响统计</el-tag>
            <el-tag v-if="row.affects_delay" type="warning">影响滞后</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="用户选择字段" min-width="190">
          <template #default="{ row }">
            <el-select v-model="row.system_field_name" clearable filterable>
              <el-option v-for="field in systemFields" :key="field.value" :label="field.label" :value="field.value" />
            </el-select>
          </template>
        </el-table-column>
        <el-table-column label="字段类型" width="140">
          <template #default="{ row }">
            <el-select v-model="row.field_type">
              <el-option label="文本" value="text" />
              <el-option label="数值" value="number" />
              <el-option label="日期" value="date" />
              <el-option label="百分比" value="percent" />
              <el-option label="金额" value="currency" />
              <el-option label="未知" value="unknown" />
            </el-select>
          </template>
        </el-table-column>
        <el-table-column label="维度" width="90">
          <template #default="{ row }"><el-checkbox v-model="row.is_dimension" /></template>
        </el-table-column>
        <el-table-column label="指标" width="90">
          <template #default="{ row }"><el-checkbox v-model="row.is_metric" /></template>
        </el-table-column>
        <el-table-column label="扩展字段" width="110">
          <template #default="{ row }"><el-checkbox v-model="row.save_to_extra" /></template>
        </el-table-column>
      </el-table>
    </section>

    <section v-if="issues.length" class="table-surface">
      <div class="section-title">
        <h2>冲突提示</h2>
        <el-tag :type="validationValid ? 'success' : 'danger'">
          {{ validationValid ? '通过' : '有错误' }}
        </el-tag>
      </div>
      <el-table :data="issues">
        <el-table-column prop="level" label="级别" width="100" />
        <el-table-column prop="code" label="代码" width="180" />
        <el-table-column prop="message" label="提示" min-width="360" />
      </el-table>
    </section>

    <section v-if="importIssues.length" class="table-surface">
      <div class="section-title">
        <h2>导入校验结果</h2>
        <div class="actions-row">
          <el-tag type="warning">warning {{ warningCount }}</el-tag>
          <el-tag type="danger">error {{ errorCount }}</el-tag>
          <el-button
            v-if="errorCount + warningCount > 0"
            size="small"
            :loading="downloadingErrorReport"
            @click="downloadErrorReport"
          >下载错误清单 Excel</el-button>
        </div>
      </div>
      <div class="issue-toolbar">
        <el-radio-group v-model="issueFilter" size="small">
          <el-radio-button label="all">全部</el-radio-button>
          <el-radio-button label="error">只看 error</el-radio-button>
          <el-radio-button label="warning">只看 warning</el-radio-button>
        </el-radio-group>
      </div>
      <div class="issue-groups">
        <div v-for="group in groupedImportIssues" :key="`${group.level}:${group.code}`">
          <el-tag :type="group.level === 'error' ? 'danger' : 'warning'">{{ group.level }}</el-tag>
          <strong>{{ group.code }}</strong>
          <span>{{ group.count }} 条</span>
          <p>{{ group.explanation }}</p>
        </div>
      </div>
      <el-table :data="filteredImportIssues" height="360">
        <el-table-column prop="level" label="级别" width="100" />
        <el-table-column prop="row_index" label="行号" width="90" />
        <el-table-column prop="column_name" label="字段" min-width="140" />
        <el-table-column prop="code" label="代码" min-width="180" />
        <el-table-column prop="message" label="提示" min-width="320" />
      </el-table>
    </section>

    <section v-if="abnormalPreview.length" class="table-surface">
      <div class="section-title">
        <h2>异常数据预览</h2>
        <span>{{ abnormalPreview.length }} 类</span>
      </div>
      <el-collapse>
        <el-collapse-item v-for="group in abnormalPreview" :key="group.type" :name="group.type">
          <template #title>
            <el-tag :type="group.level === 'error' ? 'danger' : 'warning'">{{ group.level }}</el-tag>
            <strong class="collapse-title">{{ group.type }}</strong>
            <span>{{ group.count }} 条</span>
          </template>
          <el-table :data="group.examples" size="small">
            <el-table-column prop="row_index" label="行号" width="90" />
            <el-table-column prop="column_name" label="字段" min-width="140" />
            <el-table-column label="原始值" min-width="160">
              <template #default="{ row }">{{ displayRawValue(row.raw_value) }}</template>
            </el-table-column>
            <el-table-column prop="message" label="问题说明" min-width="320" />
          </el-table>
        </el-collapse-item>
      </el-collapse>
    </section>

    <section v-if="issueCodeCounts.length" class="form-surface">
      <div class="section-title">
        <h2>校验提示分布</h2>
        <span>{{ issueCodeCounts.length }} 类</span>
      </div>
      <div class="warning-list">
        <div v-for="item in issueCodeCounts" :key="`${item.level}:${item.code}`">
          <span>{{ item.code }}</span>
          <strong>{{ item.count }}</strong>
        </div>
      </div>
    </section>

    <section v-if="dataQuality" class="form-surface">
      <div class="section-title">
        <h2>数据质量评分</h2>
        <el-tag :type="qualityTagType">{{ dataQuality.data_quality_score }} 分</el-tag>
      </div>
      <div class="quality-grid">
        <div class="quality-score">
          <strong>{{ dataQuality.data_quality_score }}</strong>
          <span>data_quality_score</span>
        </div>
        <div v-for="item in qualityItems" :key="item.key" class="quality-item">
          <span>{{ item.label }}</span>
          <el-progress :percentage="item.percent" :status="item.percent >= 70 ? 'success' : undefined" />
        </div>
      </div>
    </section>

    <section v-if="fieldDiagnostics" class="form-surface">
      <div class="section-title">
        <h2>统计口径诊断</h2>
        <el-tag type="success">{{ fieldDiagnostics.recommended_calculation_method_name }}</el-tag>
      </div>
      <div class="diagnostic-grid">
        <div><span>单位列表</span><strong>{{ fieldDiagnostics.unit_diagnostics.unit_list.join('、') || '-' }}</strong></div>
        <div><span>是否混合单位</span><strong>{{ fieldDiagnostics.unit_diagnostics.is_mixed ? '是' : '否' }}</strong></div>
        <div><span>权重字段</span><strong>{{ fieldDiagnostics.weight_diagnostics.weight_field_exists ? '已识别' : '未识别' }}</strong></div>
        <div><span>权重合计</span><strong>{{ displayValue(fieldDiagnostics.weight_diagnostics.weight_total) }}</strong></div>
        <div><span>有效权重任务数</span><strong>{{ fieldDiagnostics.weight_diagnostics.valid_weight_task_count }}</strong></div>
        <div><span>缺少权重任务数</span><strong>{{ fieldDiagnostics.weight_diagnostics.missing_weight_task_count }}</strong></div>
        <div><span>工程量字段完整率</span><strong>{{ rateText(fieldDiagnostics.field_completeness_summary.quantity_field_complete_rate) }}</strong></div>
        <div><span>计划日期完整率</span><strong>{{ rateText(fieldDiagnostics.field_completeness_summary.plan_date_complete_rate) }}</strong></div>
        <div><span>实际完成率完整率</span><strong>{{ rateText(fieldDiagnostics.field_completeness_summary.actual_percent_complete_rate) }}</strong></div>
      </div>
      <div class="capability-list">
        <div v-for="method in fieldDiagnostics.available_calculation_methods" :key="method.code">
          <el-tag :type="method.available ? (method.recommended ? 'success' : 'info') : 'warning'">
            {{ method.name }}{{ method.recommended ? ' / 推荐' : '' }}
          </el-tag>
          <span>{{ method.not_recommended_reason || method.warning || method.reason }}</span>
        </div>
      </div>
      <div class="capability-list">
        <div v-for="item in dashboardCapabilityRows" :key="item.key">
          <el-tag :type="item.available ? 'success' : 'warning'">{{ item.label }}：{{ item.available ? '可用' : '不可用' }}</el-tag>
          <span>{{ item.reason }}</span>
        </div>
      </div>
    </section>

    <section v-if="dataQuality" class="form-surface">
      <div class="section-title">
        <h2>确认导入</h2>
        <el-tag v-if="confirmResult" type="success">{{ confirmResult.status }}</el-tag>
      </div>
      <div class="confirm-grid">
        <el-form-item label="数据日期">
          <el-date-picker v-model="dataDate" type="date" value-format="YYYY-MM-DD" />
        </el-form-item>
        <el-form-item label="导入策略">
          <el-select v-model="importStrategy">
            <el-option label="新增批次" value="new_batch" />
            <el-option label="替换同日期批次" value="replace_same_date" />
            <el-option label="覆盖当前批次" value="overwrite_current" />
          </el-select>
        </el-form-item>
        <el-form-item label="保存模板">
          <el-switch v-model="saveAsTemplate" />
        </el-form-item>
        <el-form-item label="模板名称">
          <el-input v-model="templateName" :disabled="!saveAsTemplate" placeholder="机电周进度模板" />
        </el-form-item>
        <el-form-item label="统计口径 ID">
          <el-input-number v-model="calculationProfileId" :min="1" controls-position="right" clearable />
        </el-form-item>
        <el-form-item label="计划基线">
          <el-select v-if="baselineOptions.length" v-model="baselinePlanId" clearable placeholder="项目默认计划基线">
            <el-option
              v-for="baseline in baselineOptions"
              :key="baseline.id"
              :label="baselineLabel(baseline)"
              :value="baseline.id"
            />
          </el-select>
          <span v-else class="muted-text">未配置计划基线</span>
        </el-form-item>
      </div>
      <el-alert
        v-if="!baselineOptions.length"
        title="未配置计划基线，仍可导入，但滞后判断可能不准确。"
        type="warning"
        show-icon
        :closable="false"
      />
      <div class="actions-row table-actions">
        <el-button type="primary" :disabled="errorCount > 0" :loading="confirming" @click="confirmImport">
          正式导入
        </el-button>
        <el-button
          type="success"
          :disabled="!canPublish"
          :loading="publishing"
          @click="publishImport"
        >
          发布到看板
        </el-button>
      </div>
      <div v-if="confirmResult" class="import-summary">
        <div><span>导入条数</span><strong>{{ confirmResult.imported_count }}</strong></div>
        <div><span>跳过条数</span><strong>{{ confirmResult.skipped_count }}</strong></div>
        <div><span>warning 数</span><strong>{{ confirmResult.warning_count }}</strong></div>
        <div><span>error 数</span><strong>{{ confirmResult.error_count }}</strong></div>
        <div><span>数据质量评分</span><strong>{{ confirmResult.data_quality.data_quality_score }}</strong></div>
        <div><span>当前批次数据日期</span><strong class="metric-date">{{ dataDate || '-' }}</strong></div>
      </div>
      <div v-if="publishResult" class="publish-result">
        <span>已发布</span>
        <strong>{{ new Date(publishResult.published_at).toLocaleString() }}</strong>
      </div>
      <div v-if="confirmResult" class="actions-row table-actions">
        <el-button type="primary" @click="goProjectModule('dashboard')">查看进度看板</el-button>
        <el-button @click="goProjectModule('progress-items')">查看进度明细</el-button>
        <el-button @click="goProjectModule('warnings')">查看预警记录</el-button>
        <el-button @click="goProjectModule('reports')">导出当前看板</el-button>
        <el-button @click="goProjectModule('import')">继续导入下一期</el-button>
      </div>
    </section>

    <section v-if="normalizedRows.length" class="table-surface">
      <div class="section-title">
        <h2>标准化预览</h2>
        <span>前 {{ normalizedRows.length }} 行</span>
      </div>
      <el-table :data="normalizedRows" height="320">
        <el-table-column
          v-for="column in normalizedColumns"
          :key="column"
          :prop="column"
          :label="column"
          min-width="140"
        />
      </el-table>
    </section>
  </main>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { confirmImportBatch, downloadImportErrorReport, getFieldDiagnostics, publishImportBatch, validateFieldMappings, validateImportBatch } from '../api/imports'
import { listBaselinePlans } from '../api/baselinePlans'
import type { BaselinePlan } from '../types/baselinePlan'
import type {
  FieldMapping,
  ImportConfirmResponse,
  ImportPublishResponse,
  ImportStrategy,
  ImportParseResponse,
  ImportValidationIssue,
  ValidationIssueCodeCount,
  DataQualityScore,
  MappingValidationIssue,
  MatchedTemplate,
  AbnormalPreviewGroup,
  FieldDiagnostics,
} from '../types/import'

const route = useRoute()
const router = useRouter()
const batchId = Number(route.params.batchId)
const parseResult = ref<ImportParseResponse | null>(null)
const fieldMappings = ref<FieldMapping[]>([])
const issues = ref<MappingValidationIssue[]>([])
const importIssues = ref<ImportValidationIssue[]>([])
const abnormalPreview = ref<AbnormalPreviewGroup[]>([])
const issueCodeCounts = ref<ValidationIssueCodeCount[]>([])
const dataQuality = ref<DataQualityScore | null>(null)
const confirmResult = ref<ImportConfirmResponse | null>(null)
const publishResult = ref<ImportPublishResponse | null>(null)
const normalizedRows = ref<Record<string, unknown>[]>([])
const validationValid = ref(false)
const validating = ref(false)
const importValidating = ref(false)
const confirming = ref(false)
const publishing = ref(false)
const errorMessage = ref('')
const importStrategy = ref<ImportStrategy>('new_batch')
const saveAsTemplate = ref(false)
const templateName = ref('')
const calculationProfileId = ref<number | null>(null)
const baselinePlanId = ref<number | null>(null)
const dataDate = ref(new Date().toISOString().slice(0, 10))
const selectedMappingTemplateId = ref<number | null>(null)
const baselineOptions = ref<BaselinePlan[]>([])
const issueFilter = ref<'all' | 'error' | 'warning'>('all')
const fieldDiagnostics = ref<FieldDiagnostics | null>(null)
const downloadingErrorReport = ref(false)

const systemFields = [
  ['wbs_code', 'WBS 编码'],
  ['identity_key', '任务唯一键'],
  ['task_code', '任务编码'],
  ['task_name', '任务名称'],
  ['parent_task_id', '父任务 ID'],
  ['parent_task_name', '父级任务名称'],
  ['task_level', '任务层级'],
  ['area', '区域'],
  ['building', '楼栋'],
  ['construction_unit', '施工单位'],
  ['floor', '楼层'],
  ['discipline', '专业'],
  ['system_name', '系统名称'],
  ['unit', '单位'],
  ['total_quantity', '总工程量'],
  ['planned_quantity', '计划完成量'],
  ['period_quantity', '本期完成量'],
  ['cumulative_quantity', '累计完成量'],
  ['actual_quantity', '实际完成量'],
  ['remaining_quantity', '剩余工程量'],
  ['planned_percent', '计划完成率'],
  ['actual_percent', '实际完成率'],
  ['reported_percent', 'Excel 上报完成率'],
  ['planned_start_date', '计划开始日期'],
  ['planned_finish_date', '计划完成日期'],
  ['actual_start_date', '实际开始日期'],
  ['actual_finish_date', '实际完成日期'],
  ['weight', '权重'],
  ['value_amount', '产值 / 金额'],
  ['status', '状态'],
  ['remark', '备注'],
].map(([value, label]) => ({ value, label }))

const warningCount = computed(() => importIssues.value.filter((issue) => issue.level === 'warning').length)
const errorCount = computed(() => importIssues.value.filter((issue) => issue.level === 'error').length)
const canPublish = computed(() => confirmResult.value?.status === 'imported' && !publishResult.value)
const qualityTagType = computed(() => {
  if (!dataQuality.value) return 'info'
  if (dataQuality.value.data_quality_score >= 85) return 'success'
  if (dataQuality.value.data_quality_score >= 70) return 'warning'
  return 'danger'
})
const qualityItems = computed(() => {
  if (!dataQuality.value) return []
  return [
    ['field_completeness', '字段完整度'],
    ['task_match_rate', '任务匹配率'],
    ['valid_row_rate', '有效数据率'],
    ['plan_field_completeness', '计划字段完整度'],
    ['unit_consistency', '单位一致性'],
  ].map(([key, label]) => ({
    key,
    label,
    percent: Math.round((dataQuality.value?.[key as keyof DataQualityScore] ?? 0) * 100),
  }))
})
const hasHighScoreTemplate = computed(() => (parseResult.value?.matched_templates ?? []).some((template) => template.match_score >= 0.8))
const exactMatchTemplate = computed(() => (parseResult.value?.matched_templates ?? []).find((template) => template.is_exact_match) ?? null)
const recommendedTemplate = computed(() => exactMatchTemplate.value ?? parseResult.value?.matched_templates?.[0] ?? null)
const unmappedFields = computed(() =>
  fieldMappings.value
    .filter((mapping) => !mapping.system_field_name && !mapping.save_to_extra)
    .map((mapping) => mapping.excel_column_name),
)
const missingRequiredFields = computed(() => {
  const mapped = new Set(fieldMappings.value.map((mapping) => mapping.system_field_name).filter(Boolean))
  const missing: string[] = []
  if (!mapped.has('task_name')) missing.push('任务名称')
  if (!mapped.has('actual_percent') && !mapped.has('actual_quantity') && !mapped.has('cumulative_quantity')) {
    missing.push('实际进度字段')
  }
  return missing
})
const filteredImportIssues = computed(() => {
  if (issueFilter.value === 'all') return importIssues.value
  return importIssues.value.filter((issue) => issue.level === issueFilter.value)
})
const groupedImportIssues = computed(() => {
  const groups = new Map<string, { level: string; code: string; count: number; explanation: string }>()
  filteredImportIssues.value.forEach((issue) => {
    const code = issue.code || '未分类'
    const key = `${issue.level}:${code}`
    const current = groups.get(key)
    if (current) {
      current.count += 1
    } else {
      groups.set(key, {
        level: issue.level,
        code,
        count: 1,
        explanation: issueExplanation(code, issue.message),
      })
    }
  })
  return Array.from(groups.values())
})
const normalizedColumns = computed(() => {
  const keys = new Set<string>()
  normalizedRows.value.forEach((row) => Object.keys(row).forEach((key) => keys.add(key)))
  return Array.from(keys)
})
const nonProgressSheetNotice = computed(() => {
  const result = parseResult.value
  if (!result) return ''
  return isLikelyNonProgressSheet(result.batch.sheet_name || '', result.columns.map((column) => column.name))
    ? '当前 Sheet 看起来像说明表、问题记录表或字段检查表，不是工程进度数据表。一般不建议导入，请确认是否选择了正确的进度 Sheet。'
    : ''
})
const roleOrder = ['核心进度字段', '分组字段', '统计增强字段', '辅助字段', '未分组字段']
const roleGroupedMappings = computed(() =>
  [...fieldMappings.value].sort((a, b) => roleOrder.indexOf(String((a as any).field_role || '未分组字段')) - roleOrder.indexOf(String((b as any).field_role || '未分组字段')) || a.sort_order - b.sort_order),
)
const fieldImpacts = computed(() => fieldDiagnostics.value?.field_impacts ?? [])
const dashboardCapabilityRows = computed(() => {
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
  return Object.entries(fieldDiagnostics.value?.dashboard_capabilities ?? {}).map(([key, value]) => ({ key, label: labels[key] || key, ...value }))
})

function buildDefaultMappings(result: ImportParseResponse): FieldMapping[] {
  return result.columns.map((column, index) => ({
    excel_column_name: column.name,
    recommended_field: column.recommended_field,
    system_field_name: column.recommended_field,
    field_type: column.field_type,
    is_dimension: column.is_dimension,
    is_metric: column.is_metric,
    is_required: column.is_required ?? false,
    save_to_extra: column.save_to_extra,
    sort_order: index,
    match_type: column.match_type,
    confidence: column.confidence,
    reason: column.reason,
    field_role: column.field_role,
    affects_statistics: column.affects_statistics,
    affects_delay: column.affects_delay,
    needs_review: column.needs_review ?? false,
    sample_values: column.sample_values ?? [],
    ...(column as any),
  }))
}

function applyTemplate(template: MatchedTemplate) {
  const templateByColumn = new Map(template.fields.map((field) => [field.excel_column_name, field]))
  fieldMappings.value = fieldMappings.value.map((mapping) => ({
    ...mapping,
    ...(templateByColumn.get(mapping.excel_column_name) ?? {}),
    match_type: templateByColumn.has(mapping.excel_column_name) ? '历史模板匹配' : (mapping as any).match_type,
    confidence: templateByColumn.has(mapping.excel_column_name) ? '高' : (mapping as any).confidence,
    reason: templateByColumn.has(mapping.excel_column_name) ? `根据模板“${template.name}”套用该字段映射。` : (mapping as any).reason,
  }))
  selectedMappingTemplateId.value = template.id
}

function previewTemplate(template: MatchedTemplate) {
  issues.value = template.fields.map((field) => ({
    level: 'info',
    code: 'template_mapping',
    message: `${field.excel_column_name} -> ${field.system_field_name || '未映射'}`,
    excel_column_name: field.excel_column_name,
    system_field_name: field.system_field_name,
  }))
  validationValid.value = true
}

async function validateMappings() {
  validating.value = true
  errorMessage.value = ''
  try {
    const response = await validateFieldMappings(batchId, fieldMappings.value)
    issues.value = response.issues.length
      ? response.issues
      : [{ level: 'info', code: 'mapping_valid', message: '字段映射未发现冲突。' }]
    validationValid.value = response.valid
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '字段映射校验失败'
  } finally {
    validating.value = false
  }
}

async function validateImport() {
  importValidating.value = true
  errorMessage.value = ''
  try {
    const response = await validateImportBatch(batchId, fieldMappings.value)
    importIssues.value = response.issues.length
      ? response.issues
      : [{ level: 'info', code: 'import_valid', message: '导入数据未发现 warning 或 error。' }]
    dataQuality.value = response.data_quality
    confirmResult.value = null
    publishResult.value = null
    normalizedRows.value = response.normalized_preview_rows
    issueCodeCounts.value = response.issue_code_counts
    abnormalPreview.value = response.abnormal_preview
    fieldDiagnostics.value = await getFieldDiagnostics(batchId)
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '导入校验失败'
  } finally {
    importValidating.value = false
  }
}

async function downloadErrorReport() {
  downloadingErrorReport.value = true
  errorMessage.value = ''
  try {
    const { blob, filename } = await downloadImportErrorReport(batchId)
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = filename
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    URL.revokeObjectURL(url)
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '错误清单下载失败'
  } finally {
    downloadingErrorReport.value = false
  }
}

async function confirmImport() {
  confirming.value = true
  errorMessage.value = ''
  try {
    const response = await confirmImportBatch(batchId, {
      template_name: templateName.value || null,
      save_as_template: saveAsTemplate.value,
      data_date: dataDate.value,
      calculation_profile_id: calculationProfileId.value,
      baseline_plan_id: baselinePlanId.value,
      mapping_template_id: selectedMappingTemplateId.value,
      import_strategy: importStrategy.value,
      field_mappings: fieldMappings.value,
    })
    confirmResult.value = response
    publishResult.value = null
    dataQuality.value = response.data_quality
    issueCodeCounts.value = response.issue_code_counts
    fieldDiagnostics.value = await getFieldDiagnostics(batchId)
    if (!response.valid) {
      importIssues.value = response.issues
      abnormalPreview.value = []
      errorMessage.value = '正式导入失败，请先处理校验错误。'
    }
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '正式导入失败'
  } finally {
    confirming.value = false
  }
}

async function publishImport() {
  publishing.value = true
  errorMessage.value = ''
  try {
    const response = await publishImportBatch(batchId)
    publishResult.value = response
    if (confirmResult.value) {
      confirmResult.value = { ...confirmResult.value, status: response.status }
    }
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '发布失败'
  } finally {
    publishing.value = false
  }
}

function goProjectModule(module: string) {
  const projectId = parseResult.value?.batch.project_id
  if (!projectId) return
  router.push({
    path: `/projects/${projectId}/${module}`,
    query: confirmResult.value ? { batch_id: String(batchId) } : {},
  })
}

function issueExplanation(code: string, message = '') {
  const text = `${code} ${message}`.toLowerCase()
  if (text.includes('date') || text.includes('日期')) return '日期格式不正确或无法识别，请检查原表日期列。'
  if (text.includes('negative') || text.includes('负数')) return '工程量或数量不应为负数，请确认是否为录入错误。'
  if (text.includes('percent') || text.includes('range') || text.includes('完成率')) return '完成率应在 0% 到 100% 范围内，请检查百分比格式。'
  if (code === 'import_valid') return '当前导入数据未发现阻塞问题。'
  return message || '请检查原始数据和字段映射。'
}

function displayRawValue(value: unknown) {
  if (value === null || value === undefined || value === '') return '-'
  if (typeof value === 'object') return JSON.stringify(value)
  return String(value)
}
function displayValue(value: unknown) {
  if (value === null || value === undefined || value === '') return '-'
  return String(value)
}
function rateText(value: number) {
  return `${Math.round((value || 0) * 100)}%`
}

onMounted(() => {
  const raw = sessionStorage.getItem(`import:${batchId}:parse`)
  if (!raw) {
    errorMessage.value = '未找到解析结果，请先完成上传解析。'
    return
  }
  parseResult.value = JSON.parse(raw) as ImportParseResponse
  fieldDiagnostics.value = parseResult.value.field_diagnostics ?? null
  dataDate.value = parseResult.value.batch.data_date || dataDate.value
  baselinePlanId.value = parseResult.value.batch.baseline_plan_id ?? null
  fieldMappings.value = buildDefaultMappings(parseResult.value)
  void loadBaselineOptions(parseResult.value.batch.project_id)
})

async function loadBaselineOptions(projectId: number) {
  baselineOptions.value = (await listBaselinePlans(projectId)).filter((baseline) => baseline.is_active)
  if (!baselinePlanId.value) {
    baselinePlanId.value = baselineOptions.value.find((baseline) => baseline.is_default)?.id ?? null
  }
}

function baselineLabel(baseline: BaselinePlan) {
  const dateText = baseline.baseline_date ? ` / ${baseline.baseline_date}` : ''
  const defaultText = baseline.is_default ? ' / 默认' : ''
  return `${baseline.name}${dateText}${defaultText}`
}

function isLikelyNonProgressSheet(sheetName: string, columnNames: string[]) {
  const normalizedSheetName = normalizeSheetText(sheetName)
  const sheetKeywords = ['使用说明', '字段映射检查', '问题记录', '看板核对', '预期结果']
  if (sheetKeywords.some((keyword) => normalizedSheetName.includes(normalizeSheetText(keyword)))) {
    return true
  }

  const normalizedColumns = new Set(columnNames.map(normalizeSheetText))
  return hasAtLeastMatches(
    normalizedColumns,
    ['Excel原字段', '期望系统字段', '是否正确', '是否必填', '是否保存extra_fields', '问题说明', '建议补充识别规则'],
    2,
  ) || hasAtLeastMatches(normalizedColumns, ['问题编号', '问题类型', '问题描述', '处理状态'], 2)
}

function hasAtLeastMatches(normalizedColumns: Set<string>, markers: string[], minCount: number) {
  return markers.filter((marker) => normalizedColumns.has(normalizeSheetText(marker))).length >= minCount
}

function normalizeSheetText(value: string) {
  return value.replace(/\s+/g, '').trim()
}
</script>
