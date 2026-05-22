<template>
  <main class="page-shell dashboard-shell">
    <section class="page-heading">
      <div>
        <p class="eyebrow">local maintenance</p>
        <h1>系统维护</h1>
      </div>
      <el-button type="primary" :loading="loading" @click="loadSummary">刷新</el-button>
    </section>

    <el-alert v-if="errorMessage" :title="errorMessage" type="error" show-icon :closable="false" />

    <section class="table-surface">
      <div class="section-title">
        <div>
          <h2>本地运行状态</h2>
          <p>用于确认本机服务、数据目录和最近备份情况。</p>
        </div>
        <el-tag :type="runtimeStatus?.backend_status === 'running' ? 'success' : 'danger'">
          {{ runtimeStatus?.backend_status === 'running' ? '后端运行中' : '后端状态未知' }}
        </el-tag>
      </div>
      <div class="runtime-grid">
        <div><span>当前版本</span><strong>{{ runtimeStatus?.app_version ?? '-' }}</strong></div>
        <div><span>运行模式</span><strong>{{ portableModeText }}</strong></div>
        <div><span>后端启动时间</span><strong>{{ runtimeStatus?.backend_started_at ?? '-' }}</strong></div>
        <div><span>最近备份时间</span><strong>{{ backupTimeText }}</strong></div>
        <div><span>最近诊断时间</span><strong>{{ diagnoseTimeText }}</strong></div>
        <div><span>数据库状态</span><strong>{{ runtimeStatus?.database_exists ? '已找到' : '未找到' }}</strong></div>
        <div><span>前端构建产物</span><strong>{{ runtimeStatus?.frontend_dist_exists ? '已找到' : '未检测到' }}</strong></div>
        <div><span>项目数量</span><strong>{{ runtimeStatus?.project_count ?? '-' }}</strong></div>
        <div><span>导入批次数</span><strong>{{ runtimeStatus?.import_batch_count ?? '-' }}</strong></div>
        <div><span>进度明细数量</span><strong>{{ runtimeStatus?.progress_item_count ?? '-' }}</strong></div>
        <div><span>报表导出数量</span><strong>{{ runtimeStatus?.report_export_count ?? '-' }}</strong></div>
      </div>
    </section>

    <section class="dashboard-card-grid">
      <div class="metric-card">
        <span>项目数量</span>
        <strong>{{ summary?.project_count ?? '-' }}</strong>
      </div>
      <div class="metric-card">
        <span>导入批次数</span>
        <strong>{{ summary?.import_batch_count ?? '-' }}</strong>
      </div>
      <div class="metric-card">
        <span>进度明细数量</span>
        <strong>{{ summary?.progress_item_count ?? '-' }}</strong>
      </div>
      <div class="metric-card">
        <span>报表导出数量</span>
        <strong>{{ summary?.report_export_count ?? '-' }}</strong>
      </div>
    </section>

    <section class="table-surface">
      <div class="section-title">
        <div>
          <h2>桌面使用入口</h2>
          <p>便携版常用入口和本地说明，适合交付到现场电脑后快速定位。</p>
        </div>
      </div>
      <div class="desktop-actions">
        <div>
          <span>创建桌面快捷方式</span>
          <strong>双击 portable 根目录的 create_shortcut.bat，快捷方式会指向 start.bat。</strong>
        </div>
        <el-button @click="copyPath('create_shortcut.bat')">复制脚本名称</el-button>
        <el-button @click="router.push('/help')">打开帮助中心</el-button>
        <el-button @click="router.push('/about')">查看版本信息</el-button>
        <el-button @click="restoreGuideVisible = true">查看恢复说明</el-button>
      </div>
    </section>

    <section class="table-surface">
      <div class="section-title">
        <div>
          <h2>数据体检</h2>
          <p>只读扫描项目、批次、文件和数据规模。</p>
        </div>
      </div>
      <div class="runtime-grid">
        <template v-for="group in healthGroups" :key="group.title">
          <div class="health-group-title">{{ group.title }}</div>
          <div v-for="item in group.items" :key="`${group.title}-${item.label}`">
            <span>{{ item.label }}</span>
            <strong>{{ item.value }}</strong>
          </div>
        </template>
      </div>
    </section>

    <section class="table-surface">
      <div class="section-title">
        <h2>本地路径</h2>
        <span>单机数据目录</span>
      </div>
      <div class="maintenance-paths">
        <div>
          <span>数据库文件</span>
          <code>{{ runtimeStatus?.database_path ?? summary?.database_url ?? '-' }}</code>
          <el-button size="small" @click="copyPath(runtimeStatus?.database_path ?? summary?.database_url)">复制路径</el-button>
        </div>
        <div>
          <span>上传目录</span>
          <code>{{ runtimeStatus?.upload_dir ?? summary?.upload_dir ?? '-' }}</code>
          <el-button size="small" @click="copyPath(runtimeStatus?.upload_dir ?? summary?.upload_dir)">复制路径</el-button>
        </div>
        <div>
          <span>导出目录</span>
          <code>{{ runtimeStatus?.export_dir ?? summary?.export_dir ?? '-' }}</code>
          <el-button size="small" @click="copyPath(runtimeStatus?.export_dir ?? summary?.export_dir)">复制路径</el-button>
        </div>
        <div>
          <span>备份目录</span>
          <code>{{ runtimeStatus?.backup_dir ?? '-' }}</code>
          <el-button size="small" @click="copyPath(runtimeStatus?.backup_dir)">复制路径</el-button>
        </div>
        <div>
          <span>数据目录</span>
          <code>{{ runtimeStatus?.data_dir ?? '-' }}</code>
          <el-button size="small" @click="copyPath(runtimeStatus?.data_dir)">复制路径</el-button>
        </div>
        <div>
          <span>日志目录</span>
          <code>{{ runtimeStatus?.log_dir ?? '-' }}</code>
          <el-button size="small" @click="copyPath(runtimeStatus?.log_dir)">复制路径</el-button>
        </div>
      </div>
      <el-alert
        class="parse-hint"
        title="浏览器通常不能直接打开本地目录。请复制路径后在资源管理器地址栏中打开。"
        type="info"
        show-icon
        :closable="false"
      />
      <el-table v-if="cleanupPreview" class="preview-table" :data="cleanupPreview.details" empty-text="暂无预览明细">
        <el-table-column label="ID" width="90">
          <template #default="{ row }">{{ row.id ?? '-' }}</template>
        </el-table-column>
        <el-table-column label="名称 / 文件" min-width="180">
          <template #default="{ row }">{{ row.name ?? '-' }}</template>
        </el-table-column>
        <el-table-column label="路径 / 状态" min-width="220">
          <template #default="{ row }">{{ row.path ?? row.status ?? '-' }}</template>
        </el-table-column>
      </el-table>
      <el-alert
        v-if="cleanupPreview"
        class="parse-hint"
        :title="`预览：将影响 ${cleanupPreview.affected_count} 项，跳过 ${cleanupPreview.skipped_count} 项。${cleanupPreview.skipped_reasons.join('；')}`"
        type="info"
        show-icon
        :closable="false"
      />
    </section>

    <section class="form-surface">
      <div class="section-title">
        <div>
          <h2>本地诊断</h2>
          <p>诊断脚本只检查环境和目录，不会启动系统或修改数据。</p>
        </div>
      </div>
      <div class="backup-command">
        <code>scripts\diagnose.bat</code>
      </div>
      <div class="maintenance-paths diagnose-paths">
        <div>
          <span>最近诊断日志</span>
          <code>{{ runtimeStatus?.last_diagnose_log_path ?? '暂无诊断日志' }}</code>
          <el-button size="small" @click="copyPath(runtimeStatus?.last_diagnose_log_path)">复制路径</el-button>
        </div>
      </div>
      <div class="actions-row">
        <el-button @click="copyPath('scripts\\diagnose.bat')">复制诊断命令</el-button>
        <el-button @click="copyPath(runtimeStatus?.log_dir)">复制日志目录</el-button>
      </div>
    </section>

    <section class="form-surface">
      <div class="section-title">
        <div>
          <h2>安全清理</h2>
          <p>先 dry-run 预览，确认后执行；不处理已发布和冻结批次。</p>
        </div>
      </div>
      <div class="actions-row">
        <el-button :loading="cleaning === 'unpublished_batches'" @click="handleSafeCleanup('unpublished_batches')">
          清理未发布批次
        </el-button>
        <el-button :loading="cleaning === 'empty_projects'" @click="handleSafeCleanup('empty_projects')">
          清理空项目
        </el-button>
        <el-button :loading="cleaning === 'temp_files'" @click="handleSafeCleanup('temp_files')">
          清理临时文件
        </el-button>
        <el-button :loading="cleaning === 'orphan_export_records'" @click="handleSafeCleanup('orphan_export_records')">
          清理孤立导出记录
        </el-button>
      </div>
      <el-alert
        class="parse-hint"
        title="空项目仅匹配测试/示例类名称且没有任何业务数据的项目。"
        type="warning"
        show-icon
        :closable="false"
      />
    </section>

    <section class="table-surface">
      <div class="section-title">
        <div>
          <h2>备份恢复向导</h2>
          <p>选择备份、校验完整性，二次确认后恢复数据库、上传文件和导出文件。</p>
        </div>
        <el-button @click="restoreGuideVisible = true">查看恢复说明</el-button>
      </div>
      <el-steps :active="restoreStep - 1" finish-status="success" simple>
        <el-step title="选择备份" />
        <el-step title="校验备份" />
        <el-step title="查看内容" />
        <el-step title="风险确认" />
        <el-step title="执行恢复" />
        <el-step title="提示重启" />
      </el-steps>
      <el-table :data="backupRecords" empty-text="暂无备份记录">
        <el-table-column prop="name" label="备份名称" min-width="180" />
        <el-table-column prop="backup_time" label="备份时间" width="160" />
        <el-table-column label="内容" min-width="180">
          <template #default="{ row }">
            <el-tag :type="row.has_database ? 'success' : 'info'">数据库</el-tag>
            <el-tag :type="row.has_uploads ? 'success' : 'info'">uploads</el-tag>
            <el-tag :type="row.has_exports ? 'success' : 'info'">exports</el-tag>
            <el-tag :type="row.has_backup_info ? 'success' : 'info'">backup_info</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="校验" width="180">
          <template #default="{ row }">
            <el-tag :type="row.validation_status === '完整' ? 'success' : 'warning'">{{ row.validation_status }}</el-tag>
            <span v-if="row.missing_items.length">缺: {{ row.missing_items.join(', ') }}</span>
          </template>
        </el-table-column>
        <el-table-column label="大小" width="110">
          <template #default="{ row }">{{ formatBytes(row.size) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="280">
          <template #default="{ row }">
            <el-button text type="primary" @click="selectBackup(row)">选择</el-button>
            <el-button text @click="openBackupInfo(row)">查看说明</el-button>
            <el-button text @click="copyPath(row.backup_path)">复制路径</el-button>
          </template>
        </el-table-column>
      </el-table>
      <div v-if="selectedBackup" class="restore-panel">
        <div class="section-title">
          <div>
            <h3>{{ selectedBackup.name }}</h3>
            <p>{{ selectedBackup.backup_path }}</p>
          </div>
          <el-tag :type="selectedBackup.validation_status === '完整' ? 'success' : 'danger'">{{ selectedBackup.validation_status }}</el-tag>
        </div>
        <div class="runtime-grid">
          <div><span>备份时间</span><strong>{{ selectedBackup.backup_time }}</strong></div>
          <div><span>备份大小</span><strong>{{ formatBytes(selectedBackup.size) }}</strong></div>
          <div><span>数据库</span><strong>{{ selectedBackup.has_database ? '包含' : '缺失' }}</strong></div>
          <div><span>uploads</span><strong>{{ selectedBackup.has_uploads ? '包含' : '缺失' }}</strong></div>
          <div><span>exports / reports</span><strong>{{ selectedBackup.has_exports ? '包含' : '缺失' }}</strong></div>
          <div><span>backup_info.txt</span><strong>{{ selectedBackup.has_backup_info ? '包含' : '缺失' }}</strong></div>
        </div>
        <el-alert
          v-if="selectedBackup.missing_items.length"
          class="parse-hint"
          :title="`不完整备份禁止恢复，缺失：${selectedBackup.missing_items.join('、')}`"
          type="error"
          show-icon
          :closable="false"
        />
        <el-alert
          class="parse-hint"
          title="恢复操作会覆盖当前数据库、上传文件和导出文件。系统会在恢复前自动备份当前数据。"
          type="warning"
          show-icon
          :closable="false"
        />
        <div class="restore-confirm">
          <el-input
            v-model="restoreConfirmText"
            placeholder="请输入：我确认恢复备份"
            :disabled="selectedBackup.validation_status !== '完整'"
          />
        </div>
        <div class="actions-row table-actions">
          <el-button :loading="backupDetailLoading" @click="loadBackupDetail(selectedBackup.name)">查看备份详情</el-button>
          <el-button :loading="backupValidating" @click="validateSelectedBackup">校验备份完整性</el-button>
          <el-button
            type="danger"
            :disabled="!canRestoreSelectedBackup"
            :loading="backupRestoring"
            @click="restoreSelectedBackup"
          >
            执行恢复
          </el-button>
        </div>
      </div>
      <el-result
        v-if="restoreResult"
        icon="success"
        title="恢复完成"
        :sub-title="`${restoreResult.message} 恢复前自动备份：${restoreResult.pre_restore_backup_name}`"
      />
    </section>

    <section class="table-surface">
      <div class="section-title">
        <div>
          <h2>维护日志</h2>
          <p>最近 20 条项目归档、批次冻结和清理记录。</p>
        </div>
        <el-select v-model="logActionFilter" clearable placeholder="筛选动作" style="width: 220px" @change="loadSummary">
          <el-option v-for="action in logActions" :key="action" :label="action" :value="action" />
        </el-select>
      </div>
      <el-table :data="maintenanceLogs" empty-text="暂无维护日志">
        <el-table-column prop="created_at" label="时间" width="170" />
        <el-table-column prop="action" label="动作" width="190" />
        <el-table-column prop="summary" label="摘要" min-width="220" />
        <el-table-column prop="detail" label="详情" min-width="180" />
        <el-table-column label="操作" width="100">
          <template #default="{ row }">
            <el-button text type="primary" @click="openLogDetail(row.id)">详情</el-button>
          </template>
        </el-table-column>
      </el-table>
    </section>

    <section class="table-surface">
      <div class="section-title">
        <div>
          <h2>AI 调用记录</h2>
          <p>最近 AI 请求摘要，不包含 API Key 和原始明细。</p>
        </div>
      </div>
      <el-table :data="aiCallLogs" empty-text="暂无 AI 调用记录">
        <el-table-column prop="created_at" label="时间" width="170" />
        <el-table-column prop="mode" label="模式" width="180" />
        <el-table-column prop="model" label="模型" width="140" />
        <el-table-column prop="source" label="来源" width="110" />
        <el-table-column label="结果" width="110">
          <template #default="{ row }"><el-tag :type="row.success ? 'success' : 'warning'">{{ row.success ? '成功' : '回退' }}</el-tag></template>
        </el-table-column>
        <el-table-column prop="duration_ms" label="耗时(ms)" width="110" />
        <el-table-column prop="input_summary_length" label="输入摘要长度" width="130" />
        <el-table-column prop="output_length" label="输出长度" width="110" />
        <el-table-column prop="error_message" label="错误信息" min-width="220" show-overflow-tooltip />
      </el-table>
    </section>

    <section class="form-surface">
      <div class="section-title">
        <div>
          <h2>备份说明</h2>
          <p>运行脚本会备份 SQLite 数据库、上传文件和导出报表。</p>
        </div>
      </div>
      <div class="backup-command">
        <code>{{ summary?.backup_command ?? 'scripts\\backup.bat' }}</code>
      </div>
      <div class="actions-row">
        <el-button @click="copyPath(summary?.backup_command ?? 'scripts\\backup.bat')">复制备份命令</el-button>
        <el-button @click="restoreGuideVisible = true">查看恢复说明</el-button>
      </div>
    </section>

    <el-dialog v-model="restoreGuideVisible" title="恢复备份说明" width="620px">
      <el-alert title="恢复操作会覆盖当前数据，请先确认已关闭系统并额外备份当前数据。" type="warning" show-icon :closable="false" />
      <ol class="restore-guide">
        <li>运行 scripts\\stop.bat 关闭系统。</li>
        <li>运行 scripts\\backup.bat 备份当前数据库、上传文件和导出报表。</li>
        <li>从目标备份目录中复制数据库文件，覆盖当前数据库文件。</li>
        <li>将备份中的 uploads 目录复制回当前上传目录。</li>
        <li>如需恢复历史导出文件，将备份中的 reports 目录复制回当前导出目录。</li>
        <li>运行 scripts\\start.bat 重新启动系统。</li>
      </ol>
    </el-dialog>

    <el-dialog v-model="backupInfoVisible" title="backup_info.txt" width="680px">
      <pre class="detail-pre">{{ selectedBackupInfo || '该备份暂无 backup_info.txt。' }}</pre>
    </el-dialog>

    <el-dialog v-model="logDetailVisible" title="维护日志详情" width="620px">
      <el-descriptions v-if="selectedLog" :column="1" border>
        <el-descriptions-item label="操作类型">{{ selectedLog.action }}</el-descriptions-item>
        <el-descriptions-item label="目标类型">{{ selectedLog.target_type || '-' }}</el-descriptions-item>
        <el-descriptions-item label="目标 ID">{{ selectedLog.target_id ?? '-' }}</el-descriptions-item>
        <el-descriptions-item label="摘要">{{ selectedLog.summary }}</el-descriptions-item>
        <el-descriptions-item label="详情">{{ selectedLog.detail || '-' }}</el-descriptions-item>
        <el-descriptions-item label="生成时间">{{ selectedLog.created_at }}</el-descriptions-item>
      </el-descriptions>
    </el-dialog>
  </main>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'

