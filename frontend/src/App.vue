<template>
  <el-config-provider :locale="zhCn">
    <el-container class="layout-shell">
      <el-aside class="layout-sidebar" width="236px">
        <div class="brand-block">
          <span>v5.0-desktop-shell</span>
          <strong>工程进度</strong>
        </div>
        <div class="project-switcher" v-if="projects.length > 0">
          <el-select
            :model-value="currentProjectId ?? undefined"
            placeholder="切换项目"
            size="small"
            filterable
            @change="switchProject"
          >
            <el-option
              v-for="project in projects"
              :key="project.id"
              :label="project.name"
              :value="project.id"
            />
          </el-select>
        </div>
        <el-menu :default-active="activeMenu" class="side-menu" router>
          <div class="menu-group-title">项目</div>
          <el-menu-item index="/">
            <el-icon><HomeFilled /></el-icon>
            <span>工作台</span>
          </el-menu-item>
          <el-menu-item index="/projects">
            <el-icon><Folder /></el-icon>
            <span>项目管理</span>
          </el-menu-item>
          <div class="menu-group-title">进度</div>
          <el-menu-item :index="projectPath('import')" class="menu-primary">
            <el-icon><Upload /></el-icon>
            <span>导入 Excel</span>
          </el-menu-item>
          <el-menu-item :index="projectPath('dashboard')">
            <el-icon><DataBoard /></el-icon>
            <span>进度看板</span>
          </el-menu-item>
          <el-menu-item :index="projectPath('progress-items')">
            <el-icon><List /></el-icon>
            <span>进度明细</span>
          </el-menu-item>
          <div class="menu-group-title">问题闭环</div>
          <el-menu-item :index="projectPath('warnings')">
            <el-icon><WarnTriangleFilled /></el-icon>
            <span>预警记录</span>
          </el-menu-item>
          <el-menu-item :index="projectPath('rectifications')">
            <el-icon><CircleCheck /></el-icon>
            <span>整改闭环</span>
          </el-menu-item>
          <div class="menu-group-title">报表</div>
          <el-menu-item :index="projectPath('reports')">
            <el-icon><Download /></el-icon>
            <span>报表中心</span>
          </el-menu-item>
          <el-menu-item :index="projectPath('report-history')">
            <el-icon><Tickets /></el-icon>
            <span>报表历史</span>
          </el-menu-item>
          <div class="menu-group-title">系统</div>
          <el-menu-item index="/maintenance">
            <el-icon><Tools /></el-icon>
            <span>系统维护</span>
          </el-menu-item>
          <el-menu-item index="/diagnostic">
            <el-icon><Warning /></el-icon>
            <span>问题诊断</span>
          </el-menu-item>
          <el-menu-item index="/help">
            <el-icon><QuestionFilled /></el-icon>
            <span>帮助中心</span>
          </el-menu-item>
          <el-menu-item index="/getting-started">
            <el-icon><Guide /></el-icon>
            <span>新手引导</span>
          </el-menu-item>
          <el-menu-item index="/about">
            <el-icon><InfoFilled /></el-icon>
            <span>关于</span>
          </el-menu-item>
        </el-menu>
      </el-aside>

      <el-container>
        <el-main class="layout-main">
          <ErrorBoundary>
            <router-view />
          </ErrorBoundary>
        </el-main>
      </el-container>
    </el-container>
  </el-config-provider>
</template>

