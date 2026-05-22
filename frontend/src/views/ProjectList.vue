<template>
  <main class="page-shell">
    <section class="page-heading">
      <div>
        <p class="eyebrow">projects</p>
        <h1>项目列表</h1>
      </div>
      <div class="actions-row">
        <el-segmented v-model="projectFilter" :options="filterOptions" @change="loadProjects" />
        <el-button @click="createDemo">创建示例项目</el-button>
        <el-button type="primary" @click="router.push('/projects/new')">新建项目</el-button>
        <el-button @click="router.push('/getting-started')">新手引导</el-button>
      </div>
    </section>

    <el-alert v-if="errorMessage" :title="errorMessage" type="error" show-icon :closable="false" />
    <el-alert v-if="route.query.project_missing" title="原项目不存在或已被清理，已返回项目列表。请重新选择项目。" type="warning" show-icon :closable="false" />

    <section class="table-surface">
      <el-table v-loading="loading" :data="filteredProjects" empty-text="当前还没有项目，请先创建项目或使用示例项目体验系统。">
        <el-table-column prop="name" label="项目名称" min-width="180">
          <template #default="{ row }">
            <span>{{ row.name }}</span>
            <el-tag v-if="row.is_archived" class="status-tag" size="small" type="info">已归档</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="project_type" label="项目类型" min-width="120" />
        <el-table-column prop="owner_unit" label="建设单位" min-width="150" />
        <el-table-column prop="construction_unit" label="施工单位" min-width="150" />
        <el-table-column label="计划完成" width="120">
          <template #default="{ row }">{{ formatDate(row.planned_finish_date) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="380" fixed="right">
          <template #default="{ row }">
            <el-button text type="primary" @click="router.push(`/projects/${row.id}`)">详情</el-button>
            <el-button text type="primary" @click="router.push(`/projects/${row.id}/dashboard`)">看板</el-button>
            <el-button text @click="router.push(`/projects/${row.id}/settings`)">编辑</el-button>
            <el-button v-if="!row.is_archived" text type="warning" @click="archive(row.id)">归档</el-button>
            <el-button v-else text type="success" @click="restore(row.id)">恢复</el-button>
            <el-button text type="danger" @click="openDeleteDialog(row)">删除项目</el-button>
          </template>
        </el-table-column>
      </el-table>
    </section>

    <el-dialog v-model="deleteDialogVisible" title="删除项目" width="560px" destroy-on-close>
      <div v-if="deleteTarget" class="delete-confirm">
        <p>你正在删除项目：<strong>{{ deleteTarget.name }}</strong></p>
        <p>此操作会删除该项目下的：</p>
        <ul>
          <li>导入批次</li>
          <li>进度明细</li>
          <li>预警记录</li>
          <li>整改项</li>
          <li>报表历史</li>
          <li>计划基线</li>
          <li>相关配置</li>
        </ul>
        <el-alert title="此操作不可恢复。建议删除前先执行一次备份。" type="warning" show-icon :closable="false" />
        <el-form-item label="请输入“确认删除项目”继续">
          <el-input v-model="deleteConfirmText" placeholder="确认删除项目" />
        </el-form-item>
      </div>
      <template #footer>
        <el-button @click="closeDeleteDialog">取消</el-button>
        <el-button type="danger" :loading="deleting" :disabled="deleteConfirmText !== forceDeleteConfirmText" @click="removeProject">
          确认删除
        </el-button>
      </template>
    </el-dialog>
  </main>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { ElMessage, ElMessageBox } from 'element-plus'

import { archiveProject, createDemoProject, forceDeleteProject, listProjects, restoreProject } from '../api/projects'
import type { Project } from '../types/project'
import { formatDate } from '../utils/format'

const router = useRouter()
const route = useRoute()
const loading = ref(false)
const deleting = ref(false)
const errorMessage = ref('')
const projects = ref<Project[]>([])
const deleteDialogVisible = ref(false)
const deleteTarget = ref<Project | null>(null)
const deleteConfirmText = ref('')
const forceDeleteConfirmText = '确认删除项目'
const projectFilter = ref<'all' | 'active' | 'archived'>('active')
const filterOptions = [
  { label: '全部项目', value: 'all' },
  { label: '正常项目', value: 'active' },
  { label: '已归档项目', value: 'archived' },
]
const filteredProjects = computed(() => {
  if (projectFilter.value === 'active') return projects.value.filter((project) => !project.is_archived)
  if (projectFilter.value === 'archived') return projects.value.filter((project) => project.is_archived)
  return projects.value
})

async function loadProjects() {
  loading.value = true
  errorMessage.value = ''
  try {
    projects.value = await listProjects(projectFilter.value !== 'active')
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '项目列表加载失败'
  } finally {
    loading.value = false
  }
}

async function archive(projectId: number) {
  try {
    await ElMessageBox.confirm('归档不会删除任何数据，但归档项目默认禁止新增导入。是否继续？', '归档项目', {
      confirmButtonText: '确认归档',
      cancelButtonText: '取消',
      type: 'warning',
    })
    await archiveProject(projectId)
    if (localStorage.getItem('currentProjectId') === String(projectId)) {
      localStorage.removeItem('currentProjectId')
    }
    await loadProjects()
  } catch (error) {
    if (error instanceof Error && error.message) errorMessage.value = error.message
  }
}

async function restore(projectId: number) {
  try {
    await restoreProject(projectId)
    await loadProjects()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '项目恢复失败'
  }
}

async function createDemo() {
  errorMessage.value = ''
  try {
    const project = await createDemoProject()
    ElMessage.success('示例项目已创建，请导入 sample_data 中的示例 Excel。')
    localStorage.setItem('currentProjectId', String(project.id))
    router.push(`/projects/${project.id}/import`)
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '示例项目创建失败'
  }
}

function openDeleteDialog(project: Project) {
  errorMessage.value = ''
  deleteTarget.value = project
  deleteConfirmText.value = ''
  deleteDialogVisible.value = true
}

function closeDeleteDialog() {
  deleteDialogVisible.value = false
  deleteTarget.value = null
  deleteConfirmText.value = ''
}

async function removeProject() {
  if (!deleteTarget.value) return
  try {
    deleting.value = true
    const projectId = deleteTarget.value.id
    const result = await forceDeleteProject(projectId, deleteConfirmText.value)
    if (localStorage.getItem('currentProjectId') === String(projectId)) {
      localStorage.removeItem('currentProjectId')
    }
    ElMessage.success(result.message || '项目及关联数据已删除。')
    closeDeleteDialog()
    await router.push('/projects')
    await loadProjects()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '项目删除失败'
  } finally {
    deleting.value = false
  }
}

onMounted(loadProjects)
</script>

<style scoped>
.status-tag {
  margin-left: 8px;
}

.delete-confirm {
  display: grid;
  gap: 12px;
}

.delete-confirm p {
  margin: 0;
}

.delete-confirm ul {
  margin: 0;
  padding-left: 20px;
}
</style>