import { getBackupRecord, getDataHealth, getMaintenanceLog, getMaintenanceSummary, getRuntimeStatus, listAiCallLogs, listBackupRecords, listMaintenanceLogs, restoreBackupRecord, safeCleanup, validateBackupRecord } from '../api/maintenance'
import type { BackupRecord, BackupRestoreResponse, CleanupResponse, DataHealth, MaintenanceAiCallLog, MaintenanceLog, MaintenanceSummary, RuntimeStatus } from '../types/maintenance'

const router = useRouter()
const summary = ref<MaintenanceSummary | null>(null)
const runtimeStatus = ref<RuntimeStatus | null>(null)
const dataHealth = ref<DataHealth | null>(null)
const backupRecords = ref<BackupRecord[]>([])
const maintenanceLogs = ref<MaintenanceLog[]>([])
const aiCallLogs = ref<MaintenanceAiCallLog[]>([])
const loading = ref(false)
const cleaning = ref<string>('')
const errorMessage = ref('')
const restoreGuideVisible = ref(false)
const cleanupPreview = ref<CleanupResponse | null>(null)
const backupInfoVisible = ref(false)
const selectedBackupInfo = ref('')
const selectedBackup = ref<BackupRecord | null>(null)
const restoreConfirmText = ref('')
const restoreResult = ref<BackupRestoreResponse | null>(null)
const backupDetailLoading = ref(false)
const backupValidating = ref(false)
const backupRestoring = ref(false)
const logDetailVisible = ref(false)
const selectedLog = ref<MaintenanceLog | null>(null)
const logActionFilter = ref('')
const logActions = ['archive_project', 'restore_project', 'freeze_batch', 'unfreeze_batch', 'cleanup_unpublished_batches', 'cleanup_temp_files', 'cleanup_orphan_exports']
const backupTimeText = computed(() => {
  const value = runtimeStatus.value?.last_backup_time
  return value && value !== '-' ? value : '暂无备份记录'
})
const diagnoseTimeText = computed(() => {
  const value = runtimeStatus.value?.last_diagnose_time
  return value && value !== '-' ? value : '暂无诊断记录'
})
const portableModeText = computed(() => {
  const value = runtimeStatus.value?.portable_mode
  if (value === true) return '便携版'
  if (value === false) return '源码模式'
  return '未知'
})
const restoreStep = computed(() => {
  if (restoreResult.value) return 6
  if (backupRestoring.value) return 5
  if (restoreConfirmText.value) return 4
  if (selectedBackup.value) return selectedBackup.value.validation_status === '完整' ? 3 : 2
  return 1
})
const canRestoreSelectedBackup = computed(() =>
  selectedBackup.value?.validation_status === '完整' && restoreConfirmText.value === '我确认恢复备份',
)
const healthGroups = computed(() => {
  const health = dataHealth.value
  if (!health) return []
  return [
    { title: '项目数据', items: [['项目数', health.project_count], ['正常项目', health.active_project_count], ['归档项目', health.archived_project_count]] },
    { title: '导入批次', items: [['导入批次', health.import_batch_count], ['已发布', health.published_batch_count], ['未发布', health.unpublished_batch_count], ['冻结批次', health.frozen_batch_count], ['未冻结', health.unfrozen_batch_count]] },
    { title: '业务数据', items: [['进度明细', health.progress_item_count], ['预警记录', health.warning_record_count], ['整改项', health.rectification_item_count], ['报表记录', health.report_export_count]] },
    { title: '文件目录', items: [['孤立批次', health.orphan_batch_count], ['孤立明细', health.orphan_item_count], ['缺失文件', health.missing_file_count], ['临时文件', health.temp_file_count], ['数据库大小', formatBytes(health.database_size)], ['上传目录', formatBytes(health.upload_dir_size)], ['导出目录', formatBytes(health.export_dir_size)]] },
    { title: '备份状态', items: [['备份数量', health.total_backup_count], ['不完整备份', health.incomplete_backup_count], ['备份目录', formatBytes(health.backup_dir_size)]] },
    { title: '维护日志', items: [['日志数量', health.maintenance_log_count]] },
  ].map((group) => ({ title: group.title, items: group.items.map(([label, value]) => ({ label: String(label), value })) }))
})

