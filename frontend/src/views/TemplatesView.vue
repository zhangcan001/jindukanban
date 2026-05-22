<template>
  <main class="page-shell dashboard-shell">
    <section class="page-heading">
      <div>
        <p class="eyebrow">templates</p>
        <h1>模板管理</h1>
      </div>
      <el-button type="primary" :loading="loading" :disabled="loading" @click="loadTemplates">刷新</el-button>
    </section>

    <el-alert v-if="errorMessage" :title="errorMessage" type="error" show-icon :closable="false" />

    <section class="table-surface">
      <div class="section-title">
        <h2>项目模板</h2>
        <span>{{ projectTemplates.length }} 个模板</span>
      </div>
      <el-table v-loading="loading" :data="pagedProjectTemplates" empty-text="暂无项目模板。可通过导入流程保存常用项目结构。">
        <el-table-column prop="name" label="模板名称" min-width="180" fixed show-overflow-tooltip />
        <el-table-column prop="project_type" label="项目类型" width="140" show-overflow-tooltip />
        <el-table-column label="来源" width="100">
          <template #default="{ row }">
            <el-tag :type="row.is_builtin ? 'success' : 'info'">{{ row.is_builtin ? '内置' : '自建' }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="100">
          <template #default="{ row }">
            <el-switch v-model="row.is_active" @change="toggleProjectTemplate(row)" />
          </template>
        </el-table-column>
        <el-table-column prop="description" label="说明" min-width="240" show-overflow-tooltip />
        <el-table-column label="操作" width="260" fixed="right">
          <template #default="{ row }">
            <el-button text type="primary" @click="showProjectTemplate(row)">详情</el-button>
            <el-button text @click="copyTemplate(row.id)">复制</el-button>
            <el-button text @click="renameProjectTemplate(row)">重命名</el-button>
            <el-button text type="danger" :disabled="row.is_builtin" @click="removeProjectTemplate(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
      <el-pagination
        v-if="projectTemplates.length"
        v-model:current-page="projectPage"
        v-model:page-size="projectPageSize"
        class="table-pagination"
        layout="total, sizes, prev, pager, next"
        :total="projectTemplates.length"
        :page-sizes="[20, 50, 100]"
      />
    </section>

    <section class="table-surface">
      <div class="section-title">
        <h2>字段映射模板</h2>
        <span>{{ mappingTemplates.length }} 个模板</span>
      </div>
      <el-table v-loading="loading" :data="pagedMappingTemplates" empty-text="暂无字段映射模板。完成字段确认后可保存模板以便复用。">
        <el-table-column prop="name" label="模板名称" min-width="180" fixed show-overflow-tooltip />
        <el-table-column prop="project_type" label="适用类型" width="140" show-overflow-tooltip />
        <el-table-column label="字段数" width="90">
          <template #default="{ row }">{{ row.fields.length }}</template>
        </el-table-column>
        <el-table-column prop="use_count" label="使用次数" width="100" />
        <el-table-column label="最近使用" min-width="160">
          <template #default="{ row }">{{ row.last_used_at ? new Date(row.last_used_at).toLocaleString() : '-' }}</template>
        </el-table-column>
        <el-table-column label="状态" width="100">
          <template #default="{ row }">
            <el-switch v-model="row.is_active" @change="toggleMappingTemplate(row)" />
          </template>
        </el-table-column>
        <el-table-column label="操作" width="220" fixed="right">
          <template #default="{ row }">
            <el-button text type="primary" @click="showMappingTemplate(row)">详情</el-button>
            <el-button text @click="renameMappingTemplate(row)">重命名</el-button>
            <el-button text type="danger" @click="removeMappingTemplate(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
      <el-pagination
        v-if="mappingTemplates.length"
        v-model:current-page="mappingPage"
        v-model:page-size="mappingPageSize"
        class="table-pagination"
        layout="total, sizes, prev, pager, next"
        :total="mappingTemplates.length"
        :page-sizes="[20, 50, 100]"
      />
    </section>

    <el-dialog v-model="detailVisible" title="模板详情" width="720px">
      <pre class="template-detail">{{ detailText }}</pre>
    </el-dialog>
  </main>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'

import {
  copyProjectTemplate,
  deleteMappingTemplate,
  deleteProjectTemplate,
  listMappingTemplates,
  listProjectTemplates,
  updateMappingTemplate,
  updateProjectTemplate,
} from '../api/templates'
import type { MappingTemplate, ProjectTemplate } from '../types/template'

const loading = ref(false)
const errorMessage = ref('')
const projectTemplates = ref<ProjectTemplate[]>([])
const mappingTemplates = ref<MappingTemplate[]>([])
const projectPage = ref(1)
const projectPageSize = ref(20)
const mappingPage = ref(1)
const mappingPageSize = ref(20)
const selectedDetail = ref<unknown>(null)
const detailVisible = ref(false)
const detailText = computed(() => JSON.stringify(selectedDetail.value, null, 2))
const pagedProjectTemplates = computed(() => projectTemplates.value.slice((projectPage.value - 1) * projectPageSize.value, projectPage.value * projectPageSize.value))
const pagedMappingTemplates = computed(() => mappingTemplates.value.slice((mappingPage.value - 1) * mappingPageSize.value, mappingPage.value * mappingPageSize.value))

async function loadTemplates() {
  loading.value = true
  errorMessage.value = ''
  try {
    const [projects, mappings] = await Promise.all([listProjectTemplates(), listMappingTemplates()])
    projectTemplates.value = projects
    mappingTemplates.value = mappings
    projectPage.value = 1
    mappingPage.value = 1
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '模板列表加载失败'
  } finally {
    loading.value = false
  }
}

function showProjectTemplate(template: ProjectTemplate) {
  selectedDetail.value = template
  detailVisible.value = true
}

function showMappingTemplate(template: MappingTemplate) {
  selectedDetail.value = template
  detailVisible.value = true
}

async function copyTemplate(templateId: number) {
  await copyProjectTemplate(templateId)
  ElMessage.success('已复制项目模板。')
  await loadTemplates()
}

async function toggleProjectTemplate(template: ProjectTemplate) {
  await updateProjectTemplate(template.id, { is_active: template.is_active })
}

async function toggleMappingTemplate(template: MappingTemplate) {
  await updateMappingTemplate(template.id, { is_active: template.is_active })
}

async function renameProjectTemplate(template: ProjectTemplate) {
  const result = await ElMessageBox.prompt('请输入新的模板名称', '重命名项目模板', {
    inputValue: template.name,
    confirmButtonText: '保存',
    cancelButtonText: '取消',
  })
  await updateProjectTemplate(template.id, { name: result.value })
  await loadTemplates()
}

async function renameMappingTemplate(template: MappingTemplate) {
  const result = await ElMessageBox.prompt('请输入新的模板名称', '重命名字段映射模板', {
    inputValue: template.name,
    confirmButtonText: '保存',
    cancelButtonText: '取消',
  })
  await updateMappingTemplate(template.id, { name: result.value })
  await loadTemplates()
}

async function removeProjectTemplate(template: ProjectTemplate) {
  await ElMessageBox.confirm(`确认删除项目模板“${template.name}”？`, '删除模板', {
    confirmButtonText: '删除',
    cancelButtonText: '取消',
    type: 'warning',
  })
  await deleteProjectTemplate(template.id)
  await loadTemplates()
}

async function removeMappingTemplate(template: MappingTemplate) {
  await ElMessageBox.confirm(`确认删除字段映射模板“${template.name}”？`, '删除模板', {
    confirmButtonText: '删除',
    cancelButtonText: '取消',
    type: 'warning',
  })
  await deleteMappingTemplate(template.id)
  await loadTemplates()
}

onMounted(loadTemplates)
</script>

<style scoped>
.template-detail {
  max-height: 520px;
  overflow: auto;
  margin: 0;
  white-space: pre-wrap;
  font-family: Consolas, monospace;
  font-size: 12px;
  line-height: 1.6;
}
</style>
