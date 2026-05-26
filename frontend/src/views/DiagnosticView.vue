<template>
  <main class="page-shell">
    <section class="page-heading">
      <div>
        <p class="eyebrow">diagnostic</p>
        <h1>问题诊断</h1>
        <p class="subtitle">最近 200 条 WARNING / ERROR 日志（进程内缓存，重启清空）</p>
      </div>
      <div class="toolbar">
        <el-button :loading="loading" :disabled="loading" @click="loadAll">刷新</el-button>
        <el-button type="warning" plain :disabled="loading" @click="confirmClear">清空缓存</el-button>
      </div>
    </section>

    <section v-if="systemInfo" class="form-surface system-info">
      <div><span>应用：</span><strong>{{ systemInfo.app_name }}</strong></div>
      <div><span>环境：</span><strong>{{ systemInfo.app_env }}</strong></div>
      <div><span>日志级别：</span><strong>{{ systemInfo.log_level }} / {{ systemInfo.log_format }}</strong></div>
      <div><span>Python：</span><strong>{{ systemInfo.python_version }}</strong></div>
      <div><span>平台：</span><strong>{{ systemInfo.platform }}</strong></div>
      <div><span>PID：</span><strong>{{ systemInfo.pid }}</strong></div>
    </section>

    <section class="form-surface filter-row">
      <el-form-item label="最低级别">
        <el-select v-model="level" @change="loadLogs">
          <el-option label="WARNING+" value="WARNING" />
          <el-option label="ERROR+" value="ERROR" />
          <el-option label="CRITICAL" value="CRITICAL" />
        </el-select>
      </el-form-item>
      <el-form-item label="数量上限">
        <el-select v-model="limit" @change="loadLogs">
          <el-option :value="20" label="20" />
          <el-option :value="50" label="50" />
          <el-option :value="100" label="100" />
          <el-option :value="200" label="200" />
        </el-select>
      </el-form-item>
      <span class="hint">共 {{ entries.length }} 条</span>
    </section>

    <el-empty v-if="!loading && !entries.length" description="缓存为空——目前没有 WARNING 或 ERROR 日志。" />

    <section v-else class="logs">
      <article v-for="(entry, idx) in entries" :key="`${entry.ts}-${idx}`" class="log-card" :class="`level-${entry.level.toLowerCase()}`">
        <header class="log-head">
          <el-tag :type="levelTagType(entry.level)" effect="dark">{{ entry.level }}</el-tag>
          <span class="log-ts">{{ entry.ts }}</span>
          <span class="log-logger">{{ entry.logger }}</span>
          <span v-if="entry.request_id" class="log-rid">rid={{ entry.request_id.slice(0, 8) }}</span>
        </header>
        <p class="log-msg">{{ entry.message }}</p>
        <details v-if="entry.exc_info" class="log-exc">
          <summary>展开 traceback</summary>
          <pre>{{ entry.exc_info }}</pre>
        </details>
        <details v-if="entry.extra && Object.keys(entry.extra).length" class="log-extra">
          <summary>展开 extra ({{ Object.keys(entry.extra).length }})</summary>
          <pre>{{ JSON.stringify(entry.extra, null, 2) }}</pre>
        </details>
      </article>
    </section>
  </main>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'

import { clearDiagnosticLogs, getRecentErrors, getSystemInfo, type DiagnosticLogEntry, type DiagnosticSystemInfo } from '../api/diagnostic'

const entries = ref<DiagnosticLogEntry[]>([])
const systemInfo = ref<DiagnosticSystemInfo | null>(null)
const level = ref('WARNING')
const limit = ref(50)
const loading = ref(false)

async function loadLogs() {
  loading.value = true
  try {
    const result = await getRecentErrors({ level: level.value, limit: limit.value })
    entries.value = result.entries
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : '加载日志失败')
  } finally {
    loading.value = false
  }
}

async function loadSystem() {
  try {
    systemInfo.value = await getSystemInfo()
  } catch {
    systemInfo.value = null
  }
}

async function loadAll() {
  await Promise.all([loadLogs(), loadSystem()])
}

async function confirmClear() {
  try {
    await ElMessageBox.confirm('清空后无法恢复，确定吗？', '清空日志缓存', { type: 'warning' })
  } catch {
    return
  }
  try {
    const result = await clearDiagnosticLogs()
    ElMessage.success(`已清空 ${result.cleared} 条`)
    await loadLogs()
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : '清空失败')
  }
}

function levelTagType(lv: string) {
  if (lv === 'CRITICAL' || lv === 'ERROR') return 'danger'
  if (lv === 'WARNING') return 'warning'
  return 'info'
}

onMounted(loadAll)
</script>

<style scoped>
.subtitle {
  margin-top: 4px;
  color: #64748b;
  font-size: 13px;
}

.system-info {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 10px 18px;
  font-size: 13px;
  color: #475569;
}

.system-info span {
  color: #94a3b8;
  margin-right: 6px;
}

.system-info strong {
  color: #0f172a;
}

.filter-row {
  display: flex;
  align-items: center;
  gap: 18px;
  flex-wrap: wrap;
}

.filter-row .hint {
  color: #94a3b8;
  font-size: 13px;
  margin-left: auto;
}

.logs {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.log-card {
  background: #ffffff;
  border-radius: 14px;
  padding: 14px 18px;
  box-shadow: 0 1px 2px rgba(15, 23, 42, 0.05);
  border-left: 4px solid #cbd5e1;
}

.log-card.level-error,
.log-card.level-critical {
  border-left-color: #dc2626;
  background: #fef2f2;
}

.log-card.level-warning {
  border-left-color: #f59e0b;
  background: #fffbeb;
}

.log-head {
  display: flex;
  align-items: center;
  gap: 12px;
  font-size: 12px;
  color: #64748b;
  margin-bottom: 6px;
  flex-wrap: wrap;
}

.log-ts {
  font-family: ui-monospace, SFMono-Regular, monospace;
}

.log-logger {
  color: #0f172a;
  font-weight: 600;
}

.log-rid {
  color: #94a3b8;
  margin-left: auto;
  font-family: ui-monospace, SFMono-Regular, monospace;
}

.log-msg {
  margin: 0;
  color: #0f172a;
  line-height: 1.6;
  word-break: break-word;
}

.log-exc,
.log-extra {
  margin-top: 8px;
  font-size: 12px;
}

.log-exc pre,
.log-extra pre {
  background: #0f172a;
  color: #e2e8f0;
  padding: 10px 12px;
  border-radius: 8px;
  overflow-x: auto;
  font-size: 12px;
  line-height: 1.5;
}
</style>