async function loadSummary() {
  loading.value = true
  errorMessage.value = ''
  try {
    const [loadedSummary, loadedRuntimeStatus, loadedHealth, loadedBackups, loadedLogs, loadedAiLogs] = await Promise.all([
      getMaintenanceSummary(),
      getRuntimeStatus(),
      getDataHealth(),
      listBackupRecords(),
      listMaintenanceLogs(logActionFilter.value || undefined),
      listAiCallLogs(),
    ])
    summary.value = loadedSummary
    runtimeStatus.value = loadedRuntimeStatus
    dataHealth.value = loadedHealth
    backupRecords.value = loadedBackups
    maintenanceLogs.value = loadedLogs
    aiCallLogs.value = loadedAiLogs
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '维护信息加载失败'
  } finally {
    loading.value = false
  }
}

async function copyPath(path?: string | null) {
  const value = path || '-'
  if (value === '-') {
    ElMessage.warning('暂无可复制的路径。')
    return
  }
  try {
    await navigator.clipboard.writeText(value)
    ElMessage.success('路径已复制。')
  } catch {
    ElMessage.warning(`请手动复制路径：${value}`)
  }
}

function cleanupLabel(type: string) {
  const labels: Record<string, string> = {
    unpublished_batches: '未发布批次',
    empty_projects: '空项目',
    temp_files: '临时文件',
    orphan_export_records: '孤立导出记录',
  }
  return labels[type] ?? type
}

