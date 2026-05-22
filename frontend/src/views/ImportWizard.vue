<template>
  <main class="page-shell">
    <section class="page-heading">
      <div>
        <p class="eyebrow">excel import</p>
        <h1>Excel 导入解析</h1>
      </div>
      <el-button @click="router.push(`/projects/${projectId}`)">返回项目</el-button>
    </section>

    <section class="import-guide">
      <div v-for="step in importSteps" :key="step.title" :class="{ active: step.step === activeStep }">
        <span>{{ step.index }}</span>
        <strong>{{ step.title }}</strong>
      </div>
    </section>

    <el-alert v-if="errorMessage" :title="errorMessage" type="error" show-icon :closable="false" />
    <el-alert
      v-if="nonProgressSheetNotice"
      :title="nonProgressSheetNotice"
      type="warning"
      show-icon
      :closable="false"
    />

    <section class="form-surface">
      <div class="import-tips">
        <strong>导入前确认</strong>
        <span>支持单 Sheet 和多 Sheet。</span>
        <span>系统会自动识别字段。</span>
        <span>导入前可查看字段映射和数据校验。</span>
        <span>有 error 的 Sheet 不允许发布。</span>
        <span>支持权重、工程量、百分比等不同统计口径。</span>
      </div>
      <el-form-item label="导入模式">
        <el-segmented
          v-model="importMode"
          :options="[
            { label: '单 Sheet 导入', value: 'single' },
            { label: '多 Sheet 批量导入', value: 'multi' },
          ]"
        />
      </el-form-item>
      <el-alert
        v-if="!baselineOptions.length"
        title="当前项目未配置计划基线，仍可导入；后续滞后判断将主要依赖导入表中的计划字段。"
        type="warning"
        show-icon
        :closable="false"
      />
      <el-alert
        v-if="batch && !bulkTemplateOptions.length"
        title="暂无可用模板或尚未解析 Sheet。可以继续使用系统推荐字段，解析后会显示模板匹配度。"
        type="info"
        show-icon
        :closable="false"
      />
      <el-steps :active="activeStep - 1" finish-status="success" simple>
        <el-step title="上传文件" />
        <el-step title="选择 Sheet" />
        <el-step title="字段映射" />
        <el-step title="导入校验" />
        <el-step title="确认导入" />
        <el-step title="发布批次" />
      </el-steps>

      <div class="import-panel">
        <el-form-item label="数据日期">
          <el-date-picker v-model="parseForm.data_date" type="date" value-format="YYYY-MM-DD" />
        </el-form-item>
        <el-upload
          drag
          :auto-upload="false"
          :limit="1"
          :on-change="handleFileChange"
          :on-remove="handleFileRemove"
          accept=".xlsx,.csv"
        >
          <div class="upload-copy">
            <strong>选择 .xlsx 或 .csv 文件</strong>
            <span>上传后会创建 draft 导入批次，并读取 Sheet 列表。</span>
          </div>
        </el-upload>

        <el-button type="primary" :loading="uploading" :disabled="!selectedFile" @click="uploadFile">
          上传并读取 Sheet
        </el-button>
      </div>
    </section>

    <section v-if="batch && sheetHints.length" class="table-surface">
      <div class="section-title">
        <h2>Sheet 选择建议</h2>
        <span>{{ sheetHints.length }} 个 Sheet</span>
      </div>
      <el-table :data="sheetHints" height="300" empty-text="暂无 Sheet">
        <el-table-column prop="name" label="Sheet 名称" min-width="160" show-overflow-tooltip />
        <el-table-column prop="rowCount" label="行数预估" width="100" />
        <el-table-column prop="columnCount" label="列数预估" width="100" />
        <el-table-column label="是否疑似进度表" width="150">
          <template #default="{ row }">
            <el-tag :type="row.isLikelyProgress ? 'success' : 'warning'">{{ row.isLikelyProgress ? '是' : '请确认' }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="说明 / 问题表" width="150">
          <template #default="{ row }">{{ row.isLikelyNonProgress ? '疑似' : '未发现' }}</template>
        </el-table-column>
        <el-table-column prop="recommendation" label="推荐操作" min-width="220" />
        <el-table-column label="操作" width="120">
          <template #default="{ row }">
            <el-button size="small" @click="selectSheetHint(row.name)">选择</el-button>
          </template>
        </el-table-column>
      </el-table>
    </section>

    <section v-if="batch && importMode === 'single'" class="form-surface">
      <div class="section-title">
        <h2>解析设置</h2>
        <el-tag>{{ batch.status }}</el-tag>
      </div>

      <el-form label-position="top" :model="parseForm">
        <div class="form-grid">
          <el-form-item label="Sheet 名称">
            <el-select v-model="parseForm.sheet_name" @change="handleSheetChange">
              <el-option v-for="sheet in sheets" :key="sheet" :label="sheet" :value="sheet" />
            </el-select>
          </el-form-item>
          <el-form-item label="表头行">
            <el-input-number
              v-model="parseForm.header_row_index"
              :min="1"
              placeholder="自动识别"
              @change="handleRowSettingChange"
            />
          </el-form-item>
          <el-form-item label="数据起始行">
            <el-input-number
              v-model="parseForm.data_start_row_index"
              :min="1"
              placeholder="自动识别"
              @change="handleRowSettingChange"
            />
          </el-form-item>
          <el-form-item label="多行表头结束行">
            <el-input-number
              v-model="headerEndRow"
              :min="parseForm.header_row_index"
              :disabled="!parseForm.multi_header"
            />
          </el-form-item>
        </div>
        <div class="switch-row">
          <el-checkbox v-model="parseForm.multi_header">启用多行表头</el-checkbox>
        </div>
        <div class="actions-row">
          <el-button type="primary" :loading="parsing" @click="parseFile">解析并预览</el-button>
        </div>
      </el-form>
      <el-alert
        class="parse-hint"
        title="如果字段显示为“未命名字段”，请检查表头行设置。"
        type="info"
        show-icon
        :closable="false"
      />
      <el-alert
        v-if="headerRecommendation"
        class="parse-hint"
        :title="`推荐表头行：第 ${headerRecommendation.header_row_index || '-'} 行；推荐数据起始行：第 ${headerRecommendation.data_start_row_index || '-'} 行；置信度：${headerRecommendation.confidence}`"
        :type="headerRecommendation.confidence === '高' ? 'success' : headerRecommendation.confidence === '中' ? 'warning' : 'info'"
        show-icon
        :closable="false"
      />
    </section>

    <section v-if="batch && importMode === 'multi'" class="form-surface">
      <div class="section-title">
        <h2>多 Sheet 批量导入</h2>
        <span>{{ selectedSheetNames.length }} / {{ sheets.length }} 个 Sheet</span>
      </div>
      <el-form label-position="top">
        <div class="form-grid">
          <el-form-item label="选择 Sheet">
            <el-select v-model="selectedSheetNames" multiple filterable collapse-tags collapse-tags-tooltip>
              <el-option v-for="sheet in sheets" :key="sheet" :label="sheet" :value="sheet" />
            </el-select>
          </el-form-item>
          <el-form-item label="表头行">
            <el-input-number v-model="parseForm.header_row_index" :min="1" placeholder="自动识别" />
          </el-form-item>
          <el-form-item label="数据起始行">
            <el-input-number v-model="parseForm.data_start_row_index" :min="1" placeholder="自动识别" />
          </el-form-item>
          <el-form-item label="计划基线">
            <el-select v-if="baselineOptions.length" v-model="baselinePlanId" clearable placeholder="项目默认计划基线">
              <el-option v-for="baseline in baselineOptions" :key="baseline.id" :label="baselineLabel(baseline)" :value="baseline.id" />
            </el-select>
            <span v-else class="muted-text">未配置计划基线</span>
          </el-form-item>
          <el-form-item label="导入策略">
            <el-select v-model="multiImportStrategy">
              <el-option label="新增批次" value="new_batch" />
              <el-option label="替换同日期同 Sheet 批次" value="replace_same_date" />
            </el-select>
          </el-form-item>
          <el-form-item label="批量模板">
            <el-select v-model="bulkTemplateId" clearable placeholder="选择模板">
              <el-option
                v-for="template in bulkTemplateOptions"
                :key="template.id"
                :label="`${template.name}｜匹配度 ${templateMatchText(template.match_score)}`"
                :value="template.id"
              />
            </el-select>
          </el-form-item>
        </div>
      </el-form>
      <div class="actions-row">
        <el-button type="primary" :loading="multiParsing" :disabled="!selectedSheetNames.length" @click="parseMultiSheets">批量解析</el-button>
        <el-button :loading="multiValidating" :disabled="!multiParsedRows.length" @click="validateMultiSheets">批量校验</el-button>
        <el-button type="primary" :loading="multiConfirming" :disabled="!multiImportableRows.length" @click="confirmMultiSheets">批量确认导入</el-button>
        <el-button type="success" :loading="multiPublishing" :disabled="!multiPublishableBatchIds.length" @click="publishMultiSheets">批量发布</el-button>
        <el-button :disabled="!bulkTemplateId" @click="applyBulkTemplate">对全部 Sheet 套用模板</el-button>
      </div>
    </section>

    <section v-if="importMode === 'multi' && multiSheetRows.length" class="table-surface">
      <div class="section-title">
        <h2>Sheet 状态</h2>
        <span>{{ multiSheetRows.length }} 个 Sheet</span>
      </div>
      <el-table :data="multiSheetRows" highlight-current-row @current-change="setActiveMultiSheet">
        <el-table-column prop="sheet_name" label="Sheet" min-width="160" />
        <el-table-column prop="batch_id" label="批次 ID" width="100">
          <template #default="{ row }">{{ row.batch_id || '-' }}</template>
        </el-table-column>
        <el-table-column prop="row_count" label="行数预估" width="100" />
        <el-table-column label="推荐表头" width="140">
          <template #default="{ row }">{{ row.header_recommendation?.header_row_index ? `第 ${row.header_recommendation.header_row_index} 行` : '-' }}</template>
        </el-table-column>
        <el-table-column label="推荐数据行" width="150">
          <template #default="{ row }">{{ row.header_recommendation?.data_start_row_index ? `第 ${row.header_recommendation.data_start_row_index} 行` : '-' }}</template>
        </el-table-column>
        <el-table-column prop="status" label="状态" width="130">
          <template #default="{ row }"><el-tag :type="statusTag(row.status)">{{ statusText(row.status) }}</el-tag></template>
        </el-table-column>
        <el-table-column prop="publish_status" label="发布状态" width="130">
          <template #default="{ row }"><el-tag :type="publishTag(row.publish_status)">{{ publishStatusText(row.publish_status) }}</el-tag></template>
        </el-table-column>
        <el-table-column prop="warning_count" label="warning" width="100" />
        <el-table-column prop="error_count" label="error" width="90" />
        <el-table-column prop="imported_count" label="导入条数" width="110" />
        <el-table-column prop="skipped_count" label="跳过条数" width="110" />
        <el-table-column prop="error" label="失败原因" min-width="220" show-overflow-tooltip>
          <template #default="{ row }">{{ friendlyImportError(row.error) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="340">
          <template #default="{ row }">
            <el-button size="small" @click="activeMultiSheetName = row.sheet_name">查看映射</el-button>
            <el-button v-if="row.batch_id && row.status === 'imported'" size="small" :loading="row.publishing" @click="publishOneSheet(row)">发布</el-button>
            <el-button size="small" @click="reprocessSheet(row)">重新处理</el-button>
            <el-button v-if="row.batch_id" size="small" @click="router.push(`/projects/${projectId}/dashboard?batch_id=${row.batch_id}`)">Dashboard</el-button>
          </template>
        </el-table-column>
      </el-table>
    </section>

    <section v-if="importMode === 'multi' && activeMultiSheet" class="table-surface">
      <div class="section-title">
        <h2>{{ activeMultiSheet.sheet_name }} 字段映射</h2>
        <span>{{ activeMultiSheet.columns.length }} 个字段</span>
      </div>
      <div class="template-recommendation">
        <span>推荐模板：{{ topTemplateText(activeMultiSheet) }}</span>
        <el-tag v-if="isLowTemplateMatch(activeMultiSheet)" type="warning">匹配度较低，请手动调整映射</el-tag>
        <el-tag v-else-if="activeMultiSheet.suggested_mappings.length" type="success">可一键套用推荐模板</el-tag>
      </div>
      <el-alert
        v-if="unmappedFields(activeMultiSheet).length"
        class="parse-hint"
        :title="`未识别字段 ${unmappedFields(activeMultiSheet).length} 个：${unmappedFields(activeMultiSheet).slice(0, 8).join('、')}`"
        type="warning"
        show-icon
        :closable="false"
      />
      <el-alert
        v-if="missingRequiredFields(activeMultiSheet).length"
        class="parse-hint"
        :title="`必填字段缺失：${missingRequiredFields(activeMultiSheet).join('、')}。请检查字段映射后重新校验。`"
        type="error"
        show-icon
        :closable="false"
      />
      <el-alert
        class="parse-hint"
        title="施工单位、责任人等非核心统计字段可保存到 extra_fields，后续可用于追溯原始信息，不参与进度计算。"
        type="info"
        show-icon
        :closable="false"
      />
      <div v-if="activeMultiSheet.suggested_mappings.length" class="actions-row table-actions">
        <el-button @click="applyMultiTemplate(activeMultiSheet, activeMultiSheet.suggested_mappings[0])">
          套用推荐模板：{{ activeMultiSheet.suggested_mappings[0].name }}（{{ templateMatchText(activeMultiSheet.suggested_mappings[0].match_score) }}）
        </el-button>
      </div>
      <el-table :data="activeMultiSheet.mappings" height="360">
        <el-table-column prop="excel_column_name" label="Excel 字段" min-width="160" />
        <el-table-column prop="recommended_field" label="推荐字段" min-width="150">
          <template #default="{ row }">{{ row.recommended_field || '未识别' }}</template>
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
        <el-table-column label="扩展字段" width="110">
          <template #default="{ row }"><el-checkbox v-model="row.save_to_extra" /></template>
        </el-table-column>
      </el-table>
    </section>

    <section v-if="importMode === 'multi' && activeMultiSheet?.preview_rows.length" class="table-surface">
      <div class="section-title">
        <h2>{{ activeMultiSheet.sheet_name }} 数据预览</h2>
        <span>前 {{ activeMultiSheet.preview_rows.length }} 行</span>
      </div>
      <el-table :data="activeMultiSheet.preview_rows" height="320">
        <el-table-column v-for="column in activeMultiSheet.columns" :key="column.name" :prop="column.name" :label="column.name" min-width="140" />
      </el-table>
    </section>

    <section v-if="importMode === 'multi' && activeMultiSheet?.issues.length" class="table-surface">
      <div class="section-title">
        <h2>{{ activeMultiSheet.sheet_name }} 校验问题</h2>
        <span>{{ activeMultiSheet.issues.length }} 条</span>
      </div>
      <div class="issue-toolbar">
        <el-radio-group v-model="multiIssueFilter" size="small">
          <el-radio-button label="all">全部</el-radio-button>
          <el-radio-button label="error">只看 error</el-radio-button>
          <el-radio-button label="warning">只看 warning</el-radio-button>
        </el-radio-group>
      </div>
      <div class="issue-groups">
        <div v-for="group in groupedIssues(activeMultiSheet.issues)" :key="`${group.level}:${group.code}`">
          <el-tag :type="group.level === 'error' ? 'danger' : 'warning'">{{ group.level }}</el-tag>
          <strong>{{ group.code }}</strong>
          <span>{{ group.count }} 条</span>
          <p>{{ group.explanation }}</p>
        </div>
      </div>
      <el-table :data="filteredIssues(activeMultiSheet.issues)" height="320">
        <el-table-column prop="level" label="级别" width="100" />
        <el-table-column prop="row_index" label="行号" width="90" />
        <el-table-column prop="column_name" label="字段" min-width="140" />
        <el-table-column prop="code" label="代码" min-width="180" />
        <el-table-column prop="message" label="提示" min-width="320" />
      </el-table>
    </section>

    <section v-if="importMode === 'multi' && multiConfirmResult" class="table-surface">
      <div class="section-title">
        <h2>导入结果汇总</h2>
        <span>成功 {{ multiSummary.successSheets }} / 失败 {{ multiSummary.failedSheets }}</span>
      </div>
      <div class="import-summary">
        <div><span>总 Sheet 数</span><strong>{{ multiSummary.totalSheets }}</strong></div>
        <div><span>成功 Sheet 数</span><strong>{{ multiSummary.successSheets }}</strong></div>
        <div><span>失败 Sheet 数</span><strong>{{ multiSummary.failedSheets }}</strong></div>
        <div><span>已发布数</span><strong>{{ multiSummary.publishedSheets }}</strong></div>
        <div><span>发布失败数</span><strong>{{ multiSummary.failedPublishSheets }}</strong></div>
        <div><span>总导入行数</span><strong>{{ multiSummary.importedRows }}</strong></div>
        <div><span>总跳过行数</span><strong>{{ multiSummary.skippedRows }}</strong></div>
        <div><span>warning 总数</span><strong>{{ multiSummary.warningCount }}</strong></div>
        <div><span>error 总数</span><strong>{{ multiSummary.errorCount }}</strong></div>
      </div>
      <el-table :data="multiSheetRows">
        <el-table-column prop="sheet_name" label="Sheet" min-width="160" />
        <el-table-column prop="batch_id" label="批次 ID" width="100" />
        <el-table-column prop="imported_count" label="导入条数" width="110" />
        <el-table-column prop="skipped_count" label="跳过条数" width="110" />
        <el-table-column prop="warning_count" label="warning" width="100" />
        <el-table-column prop="error_count" label="error" width="90" />
        <el-table-column prop="status" label="导入状态" width="130">
          <template #default="{ row }"><el-tag :type="statusTag(row.status)">{{ statusText(row.status) }}</el-tag></template>
        </el-table-column>
        <el-table-column prop="publish_status" label="发布状态" width="130">
          <template #default="{ row }"><el-tag :type="publishTag(row.publish_status)">{{ publishStatusText(row.publish_status) }}</el-tag></template>
        </el-table-column>
        <el-table-column prop="error" label="失败原因" min-width="220" show-overflow-tooltip>
          <template #default="{ row }">{{ friendlyImportError(row.error) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="500">
          <template #default="{ row }">
            <el-button v-if="row.batch_id" size="small" @click="router.push(`/projects/${projectId}/imports`)">查看批次</el-button>
            <el-button v-if="row.batch_id && row.status === 'imported'" size="small" :loading="row.publishing" @click="publishOneSheet(row)">发布</el-button>
            <el-button size="small" @click="reprocessSheet(row)">重新处理</el-button>
            <el-button v-if="row.issues.length" size="small" @click="activeMultiSheetName = row.sheet_name">查看校验问题</el-button>
            <el-button
              v-if="row.batch_id && (row.error_count > 0 || row.warning_count > 0)"
              size="small"
              :loading="row.downloadingErrorReport"
              @click="downloadSheetErrorReport(row)"
            >下载错误清单</el-button>
            <el-button v-if="row.batch_id" size="small" @click="router.push(`/projects/${projectId}/dashboard?batch_id=${row.batch_id}`)">查看 Dashboard</el-button>
          </template>
        </el-table-column>
      </el-table>
      <div class="actions-row table-actions">
        <el-select v-model="quickBatchId" placeholder="选择批次跳转" style="width: 220px;">
          <el-option v-for="row in multiJumpRows" :key="row.batch_id" :label="`${row.sheet_name} / batch ${row.batch_id}`" :value="row.batch_id" />
        </el-select>
        <span class="next-step-label">下一步推荐操作</span>
        <el-button type="primary" @click="goBatchDashboard">查看进度看板</el-button>
        <el-button @click="activeMultiSheetName = multiJumpRows.find((row) => row.batch_id === quickBatchId)?.sheet_name ?? activeMultiSheetName">查看字段诊断</el-button>
        <el-button @click="router.push({ path: `/projects/${projectId}/reports`, query: selectedQuickBatchId() ? { batch_id: String(selectedQuickBatchId()) } : {} })">导出当前看板</el-button>
        <el-button @click="goBatchItems">查看进度明细</el-button>
        <el-button @click="goBatchWarnings">查看预警记录</el-button>
        <el-button @click="resetMultiImport">继续导入下一期</el-button>
        <el-button @click="exportMultiIssues">导出校验问题</el-button>
      </div>
    </section>

    <section v-if="importMode === 'single' && columns.length" class="table-surface">
      <div class="section-title">
        <h2>字段识别</h2>
        <span>{{ columns.length }} 个字段</span>
      </div>
      <el-table :data="columns">
        <el-table-column prop="name" label="Excel 字段" min-width="180" />
        <el-table-column prop="field_type" label="字段类型" width="120" />
        <el-table-column prop="recommended_field" label="推荐系统字段" min-width="180">
          <template #default="{ row }">{{ row.recommended_field || '未识别' }}</template>
        </el-table-column>
      </el-table>
      <div class="actions-row table-actions">
        <el-button type="primary" @click="goMapping">确认字段映射</el-button>
      </div>
    </section>

    <section v-if="importMode === 'single' && previewRows.length" class="table-surface">
      <div class="section-title">
        <h2>数据预览</h2>
        <span>前 {{ previewRows.length }} 行 / 共 {{ batch?.row_count ?? 0 }} 行</span>
      </div>
      <el-table :data="previewRows" height="420">
        <el-table-column
          v-for="column in columns"
          :key="column.name"
          :prop="column.name"
          :label="column.name"
          min-width="140"
        />
      </el-table>
    </section>
  </main>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import type { UploadFile } from 'element-plus'

import {
  confirmMultipleSheets,
  downloadImportErrorReport,
  parseImportBatch,
  parseMultipleSheets,
  publishMultipleSheets,
  uploadImportFile,
  validateMultipleSheets,
} from '../api/imports'
import { listBaselinePlans } from '../api/baselinePlans'
import type { BaselinePlan } from '../types/baselinePlan'
import type {
  FieldMapping,
  ImportBatch,
  ImportStrategy,
  MatchedTemplate,
  MultiSheetConfirmResponse,
  ParsedColumn,
  ImportValidationIssue,
  HeaderRecommendation,
} from '../types/import'

const route = useRoute()
const router = useRouter()
const projectId = Number(route.params.id)
const selectedFile = ref<File | null>(null)
const batch = ref<ImportBatch | null>(null)
const sheets = ref<string[]>([])
const columns = ref<ParsedColumn[]>([])
const previewRows = ref<Record<string, unknown>[]>([])
const headerRecommendation = ref<HeaderRecommendation | null>(null)
const importMode = ref<'single' | 'multi'>('single')
const selectedSheetNames = ref<string[]>([])
const multiSheetRows = ref<MultiSheetRow[]>([])
const activeMultiSheetName = ref('')
const baselineOptions = ref<BaselinePlan[]>([])
const baselinePlanId = ref<number | null>(null)
const multiImportStrategy = ref<ImportStrategy>('new_batch')
const bulkTemplateId = ref<number | null>(null)
const multiParseResult = ref(null)
const multiConfirmResult = ref<MultiSheetConfirmResponse | null>(null)
const uploading = ref(false)
const parsing = ref(false)
const multiParsing = ref(false)
const multiValidating = ref(false)
const multiConfirming = ref(false)
const multiPublishing = ref(false)
const errorMessage = ref('')
const multiIssueFilter = ref<'all' | 'error' | 'warning'>('all')
const quickBatchId = ref<number | null>(null)

const parseForm = reactive({
  sheet_name: '',
  data_date: new Date().toISOString().slice(0, 10),
  header_row_index: null as number | null,
  data_start_row_index: null as number | null,
  multi_header: false,
})

const headerEndRow = ref<number | null>(null)
const importSteps = [
  { step: 1, index: '第一步', title: '上传 Excel' },
  { step: 2, index: '第二步', title: '选择 Sheet' },
  { step: 3, index: '第三步', title: '字段映射' },
  { step: 4, index: '第四步', title: '导入校验' },
  { step: 5, index: '第五步', title: '确认导入' },
  { step: 6, index: '第六步', title: '发布批次' },
]

const activeStep = computed(() => {
  if (importMode.value === 'multi' && multiSheetRows.value.some((row) => row.status === 'published')) return 6
  if (importMode.value === 'multi' && multiConfirmResult.value) return 5
  if (importMode.value === 'multi' && multiSheetRows.value.some((row) => row.issues.length)) return 4
  if (importMode.value === 'multi' && multiSheetRows.value.length) return 3
  if (previewRows.value.length) return 3
  if (batch.value) return 2
  return 1
})
const nonProgressSheetNotice = computed(() => {
  if (importMode.value === 'multi') return ''
  if (!columns.value.length && !parseForm.sheet_name) return ''
  return isLikelyNonProgressSheet(parseForm.sheet_name, columns.value.map((column) => column.name))
    ? '当前 Sheet 看起来像说明表、问题记录表或字段检查表，不是工程进度数据表。一般不建议导入，请确认是否选择了正确的进度 Sheet。'
    : ''
})
const activeMultiSheet = computed(() => multiSheetRows.value.find((row) => row.sheet_name === activeMultiSheetName.value) ?? multiSheetRows.value[0] ?? null)
const multiJumpRows = computed(() => multiSheetRows.value.filter((item) => item.batch_id))
const sheetHints = computed(() => sheets.value.map((sheet) => {
  const parsed = multiSheetRows.value.find((row) => row.sheet_name === sheet)
  const columnNames = parsed?.columns.map((column) => column.name) ?? []
  const isLikelyNonProgress = isLikelyNonProgressSheet(sheet, columnNames)
  const hasProgressName = /机电|消防|智能化|进度|单位|工程/i.test(sheet)
  const columnCount = parsed?.columns.length ?? 0
  const rowCount = parsed?.row_count ?? 0
  const isLikelyProgress = !isLikelyNonProgress && (hasProgressName || columnCount >= 6)
  const recommendation = isLikelyProgress
    ? '推荐导入'
    : isLikelyNonProgress
      ? '可能不是进度 Sheet，请确认'
      : columnCount > 0 && columnCount < 5
        ? '字段较少，建议检查'
        : '请解析后确认字段'
  return {
    name: sheet,
    rowCount: parsed ? rowCount : '-',
    columnCount: parsed ? columnCount : '-',
    isLikelyProgress,
    isLikelyNonProgress,
    recommendation,
  }
}))
const multiParsedRows = computed(() => multiSheetRows.value.filter((row) => row.batch_id && row.status !== 'parse_failed'))
const multiImportableRows = computed(() => multiSheetRows.value.filter((row) => row.batch_id && (row.status === 'parsed' || row.status === 'validated') && row.error_count === 0))
const multiPublishableBatchIds = computed(() => multiSheetRows.value.filter((row) => row.batch_id && row.status === 'imported' && row.imported_count > 0 && row.error_count === 0).map((row) => row.batch_id as number))
const bulkTemplateOptions = computed(() => {
  const byId = new Map<number, MatchedTemplate>()
  multiSheetRows.value.forEach((row) => row.suggested_mappings.forEach((template) => {
    if (!byId.has(template.id)) byId.set(template.id, template)
  }))
  return Array.from(byId.values()).sort((a, b) => b.match_score - a.match_score)
})
const multiSummary = computed(() => ({
  totalSheets: multiSheetRows.value.length,
  successSheets: multiSheetRows.value.filter((row) => row.imported_count > 0 && (row.status === 'imported' || row.status === 'published')).length,
  failedSheets: multiSheetRows.value.filter((row) => isFailedStatus(row.status) || row.publish_status === 'unpublishable').length,
  publishedSheets: multiSheetRows.value.filter((row) => row.status === 'published').length,
  failedPublishSheets: multiSheetRows.value.filter((row) => row.status === 'publish_failed' || row.publish_status === 'publish_failed').length,
  importedRows: multiSheetRows.value.reduce((sum, row) => sum + row.imported_count, 0),
  skippedRows: multiSheetRows.value.reduce((sum, row) => sum + row.skipped_count, 0),
  warningCount: multiSheetRows.value.reduce((sum, row) => sum + row.warning_count, 0),
  errorCount: multiSheetRows.value.reduce((sum, row) => sum + row.error_count, 0),
}))

type MultiSheetRow = {
  sheet_name: string
  status: string
  batch_id?: number | null
  row_count: number
  columns: ParsedColumn[]
  preview_rows: Record<string, unknown>[]
  suggested_mappings: MatchedTemplate[]
  mappings: FieldMapping[]
  issues: ImportValidationIssue[]
  warning_count: number
  error_count: number
  skipped_count: number
  imported_count: number
  publish_status: string
  publishing: boolean
  downloadingErrorReport?: boolean
  data_quality_score?: number | null
  header_recommendation?: HeaderRecommendation | null
  error?: string | null
  note?: string | null
}

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

function handleFileChange(uploadFile: UploadFile) {
  selectedFile.value = uploadFile.raw ?? null
}

function handleFileRemove() {
  selectedFile.value = null
  batch.value = null
  sheets.value = []
  selectedSheetNames.value = []
  multiSheetRows.value = []
  parseForm.sheet_name = ''
  clearParsedSheetState()
}

function handleSheetChange() {
  parseForm.header_row_index = null
  parseForm.data_start_row_index = null
  clearParsedSheetState()
}

function handleRowSettingChange() {
  clearParsedSheetState()
  if (batch.value && parseForm.sheet_name) {
    void parseFile()
  }
}

function clearParsedSheetState() {
  columns.value = []
  previewRows.value = []
  headerRecommendation.value = null
  if (batch.value) {
    sessionStorage.removeItem(`import:${batch.value.id}:parse`)
  }
}

async function uploadFile() {
  if (!selectedFile.value) return
  uploading.value = true
  errorMessage.value = ''
    columns.value = []
    previewRows.value = []
    headerRecommendation.value = null
  try {
    const response = await uploadImportFile(projectId, selectedFile.value, parseForm.data_date)
    batch.value = response.batch
    sheets.value = response.sheets
    parseForm.sheet_name = response.sheets[0] ?? ''
    selectedSheetNames.value = response.sheets.slice(0, 3)
    parseForm.header_row_index = null
    parseForm.data_start_row_index = null
    multiSheetRows.value = []
    multiConfirmResult.value = null
    clearParsedSheetState()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '文件上传失败'
  } finally {
    uploading.value = false
  }
}

async function parseFile() {
  if (!batch.value) return
  if (!parseForm.sheet_name) {
    errorMessage.value = '请先选择要导入的 Sheet'
    return
  }
  parsing.value = true
  errorMessage.value = ''
  try {
    const response = await parseImportBatch(batch.value.id, {
      ...parseForm,
      header_end_row_index: parseForm.multi_header ? headerEndRow.value : null,
    })
    batch.value = response.batch
    columns.value = response.columns
    previewRows.value = response.preview_rows
    headerRecommendation.value = response.header_recommendation ?? null
    parseForm.header_row_index = response.batch.header_row_index ?? null
    parseForm.data_start_row_index = response.batch.data_start_row_index ?? null
    sessionStorage.setItem(`import:${response.batch.id}:parse`, JSON.stringify(response))
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '文件解析失败'
  } finally {
    parsing.value = false
  }
}

function goMapping() {
  if (!batch.value) return
  router.push(`/imports/${batch.value.id}/mapping`)
}

function buildDefaultMappings(columns: ParsedColumn[]): FieldMapping[] {
  return columns.map((column, index) => ({
    excel_column_name: column.name,
    recommended_field: column.recommended_field,
    system_field_name: column.recommended_field,
    field_type: column.field_type,
    is_dimension: column.is_dimension,
    is_metric: column.is_metric,
    is_required: false,
    save_to_extra: column.save_to_extra,
    sort_order: index,
  }))
}

async function parseMultiSheets() {
  if (!batch.value || !selectedSheetNames.value.length) return
  multiParsing.value = true
  errorMessage.value = ''
  try {
    const response = await parseMultipleSheets(batch.value.id, {
      project_id: projectId,
      sheet_names: selectedSheetNames.value,
      header_row_index: parseForm.header_row_index,
      data_start_row_index: parseForm.data_start_row_index,
      data_date: parseForm.data_date,
      baseline_plan_id: baselinePlanId.value,
      multi_header: parseForm.multi_header,
      header_end_row_index: parseForm.multi_header ? headerEndRow.value : null,
    })
    multiParseResult.value = response as never
    multiConfirmResult.value = null
    multiSheetRows.value = response.results.map((result) => ({
      sheet_name: result.sheet_name,
      status: result.status === 'parsed' ? 'parsed' : 'parse_failed',
      batch_id: result.batch_id,
      row_count: result.row_count,
      columns: result.columns,
      preview_rows: result.preview_rows,
      suggested_mappings: result.suggested_mappings,
      header_recommendation: result.header_recommendation ?? null,
      mappings: buildDefaultMappings(result.columns),
      issues: [],
      warning_count: 0,
      error_count: result.error ? 1 : 0,
      skipped_count: 0,
      imported_count: 0,
      data_quality_score: null,
      error: result.error,
      publish_status: 'unpublished',
      publishing: false,
    }))
    activeMultiSheetName.value = multiSheetRows.value[0]?.sheet_name ?? ''
    quickBatchId.value = multiSheetRows.value.find((row) => row.batch_id)?.batch_id ?? null
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '多 Sheet 解析失败'
  } finally {
    multiParsing.value = false
  }
}

async function validateMultiSheets() {
  const sheetsToValidate = multiSheetRows.value.filter((row) => row.batch_id && row.status !== 'error')
  if (!sheetsToValidate.length) return
  multiValidating.value = true
  errorMessage.value = ''
  try {
    const response = await validateMultipleSheets(sheetsToValidate.map((row) => ({
      batch_id: row.batch_id as number,
      sheet_name: row.sheet_name,
      mappings: row.mappings,
      header_row_index: parseForm.header_row_index,
      data_start_row_index: parseForm.data_start_row_index,
    })))
    response.results.forEach((result) => {
      const row = multiSheetRows.value.find((item) => item.batch_id === result.batch_id)
      if (!row) return
      row.warning_count = result.warning_count
      row.error_count = result.error_count
      row.skipped_count = result.skipped_count
      row.data_quality_score = result.data_quality_score
      row.issues = result.issues
      row.error = result.error
      row.status = result.error ? 'validate_failed' : result.valid ? 'validated' : 'validate_failed'
      if (result.error_count > 0) {
        row.publish_status = 'unpublishable'
      } else if (result.skipped_count > 0 && result.error_count === 0 && row.imported_count === 0) {
        row.publish_status = 'unpublished'
      }
    })
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '多 Sheet 校验失败'
  } finally {
    multiValidating.value = false
  }
}

async function confirmMultiSheets() {
  const rows = multiSheetRows.value.filter((row) => row.batch_id && row.status !== 'error')
  if (!rows.length) return
  multiConfirming.value = true
  errorMessage.value = ''
  try {
    const response = await confirmMultipleSheets({
      project_id: projectId,
      data_date: parseForm.data_date,
      baseline_plan_id: baselinePlanId.value,
      sheets: rows.map((row) => ({
        batch_id: row.batch_id as number,
        sheet_name: row.sheet_name,
        mappings: row.mappings,
        import_strategy: multiImportStrategy.value,
        save_template: false,
        template_name: null,
      })),
    })
    multiConfirmResult.value = response
    quickBatchId.value = response.batches.find((result) => result.batch_id)?.batch_id ?? quickBatchId.value
    response.batches.forEach((result) => {
      const row = multiSheetRows.value.find((item) => item.sheet_name === result.sheet_name && item.batch_id === result.batch_id)
      if (!row) return
      row.imported_count = result.imported_count
      row.skipped_count = result.skipped_count
      row.warning_count = result.warning_count
      row.error_count = result.error_count
      if (result.status === 'imported' && result.imported_count > 0) {
        row.status = 'imported'
        row.publish_status = 'unpublished'
      } else if (result.error_count > 0) {
        row.status = 'validate_failed'
        row.publish_status = 'unpublishable'
      } else if (result.imported_count === 0 && result.skipped_count > 0) {
        row.status = 'no_valid_data'
        row.publish_status = 'unpublishable'
      } else {
        row.status = 'confirm_failed'
        row.publish_status = 'unpublishable'
      }
      row.error = result.error
    })
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '多 Sheet 确认导入失败'
  } finally {
    multiConfirming.value = false
  }
}

async function publishMultiSheets() {
  if (!multiPublishableBatchIds.value.length) return
  multiPublishing.value = true
  errorMessage.value = ''
  try {
    const response = await publishMultipleSheets(multiPublishableBatchIds.value)
    response.results.forEach((result) => {
      const row = multiSheetRows.value.find((item) => item.batch_id === result.batch_id)
      if (!row) return
      row.publish_status = result.published ? 'published' : (result.status === 'unpublishable' ? 'unpublishable' : 'publish_failed')
      if (result.published) {
        row.status = result.status
      } else {
        row.error = result.error
      }
    })
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '多 Sheet 发布失败'
  } finally {
    multiPublishing.value = false
  }
}

async function publishOneSheet(row: MultiSheetRow) {
  if (!row.batch_id) return
  row.publishing = true
  errorMessage.value = ''
  try {
    const response = await publishMultipleSheets([row.batch_id])
    const result = response.results[0]
    row.publish_status = result.published ? 'published' : (result.status === 'unpublishable' ? 'unpublishable' : 'publish_failed')
    if (result.published) {
      row.status = result.status
      row.error = null
    } else {
      row.error = result.error
    }
  } catch (error) {
    row.publish_status = 'publish_failed'
    row.error = error instanceof Error ? error.message : '发布失败'
  } finally {
    row.publishing = false
  }
}

function setActiveMultiSheet(row: MultiSheetRow | null) {
  if (row) activeMultiSheetName.value = row.sheet_name
}

function applyMultiTemplate(row: MultiSheetRow, template: MatchedTemplate) {
  const templateByColumn = new Map(template.fields.map((field) => [field.excel_column_name, field]))
  row.mappings = row.mappings.map((mapping) => ({
    ...mapping,
    ...(templateByColumn.get(mapping.excel_column_name) ?? {}),
  }))
}

function applyBulkTemplate() {
  const template = bulkTemplateOptions.value.find((item) => item.id === bulkTemplateId.value)
  if (!template) return
  multiSheetRows.value.forEach((row) => applyMultiTemplate(row, template))
}

function reprocessSheet(row: MultiSheetRow) {
  activeMultiSheetName.value = row.sheet_name
  row.status = row.batch_id ? 'parsed' : 'parse_failed'
  row.error = null
  row.publish_status = 'unpublished'
  row.note = null
  row.issues = []
  row.warning_count = 0
  row.error_count = 0
}

function resetMultiImport() {
  multiSheetRows.value = []
  multiConfirmResult.value = null
  activeMultiSheetName.value = ''
}

function exportMultiIssues() {
  const rows = multiSheetRows.value.flatMap((sheet) =>
    sheet.issues.map((issue) => ({
      Sheet: sheet.sheet_name,
      Level: issue.level,
      Row: issue.row_index ?? '',
      Column: issue.column_name ?? '',
      Code: issue.code ?? '',
      Message: issue.message,
    })),
  )
  const header = ['Sheet', 'Level', 'Row', 'Column', 'Code', 'Message']
  const csv = [header.join(','), ...rows.map((row) => header.map((key) => JSON.stringify(row[key as keyof typeof row] ?? '')).join(','))].join('\n')
  const blob = new Blob([`\uFEFF${csv}`], { type: 'text/csv;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = `multi-sheet-issues-${Date.now()}.csv`
  link.click()
  URL.revokeObjectURL(url)
}

async function downloadSheetErrorReport(row: MultiSheetRow) {
  if (!row.batch_id) return
  row.downloadingErrorReport = true
  errorMessage.value = ''
  try {
    const { blob, filename } = await downloadImportErrorReport(row.batch_id)
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = filename
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    URL.revokeObjectURL(url)
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '\u9519\u8BEF\u6E05\u5355\u4E0B\u8F7D\u5931\u8D25'
  } finally {
    row.downloadingErrorReport = false
  }
}

function statusText(status: string) {
  return ({
    parse_failed: '未导入',
    validate_failed: '校验失败',
    confirm_failed: '未导入',
    publish_failed: '未发布',
    parsed: '已解析',
    validated: '校验通过',
    warning: '已导入',
    error: '校验失败',
    imported: '已导入',
    published: '已发布',
    failed: '未导入',
    blocked: '跳过',
    no_valid_data: '未生成有效进度数据',
    non_progress: '非进度 Sheet',
  } as Record<string, string>)[status] ?? status
}

function statusTag(status: string) {
  if (status === 'published' || status === 'imported') return 'success'
  if (status === 'validated' || status === 'warning' || status === 'parsed' || status === 'blocked' || status === 'no_valid_data' || status === 'non_progress') return 'warning'
  if (status === 'error' || status === 'failed' || isFailedStatus(status)) return 'danger'
  return 'info'
}

function publishStatusText(status: string) {
  return ({
    unpublished: '未发布',
    published: '已发布',
    publish_failed: '未发布',
    unpublishable: '不可发布',
  } as Record<string, string>)[status] ?? status
}

function publishTag(status: string) {
  if (status === 'published') return 'success'
  if (status === 'publish_failed') return 'danger'
  if (status === 'unpublishable') return 'warning'
  return 'info'
}

function isFailedStatus(status: string) {
  return ['parse_failed', 'validate_failed', 'confirm_failed', 'publish_failed', 'failed', 'error'].includes(status)
}

function isBlockedSheet(row: MultiSheetRow) {
  return row.error_count > 0 || row.imported_count <= 0
}

function selectSheetHint(sheetName: string) {
  if (importMode.value === 'single') {
    parseForm.sheet_name = sheetName
    handleSheetChange()
    return
  }
  if (!selectedSheetNames.value.includes(sheetName)) {
    selectedSheetNames.value = [...selectedSheetNames.value, sheetName]
  }
  activeMultiSheetName.value = sheetName
}

function unmappedFields(row: MultiSheetRow) {
  return row.mappings
    .filter((mapping) => !mapping.system_field_name && !mapping.save_to_extra)
    .map((mapping) => mapping.excel_column_name)
}

function missingRequiredFields(row: MultiSheetRow) {
  const mapped = new Set(row.mappings.map((mapping) => mapping.system_field_name).filter(Boolean))
  const missing: string[] = []
  if (!mapped.has('task_name')) missing.push('任务名称')
  if (!mapped.has('actual_percent') && !mapped.has('actual_quantity') && !mapped.has('cumulative_quantity')) {
    missing.push('实际进度字段')
  }
  return missing
}

function filteredIssues(issues: ImportValidationIssue[]) {
  if (multiIssueFilter.value === 'all') return issues
  return issues.filter((issue) => issue.level === multiIssueFilter.value)
}

function groupedIssues(issues: ImportValidationIssue[]) {
  const groups = new Map<string, { level: string; code: string; count: number; explanation: string }>()
  filteredIssues(issues).forEach((issue) => {
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
}

function issueExplanation(code: string, message = '') {
  const text = `${code} ${message}`.toLowerCase()
  if (text.includes('date') || text.includes('日期')) return '日期格式不正确或无法识别，请检查原表日期列。'
  if (text.includes('negative') || text.includes('负数')) return '工程量或数量不应为负数，请确认是否为录入错误。'
  if (text.includes('percent') || text.includes('range') || text.includes('完成率')) return '完成率应在 0% 到 100% 范围内，请检查百分比格式。'
  return message || '请检查原始数据和字段映射。'
}

function friendlyImportError(error?: string | null) {
  if (!error) return '-'
  if (error.includes('未生成有效进度数据')) return '未生成有效进度数据，可能是辅助 Sheet 或非进度明细表，不建议发布。'
  if (error.includes('存在校验错误')) return '存在校验错误，不能发布。点击查看具体错误。'
  if (error.includes('进度明细表')) return '该 Sheet 可能不是进度明细表，建议不要作为进度批次导入。'
  if (/traceback|stack trace|exception/i.test(error)) return '导入处理失败，请查看系统诊断日志。'
  if (/network|failed to fetch/i.test(error)) return '无法连接后端服务，请运行 scripts\\dev_start.bat 或 scripts\\start.bat。'
  return error.replace(/\bNone\b|\bnull\b|\bundefined\b/g, '-')
}

function selectedQuickBatchId() {
  return quickBatchId.value ?? multiJumpRows.value[0]?.batch_id ?? null
}

function goBatchDashboard() {
  const batchId = selectedQuickBatchId()
  router.push({ path: `/projects/${projectId}/dashboard`, query: batchId ? { batch_id: String(batchId) } : {} })
}

function goBatchItems() {
  const batchId = selectedQuickBatchId()
  router.push({ path: `/projects/${projectId}/items`, query: batchId ? { batch_id: String(batchId) } : {} })
}

function goBatchWarnings() {
  const batchId = selectedQuickBatchId()
  router.push({ path: `/projects/${projectId}/warnings`, query: batchId ? { batch_id: String(batchId) } : {} })
}

function topTemplateText(row: MultiSheetRow) {
  const template = row.suggested_mappings[0]
  return template ? `${template.name}｜匹配度 ${templateMatchText(template.match_score)}` : '暂无推荐模板'
}

function isLowTemplateMatch(row: MultiSheetRow) {
  const score = row.suggested_mappings[0]?.match_score ?? 0
  return score > 0 && score < 0.75
}

function templateMatchText(score: number) {
  return `${Math.round(score * 100)}%`
}

async function loadBaselineOptions() {
  baselineOptions.value = (await listBaselinePlans(projectId)).filter((baseline) => baseline.is_active)
  baselinePlanId.value = baselineOptions.value.find((baseline) => baseline.is_default)?.id ?? null
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

onMounted(() => {
  void loadBaselineOptions()
})
</script>
