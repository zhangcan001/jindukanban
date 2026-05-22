<template>
  <main class="page-shell dashboard-shell">
    <section class="page-heading">
      <div>
        <p class="eyebrow">about</p>
        <h1>版本信息</h1>
      </div>
      <div class="toolbar">
        <el-button @click="router.push('/help')">帮助中心</el-button>
        <el-button type="primary" @click="router.push('/maintenance')">系统维护</el-button>
      </div>
    </section>

    <el-alert v-if="errorMessage" :title="errorMessage" type="error" show-icon :closable="false" />

    <section class="table-surface" v-loading="loading">
      <div class="section-title">
        <div>
          <h2>本地运行信息</h2>
          <p>当前系统的版本、运行模式和本地数据目录。</p>
        </div>
        <el-tag>{{ about?.run_mode || '本地运行' }}</el-tag>
      </div>
      <div class="runtime-grid">
        <div><span>当前版本</span><strong>{{ about?.app_version ?? '-' }}</strong></div>
        <div><span>本地运行模式</span><strong>{{ about?.run_mode ?? '-' }}</strong></div>
        <div><span>运行模式标识</span><strong>{{ about?.runtime_mode ?? '-' }}</strong></div>
        <div><span>数据库路径</span><code>{{ about?.database_path ?? '-' }}</code></div>
        <div><span>数据目录</span><code>{{ about?.data_dir ?? '-' }}</code></div>
        <div><span>上传目录</span><code>{{ about?.upload_dir ?? '-' }}</code></div>
        <div><span>导出目录</span><code>{{ about?.export_dir ?? '-' }}</code></div>
        <div><span>备份目录</span><code>{{ about?.backup_dir ?? '-' }}</code></div>
      </div>
    </section>

    <section class="content-grid">
      <div class="table-surface">
        <div class="section-title">
          <h2>当前核心能力</h2>
          <span>{{ about?.core_capabilities.length ?? 0 }} 项</span>
        </div>
        <ul class="plain-list">
          <li v-for="item in about?.core_capabilities ?? []" :key="item">{{ item }}</li>
        </ul>
      </div>
      <div class="table-surface">
        <div class="section-title">
          <h2>当前限制</h2>
          <span>本地版</span>
        </div>
        <ul class="plain-list">
          <li v-for="item in about?.current_limits ?? []" :key="item">{{ item }}</li>
        </ul>
      </div>
    </section>

    <section class="table-surface">
      <div class="section-title">
        <h2>快速操作入口</h2>
        <span>常用页面</span>
      </div>
      <div class="quick-actions">
        <el-button v-for="item in about?.quick_actions ?? []" :key="item.label" @click="router.push(item.path)">
          {{ item.label }}
        </el-button>
        <el-button @click="router.push('/projects')">选择项目</el-button>
      </div>
    </section>
  </main>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { getAboutRuntimeInfo } from '../api/maintenance'
import type { AboutRuntimeInfo } from '../types/maintenance'

const router = useRouter()
const about = ref<AboutRuntimeInfo | null>(null)
const loading = ref(false)
const errorMessage = ref('')

async function loadAbout() {
  loading.value = true
  errorMessage.value = ''
  try {
    about.value = await getAboutRuntimeInfo()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '版本信息加载失败。'
  } finally {
    loading.value = false
  }
}

onMounted(loadAbout)
</script>

<style scoped>
.runtime-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
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

.runtime-grid strong,
.runtime-grid code {
  display: block;
  margin-top: 6px;
  color: #0f172a;
  word-break: break-all;
}

.content-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
  gap: 16px;
}

.plain-list {
  margin: 0;
  padding-left: 20px;
  line-height: 2;
}

.quick-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
}
</style>