async function handleSafeCleanup(type: string) {
  try {
    cleaning.value = type
    const preview = await safeCleanup(type, true)
    cleanupPreview.value = preview
    cleaning.value = ''
    await ElMessageBox.confirm(`dry-run 预览将影响 ${preview.affected_count} 项、跳过 ${preview.skipped_count} 项：${cleanupLabel(type)}。是否执行？`, '确认安全清理', {
      confirmButtonText: '确认执行',
      cancelButtonText: '取消',
      type: 'warning',
    })
    cleaning.value = type
    const result = await safeCleanup(type, false)
    cleanupPreview.value = result
    ElMessage.success(`已处理 ${result.affected_count} 项，维护日志：${result.log_written ? '已写入' : '未写入'}。`)
    await loadSummary()
  } catch (error) {
    if (error instanceof Error && error.message) {
      errorMessage.value = error.message
    }
  } finally {
    cleaning.value = ''
  }
}

function openBackupInfo(record: BackupRecord) {
  selectedBackupInfo.value = record.info_content || ''
  backupInfoVisible.value = true
}

function selectBackup(record: BackupRecord) {
  selectedBackup.value = record
  restoreConfirmText.value = ''
  restoreResult.value = null
}

async function loadBackupDetail(backupName: string) {
  backupDetailLoading.value = true
  errorMessage.value = ''
  try {
    selectedBackup.value = await getBackupRecord(backupName)
    ElMessage.success('备份详情已刷新。')
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '备份详情加载失败'
  } finally {
    backupDetailLoading.value = false
  }
}

