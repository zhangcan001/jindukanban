<template>
  <main class="page-shell">
    <section class="page-heading">
      <div>
        <p class="eyebrow">baseline plan</p>
        <h1>计划基线配置</h1>
      </div>
      <el-button @click="router.push(`/projects/${projectId}`)">返回项目</el-button>
    </section>

    <el-alert v-if="errorMessage" :title="errorMessage" type="error" show-icon :closable="false" />

    <section class="form-surface">
      <el-form label-position="top" :model="form">
        <div class="form-grid">
          <el-form-item label="基线名称" required>
            <el-input v-model="form.name" />
          </el-form-item>
          <el-form-item label="基线类型">
            <el-select v-model="form.plan_type">
              <el-option label="原始计划" value="original" />
              <el-option label="当前计划" value="current" />
              <el-option label="调整计划" value="adjusted" />
              <el-option label="施工单位上报计划" value="reported" />
            </el-select>
          </el-form-item>
          <el-form-item label="生效日期">
            <el-date-picker v-model="form.baseline_date" type="date" value-format="YYYY-MM-DD" clearable />
          </el-form-item>
        </div>
        <el-form-item label="说明">
          <el-input v-model="form.description" type="textarea" :rows="3" />
        </el-form-item>
        <div class="switch-row">
          <el-checkbox v-model="form.is_default">设为默认</el-checkbox>
          <el-checkbox v-model="form.is_active">启用</el-checkbox>
        </div>
        <div class="actions-row">
          <el-button type="primary" :loading="saving" @click="saveBaseline">
            {{ editingId ? '保存修改' : '新增计划基线' }}
          </el-button>
          <el-button v-if="editingId" @click="resetForm">取消编辑</el-button>
        </div>
      </el-form>
    </section>

    <section class="table-surface">
      <el-table v-loading="loading" :data="baselines" empty-text="暂无计划基线">
        <el-table-column prop="name" label="名称" min-width="180">
          <template #default="{ row }">
            <div class="baseline-name-cell">
              <strong>{{ row.name }}</strong>
              <el-tag v-if="row.is_default" type="success" effect="dark">当前默认</el-tag>
            </div>
          </template>
        </el-table-column>
        <el-table-column prop="plan_type" label="类型" min-width="120" />
        <el-table-column prop="baseline_date" label="生效日期" min-width="120">
          <template #default="{ row }">{{ row.baseline_date || '-' }}</template>
        </el-table-column>
        <el-table-column prop="description" label="说明" min-width="180" />
        <el-table-column label="绑定批次" width="110">
          <template #default="{ row }">
            <el-button link type="primary" @click="openBoundBatches(row)">{{ row.bound_batch_count }} 个</el-button>
          </template>
        </el-table-column>
        <el-table-column label="最近绑定日期" width="130">
          <template #default="{ row }">{{ row.latest_bound_batch_date || '-' }}</template>
        </el-table-column>
        <el-table-column label="默认" width="90">
          <template #default="{ row }">
            <el-tag v-if="row.is_default" type="success">默认</el-tag>
            <span v-else>-</span>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="90">
          <template #default="{ row }">
            <el-tag :type="row.is_active ? 'success' : 'info'">{{ row.is_active ? '启用' : '停用' }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="260" fixed="right">
          <template #default="{ row }">
            <el-button text type="primary" @click="editBaseline(row)">编辑</el-button>
            <el-button text @click="setDefault(row)">设为默认</el-button>
            <el-button text type="warning" @click="toggleActive(row)">{{ row.is_active ? '停用' : '启用' }}</el-button>
          </template>
        </el-table-column>
      </el-table>
    </section>

    <el-drawer v-model="boundDrawerVisible" title="绑定导入批次" size="520px">
      <el-empty v-if="!boundBatches.length" description="当前计划基线暂无绑定导入批次。" />
      <el-table v-else :data="boundBatches">
        <el-table-column prop="id" label="批次" width="80">
          <template #default="{ row }">#{{ row.id }}</template>
        </el-table-column>
        <el-table-column prop="file_name" label="文件名" min-width="180" />
        <el-table-column prop="sheet_name" label="Sheet" min-width="120" />
        <el-table-column prop="data_date" label="数据日期" width="120" />
        <el-table-column prop="baseline_plan_name" label="计划基线" min-width="160" />
        <el-table-column prop="status" label="状态" width="100" />
      </el-table>
    </el-drawer>
  </main>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { ElMessageBox } from 'element-plus'
import { useRoute, useRouter } from 'vue-router'

import {
  createBaselinePlan,
  listBaselineBoundBatches,
  listBaselinePlans,
  updateBaselinePlan,
} from '../api/baselinePlans'
import type { BaselineBoundBatch, BaselinePlan, BaselinePlanPayload } from '../types/baselinePlan'

const route = useRoute()
const router = useRouter()
const projectId = Number(route.params.id)
const baselines = ref<BaselinePlan[]>([])
const loading = ref(false)
const saving = ref(false)
const editingId = ref<number | null>(null)
const errorMessage = ref('')
const boundDrawerVisible = ref(false)
const boundBatches = ref<BaselineBoundBatch[]>([])

const form = reactive<BaselinePlanPayload>({
  name: '',
  plan_type: 'current',
  description: '',
  baseline_date: null,
  is_default: false,
  is_active: true,
})

function resetForm() {
  editingId.value = null
  Object.assign(form, {
    name: '',
    plan_type: 'current',
    description: '',
    baseline_date: null,
    is_default: false,
    is_active: true,
  })
}

async function loadBaselines() {
  loading.value = true
  try {
    baselines.value = await listBaselinePlans(projectId)
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '计划基线加载失败'
  } finally {
    loading.value = false
  }
}

function editBaseline(baseline: BaselinePlan) {
  editingId.value = baseline.id
  Object.assign(form, baseline)
}

async function saveBaseline() {
  if (!form.name.trim()) {
    errorMessage.value = '请填写计划基线名称'
    return
  }
  saving.value = true
  try {
    if (editingId.value) {
      await updateBaselinePlan(projectId, editingId.value, form)
    } else {
      await createBaselinePlan(projectId, form)
    }
    resetForm()
    await loadBaselines()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '计划基线保存失败'
  } finally {
    saving.value = false
  }
}

async function setDefault(baseline: BaselinePlan) {
  await updateBaselinePlan(projectId, baseline.id, { is_default: true })
  await loadBaselines()
}

async function toggleActive(baseline: BaselinePlan) {
  if (baseline.is_active && baseline.bound_batch_count > 0) {
    await ElMessageBox.confirm(
      `该基线已绑定 ${baseline.bound_batch_count} 个批次，停用后历史批次仍保留该基线记录。是否继续？`,
      '停用计划基线',
      { type: 'warning' },
    )
  }
  await updateBaselinePlan(projectId, baseline.id, { is_active: !baseline.is_active })
  await loadBaselines()
}

async function openBoundBatches(baseline: BaselinePlan) {
  boundBatches.value = await listBaselineBoundBatches(projectId, baseline.id)
  boundDrawerVisible.value = true
}

onMounted(loadBaselines)
</script>

<style scoped>
.baseline-name-cell {
  display: flex;
  align-items: center;
  gap: 8px;
}
</style>
