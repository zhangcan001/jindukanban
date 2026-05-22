<template>
  <main class="page-shell">
    <section class="page-heading">
      <div>
        <p class="eyebrow">project</p>
        <h1>{{ isEdit ? '编辑项目' : '新建项目' }}</h1>
      </div>
      <el-button @click="router.push('/projects')">返回列表</el-button>
    </section>

    <el-alert v-if="errorMessage" :title="errorMessage" type="error" show-icon :closable="false" />

    <section class="form-surface">
      <el-form label-position="top" :model="form">
        <div class="form-grid">
          <el-form-item v-if="!isEdit" label="项目模板">
            <el-select v-model="form.template_id" clearable placeholder="不使用模板">
              <el-option label="不使用模板" :value="null" />
              <el-option
                v-for="template in activeProjectTemplates"
                :key="template.id"
                :label="template.name"
                :value="template.id"
              />
            </el-select>
          </el-form-item>
          <el-form-item label="项目名称" required>
            <el-input v-model="form.name" placeholder="例如：机电安装工程" />
          </el-form-item>
          <el-form-item label="项目类型">
            <el-input v-model="form.project_type" placeholder="例如：房建 / 市政 / 机电" />
          </el-form-item>
          <el-form-item label="建设单位">
            <el-input v-model="form.owner_unit" />
          </el-form-item>
          <el-form-item label="监理单位">
            <el-input v-model="form.supervision_unit" />
          </el-form-item>
          <el-form-item label="施工单位">
            <el-input v-model="form.construction_unit" />
          </el-form-item>
          <el-form-item label="开始日期">
            <el-date-picker v-model="form.start_date" value-format="YYYY-MM-DD" type="date" />
          </el-form-item>
          <el-form-item label="计划完成日期">
            <el-date-picker v-model="form.planned_finish_date" value-format="YYYY-MM-DD" type="date" />
          </el-form-item>
          <el-form-item label="默认统计口径">
            <el-select v-model="form.default_calculation_method">
              <el-option label="自动推荐" value="auto" />
              <el-option label="权重统计" value="weighted_percent" />
              <el-option label="产值加权" value="value_weighted_percent" />
              <el-option label="工程量统计" value="quantity_percent" />
              <el-option label="百分比平均" value="percent_average" />
              <el-option label="任务平均" value="task_average" />
            </el-select>
          </el-form-item>
        </div>

        <el-form-item label="备注">
          <el-input v-model="form.remark" type="textarea" :rows="4" />
        </el-form-item>

        <div class="actions-row">
          <el-button type="primary" :loading="saving" @click="saveProject">保存</el-button>
          <el-button @click="router.back()">取消</el-button>
        </div>
      </el-form>
    </section>
  </main>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { createProject, getProject, updateProject } from '../api/projects'
import { listProjectTemplates } from '../api/templates'
import type { ProjectPayload } from '../types/project'
import type { ProjectTemplate } from '../types/template'

const route = useRoute()
const router = useRouter()
const projectId = computed(() => Number(route.params.id))
const isEdit = computed(() => Number.isFinite(projectId.value))
const saving = ref(false)
const errorMessage = ref('')
const projectTemplates = ref<ProjectTemplate[]>([])
const activeProjectTemplates = computed(() => projectTemplates.value.filter((template) => template.is_active))

const form = reactive<ProjectPayload>({
  name: '',
  project_type: '',
  owner_unit: '',
  supervision_unit: '',
  construction_unit: '',
  start_date: null,
  planned_finish_date: null,
  template_id: null,
  default_calculation_profile_id: null,
  default_calculation_method: 'auto',
  default_baseline_plan_id: null,
  dashboard_config: null,
  report_config: null,
  remark: '',
  created_by: '',
  updated_by: '',
})

async function loadProject() {
  if (!isEdit.value) {
    projectTemplates.value = await listProjectTemplates()
    return
  }
  const project = await getProject(projectId.value)
  Object.assign(form, project)
}

async function saveProject() {
  if (!form.name.trim()) {
    errorMessage.value = '请填写项目名称'
    return
  }

  saving.value = true
  errorMessage.value = ''
  try {
    const saved = isEdit.value
      ? await updateProject(projectId.value, form)
      : await createProject(form)
    router.push(`/projects/${saved.id}`)
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '项目保存失败'
  } finally {
    saving.value = false
  }
}

onMounted(loadProject)
</script>