async function validateSelectedBackup() {
  if (!selectedBackup.value) return
  backupValidating.value = true
  errorMessage.value = ''
  try {
    selectedBackup.value = await validateBackupRecord(selectedBackup.value.name)
    if (selectedBackup.value.validation_status === '完整') {
      ElMessage.success('备份校验通过。')
    } else {
      ElMessage.warning(`备份不完整：${selectedBackup.value.missing_items.join('、')}`)
    }
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '备份校验失败'
  } finally {
    backupValidating.value = false
  }
}

async function restoreSelectedBackup() {
  if (!selectedBackup.value) return
  try {
    await ElMessageBox.confirm(
      '恢复操作会覆盖当前数据库、上传文件和导出文件。系统已在恢复前自动备份当前数据。请输入“我确认恢复备份”继续。',
      '恢复风险确认',
      {
        confirmButtonText: '确认恢复',
        cancelButtonText: '取消',
        type: 'warning',
      },
    )
  } catch {
    return
  }
  backupRestoring.value = true
  errorMessage.value = ''
  try {
    restoreResult.value = await restoreBackupRecord(selectedBackup.value.name, restoreConfirmText.value)
    ElMessage.success('恢复完成，请重启系统。')
    await loadSummary()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '恢复失败'
  } finally {
    backupRestoring.value = false
  }
}