<script setup lang="ts">
import { computed, onMounted, onBeforeUnmount, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import zhCn from 'element-plus/es/locale/lang/zh-cn'
import {
  CircleCheck,
  DataBoard,
  Download,
  Folder,
  Guide,
  HomeFilled,
  InfoFilled,
  List,
  QuestionFilled,
  Tickets,
  Tools,
  Upload,
  Warning,
  WarnTriangleFilled,
} from '@element-plus/icons-vue'

import ErrorBoundary from './components/common/ErrorBoundary.vue'
import { listProjects } from './api/projects'
import type { Project } from './types/project'

const route = useRoute()
const router = useRouter()
const projects = ref<Project[]>([])

const routeProjectId = computed(() => {
  const id = Number(route.params.id)
  return Number.isFinite(id) && id > 0 ? id : null
})

const storedProjectId = computed(() => {
  const id = Number(localStorage.getItem('currentProjectId'))
  return Number.isFinite(id) && id > 0 ? id : null
})

const currentProjectId = computed(() => routeProjectId.value ?? storedProjectId.value)

const settingsPath = computed(() => (currentProjectId.value ? `/projects/${currentProjectId.value}/settings` : '/projects'))

const activeMenu = computed(() => {
  const path = route.path
  if (path === '/' || path === '/health') return '/'
  if (path.includes('/import')) return projectPath('import')
  if (path.includes('/dashboard')) return projectPath('dashboard')
  if (path.includes('/progress-items')) return projectPath('progress-items')
  if (path.includes('/warnings')) return projectPath('warnings')
  if (path.includes('/rectifications')) return projectPath('rectifications')
  if (path.includes('/reports/history')) return projectPath('report-history')
  if (path.includes('/reports')) return projectPath('reports')
  if (path.startsWith('/maintenance')) return '/maintenance'
  if (path.startsWith('/diagnostic')) return '/diagnostic'
  if (path.startsWith('/help')) return '/help'
  if (path.startsWith('/getting-started')) return '/getting-started'
  if (path.startsWith('/about')) return '/about'
  if (path.startsWith('/templates')) return '/templates'
  if (path.includes('/settings') || path.includes('/calculation-profiles') || path.includes('/baseline-plans')) return settingsPath.value
  if (path.startsWith('/projects')) return '/projects'
  return '/'
})

function projectPath(module: string) {
  if (module === 'report-history') {
    return currentProjectId.value ? `/projects/${currentProjectId.value}/reports/history` : '/'
  }
  return currentProjectId.value ? `/projects/${currentProjectId.value}/${module}` : '/'
}

function detectCurrentModule(): string | null {
  const path = route.path
  if (path.includes('/import')) return 'import'
  if (path.includes('/dashboard')) return 'dashboard'
  if (path.includes('/progress-items')) return 'progress-items'
  if (path.includes('/warnings')) return 'warnings'
  if (path.includes('/rectifications')) return 'rectifications'
  if (path.includes('/reports/history')) return 'reports/history'
  if (path.includes('/reports')) return 'reports'
  if (path.includes('/settings')) return 'settings'
  if (path.includes('/calculation-profiles')) return 'calculation-profiles'
  if (path.includes('/baseline-plans')) return 'baseline-plans'
  return null
}

function switchProject(projectId: number) {
  if (!projectId || projectId === currentProjectId.value) return
  localStorage.setItem('currentProjectId', String(projectId))
  const module = detectCurrentModule()
  const target = module ? `/projects/${projectId}/${module}` : `/projects/${projectId}`
  router.push(target)
}

async function loadProjectList() {
  try {
    projects.value = await listProjects(false)
  } catch {
    projects.value = []
  }
}

function handleProjectNotFound() {
  if (route.path.startsWith('/projects/')) {
    router.replace('/projects')
  }
}

onMounted(() => {
  window.addEventListener('project-not-found', handleProjectNotFound as EventListener)
  loadProjectList()
})

onBeforeUnmount(() => {
  window.removeEventListener('project-not-found', handleProjectNotFound as EventListener)
})
</script>

<style scoped>
.project-switcher {
  padding: 8px 14px 12px;
  border-bottom: 1px solid #e2e8f0;
}

.menu-group-title {
  padding: 14px 18px 6px;
  color: #94a3b8;
  font-size: 12px;
  font-weight: 700;
}

.side-menu :deep(.el-menu-item) .el-icon {
  margin-right: 10px;
  font-size: 16px;
}

@media print {
  .layout-sidebar {
    display: none !important;
  }

  .layout-main {
    padding: 0 !important;
    background: #ffffff !important;
  }
}
</style>
