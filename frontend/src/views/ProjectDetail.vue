<template>
  <main class="page-shell">
    <section class="page-heading">
      <div>
        <p class="eyebrow">project detail</p>
        <h1>{{ project?.name ?? '项目详情' }}</h1>
      </div>
      <div class="toolbar">
        <el-button @click="router.push('/projects')">项目列表</el-button>
        <el-button type="primary" @click="router.push(`/projects/${projectId}/settings`)">编辑项目</el-button>
      </div>
    </section>

    <el-alert v-if="errorMessage" :title="errorMessage" type="error" show-icon :closable="false" />
    <el-alert
      v-if="project?.is_archived"
      title="当前项目已归档，仅建议查看历史数据。如需继续导入，请先恢复项目。"
      type="warning"
      show-icon
      :closable="false"
    />

    <section v-if="project" class="detail-grid">
      <div class="detail-item"><span>项目类型</span><strong>{{ project.project_type || '-' }}</strong></div>
      <div class="detail-item"><span>建设单位</span><strong>{{ project.owner_unit || '-' }}</strong></div>
      <div class="detail-item"><span>监理单位</span><strong>{{ project.supervision_unit || '-' }}</strong></div>
      <div class="detail-item"><span>施工单位</span><strong>{{ project.construction_unit || '-' }}</strong></div>
      <div class="detail-item"><span>开始日期</span><strong>{{ formatDate(project.start_date) }}</strong></div>
      <div class="detail-item"><span>计划完成</span><strong>{{ formatDate(project.planned_finish_date) }}</strong></div>
      <div class="detail-item"><span>默认统计口径</span><strong>{{ defaultProfileName }}</strong></div>
      <div class="detail-item"><span>默认计划基线</span><strong>{{ defaultBaselineName }}</strong></div>
    </section>

    <section class="module-links">
      <el-button type="primary" @click="router.push(`/projects/${projectId}/calculation-profiles`)">
        统计口径配置
      </el-button>
      <el-button type="primary" @click="router.push(`/projects/${projectId}/baseline-plans`)">
        计划基线配置
      </el-button>
      <el-button type="primary" @click="router.push(`/projects/${projectId}/dashboard`)">
        进度看板
      </el-button>
      <el-button type="primary" @click="router.push(`/projects/${projectId}/progress-items`)">
        进度明细
      </el-button>
      <el-button type="primary" @click="router.push(`/projects/${projectId}/warnings`)">
        预警中心
      </el-button>
      <el-button type="primary" @click="router.push(`/projects/${projectId}/rectifications`)">
        整改闭环
      </el-button>
      <el-button type="primary" @click="router.push(`/projects/${projectId}/reports`)">
        报表中心
      </el-button>
      <el-button type="primary" :disabled="project?.is_archived" @click="router.push(`/projects/${projectId}/import`)">
        导入 Excel
      </el-button>
    </section>
  </main>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { listBaselinePlans } from '../api/baselinePlans'
import { listCalculationProfiles } from '../api/calculationProfiles'
import { useProjectStore } from '../stores/useProjectStore'
import type { BaselinePlan } from '../types/baselinePlan'
import type { CalculationProfile } from '../types/calculationProfile'
import type { Project } from '../types/project'
import { formatDate } from '../utils/format'

const route = useRoute()
const router = useRouter()
const projectId = Number(route.params.id)
const projectStore = useProjectStore()
const project = ref<Project | null>(null)
const profiles = ref<CalculationProfile[]>([])
const baselines = ref<BaselinePlan[]>([])
const errorMessage = ref('')

const defaultProfileName = computed(() => {
  return profiles.value.find((item) => item.id === project.value?.default_calculation_profile_id)?.name ?? '-'
})

const defaultBaselineName = computed(() => {
  return baselines.value.find((item) => item.id === project.value?.default_baseline_plan_id)?.name ?? '-'
})

async function loadDetail() {
  try {
    const [loadedProject, loadedProfiles, loadedBaselines] = await Promise.all([
      projectStore.loadProject(projectId),
      listCalculationProfiles(projectId),
      listBaselinePlans(projectId),
    ])
    project.value = loadedProject
    profiles.value = loadedProfiles
    baselines.value = loadedBaselines
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '项目详情加载失败'
  }
}

onMounted(loadDetail)
</script>