async function openLogDetail(logId: number) {
  selectedLog.value = await getMaintenanceLog(logId)
  logDetailVisible.value = true
}

function formatBytes(value: number | string) {
  const size = Number(value)
  if (!Number.isFinite(size)) return String(value)
  if (size < 1024) return `${size} B`
  if (size < 1024 * 1024) return `${(size / 1024).toFixed(1)} KB`
  return `${(size / 1024 / 1024).toFixed(1)} MB`
}

onMounted(loadSummary)
</script>

<style scoped>
.runtime-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: 12px;
}

.runtime-grid div {
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  padding: 12px;
}

.runtime-grid span {
  display: block;
  color: #64748b;
  font-size: 13px;
}

.runtime-grid strong {
  display: block;
  margin-top: 6px;
  color: #0f172a;
  font-size: 16px;
}

.health-group-title {
  grid-column: 1 / -1;
  border: none !important;
  padding: 6px 0 0 !important;
  color: #334155;
  font-weight: 700;
}

.preview-table {
  margin-top: 12px;
}

.detail-pre {
  max-height: 420px;
  overflow: auto;
  white-space: pre-wrap;
  background: #f8fafc;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  padding: 12px;
}

.maintenance-paths div {
  align-items: flex-start;
}

.maintenance-paths .el-button {
  margin-top: 8px;
}

.diagnose-paths {
  margin-top: 12px;
}

.restore-guide {
  line-height: 1.9;
  margin: 16px 0 0;
  padding-left: 22px;
}

.desktop-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  align-items: center;
}

.desktop-actions div {
  flex: 1 1 280px;
}

.desktop-actions span {
  display: block;
  color: #64748b;
  font-size: 13px;
}

.desktop-actions strong {
  display: block;
  margin-top: 4px;
  color: #0f172a;
}
</style>
