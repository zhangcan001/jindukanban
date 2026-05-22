<template>
  <main class="page-shell">
    <section class="page-heading">
      <div>
        <p class="eyebrow">calculation profile</p>
        <h1>统计口径配置</h1>
      </div>
      <el-button @click="router.push(`/projects/${projectId}`)">返回项目</el-button>
    </section>

    <el-alert v-if="errorMessage" :title="errorMessage" type="error" show-icon :closable="false" />

    <section class="form-surface">
      <el-form label-position="top" :model="form">
        <div class="form-grid">
          <el-form-item label="名称" required>
            <el-input v-model="form.name" />
          </el-form-item>
          <el-form-item label="总体进度算法">
            <el-select v-model="form.overall_algorithm">
              <el-option label="任务平均完成率" value="avg_percent" />
              <el-option label="按工程量完成率" value="quantity_percent" />
              <el-option label="按权重加权" value="weighted_percent" />
              <el-option label="按产值加权" value="value_weighted_percent" />
              <el-option label="使用 Excel 上报完成率" value="reported_percent" />
            </el-select>
          </el-form-item>
          <el-form-item label="分组算法">
            <el-select v-model="form.group_algorithm">
              <el-option label="任务平均完成率" value="avg_percent" />
              <el-option label="按工程量完成率" value="quantity_percent" />
              <el-option label="按权重加权" value="weighted_percent" />
              <el-option label="按产值加权" value="value_weighted_percent" />
              <el-option label="使用 Excel 上报完成率" value="reported_percent" />
            </el-select>
          </el-form-item>
          <el-form-item label="完成率来源">
            <el-select v-model="form.percent_source">
              <el-option label="优先使用 Excel 完成率" value="provided_percent_first" />
              <el-option label="优先按工程量计算" value="quantity_calculated_first" />
              <el-option label="只使用用户映射字段" value="manual_only" />
            </el-select>
          </el-form-item>
          <el-form-item label="权重字段">
            <el-input v-model="form.weight_field" :disabled="!form.use_weight" />
          </el-form-item>
          <el-form-item label="产值字段">
            <el-input v-model="form.value_field" :disabled="!form.use_value_amount" />
          </el-form-item>
        </div>

        <div class="switch-row">
          <el-checkbox v-model="form.use_weight">启用权重</el-checkbox>
          <el-checkbox v-model="form.use_value_amount">启用产值</el-checkbox>
          <el-checkbox v-model="form.allow_mixed_unit_sum">允许混合单位汇总</el-checkbox>
          <el-checkbox v-model="form.enable_date_plan_calculation">启用日期计划计算</el-checkbox>
          <el-checkbox v-model="form.is_default">设为默认</el-checkbox>
        </div>

        <el-divider content-position="left">滞后阈值（百分点，单位：%）</el-divider>
        <p class="hint-text">
          偏差 = 实际进度 − 计划进度。判定顺序：偏差 ≥ 超前阈值 → 超前；≥ 正常阈值 → 正常；
          ≥ 轻微阈值 → 轻微滞后；≥ 明显阈值 → 明显滞后；&lt; 明显阈值 → 严重滞后。建议保持 4 个值依次递减。
        </p>
        <div class="form-grid">
          <el-form-item label="超前阈值（≥ 该值视为超前）">
            <el-input-number v-model="form.delay_threshold_ahead" :step="1" :precision="1" controls-position="right" />
          </el-form-item>
          <el-form-item label="正常阈值（≥ 该值视为正常）">
            <el-input-number v-model="form.delay_threshold_normal" :step="1" :precision="1" controls-position="right" />
          </el-form-item>
          <el-form-item label="轻微滞后阈值（≥ 该值视为轻微滞后）">
            <el-input-number v-model="form.delay_threshold_minor" :step="1" :precision="1" controls-position="right" />
          </el-form-item>
          <el-form-item label="明显滞后阈值（≥ 该值视为明显滞后；低于此值为严重滞后）">
            <el-input-number v-model="form.delay_threshold_major" :step="1" :precision="1" controls-position="right" />
          </el-form-item>
        </div>
        <el-form-item label="按专业 / 楼层 / 楼栋的阈值覆盖（JSON，可选）">
          <el-input
            v-model="overridesText"
            type="textarea"
            :rows="4"
            placeholder='例：{"discipline": {"机电": {"normal": -3, "minor": -8, "major": -15}}}'
          />
        </el-form-item>
        <el-alert v-if="overridesError" :title="overridesError" type="warning" show-icon :closable="false" />

        <el-alert
          v-if="thresholdOrderWarning"
          :title="thresholdOrderWarning"
          type="warning"
          show-icon
          :closable="false"
        />

        <div class="actions-row">
          <el-button type="primary" :loading="saving" @click="saveProfile">
            {{ editingId ? '保存修改' : '新增统计口径' }}
          </el-button>
          <el-button v-if="editingId" @click="resetForm">取消编辑</el-button>
        </div>
      </el-form>
    </section>

    <section class="table-surface">
      <el-table v-loading="loading" :data="profiles" empty-text="暂无统计口径">
        <el-table-column prop="name" label="名称" min-width="160" />
        <el-table-column prop="overall_algorithm" label="总体算法" min-width="150" />
        <el-table-column prop="percent_source" label="完成率来源" min-width="180" />
        <el-table-column label="默认" width="90">
          <template #default="{ row }">
            <el-tag v-if="row.is_default" type="success">默认</el-tag>
            <span v-else>-</span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="260" fixed="right">
          <template #default="{ row }">
            <el-button text type="primary" @click="editProfile(row)">编辑</el-button>
            <el-button text @click="setDefault(row)">设为默认</el-button>
            <el-button text type="danger" @click="removeProfile(row.id)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </section>
  </main>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import {
  createCalculationProfile,
  deleteCalculationProfile,
  listCalculationProfiles,
  updateCalculationProfile,
} from '../api/calculationProfiles'
import type { CalculationProfile, CalculationProfilePayload } from '../types/calculationProfile'

const route = useRoute()
const router = useRouter()
const projectId = Number(route.params.id)
const profiles = ref<CalculationProfile[]>([])
const loading = ref(false)
const saving = ref(false)
const editingId = ref<number | null>(null)
const errorMessage = ref('')
const overridesText = ref('')
const overridesError = ref('')

const form = reactive<CalculationProfilePayload>({
  name: '',
  overall_algorithm: 'avg_percent',
  group_algorithm: 'avg_percent',
  percent_source: 'provided_percent_first',
  use_weight: false,
  weight_field: '',
  use_value_amount: false,
  value_field: '',
  allow_mixed_unit_sum: false,
  enable_date_plan_calculation: true,
  is_default: false,
  delay_threshold_ahead: 5,
  delay_threshold_normal: -5,
  delay_threshold_minor: -10,
  delay_threshold_major: -20,
  delay_threshold_overrides: null,
})

const thresholdOrderWarning = computed(() => {
  const a = form.delay_threshold_ahead
  const n = form.delay_threshold_normal
  const mi = form.delay_threshold_minor
  const ma = form.delay_threshold_major
  if (!(a > n && n > mi && mi > ma)) {
    return '阈值未严格递减（ahead > normal > minor > major），保存仍可，但可能导致状态判定不符合预期。'
  }
  return ''
})

function resetForm() {
  editingId.value = null
  overridesText.value = ''
  overridesError.value = ''
  Object.assign(form, {
    name: '',
    overall_algorithm: 'avg_percent',
    group_algorithm: 'avg_percent',
    percent_source: 'provided_percent_first',
    use_weight: false,
    weight_field: '',
    use_value_amount: false,
    value_field: '',
    allow_mixed_unit_sum: false,
    enable_date_plan_calculation: true,
    is_default: false,
    delay_threshold_ahead: 5,
    delay_threshold_normal: -5,
    delay_threshold_minor: -10,
    delay_threshold_major: -20,
    delay_threshold_overrides: null,
  })
}

async function loadProfiles() {
  loading.value = true
  try {
    profiles.value = await listCalculationProfiles(projectId)
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '统计口径加载失败'
  } finally {
    loading.value = false
  }
}

function editProfile(profile: CalculationProfile) {
  editingId.value = profile.id
  Object.assign(form, profile)
  overridesText.value = profile.delay_threshold_overrides ?? ''
  overridesError.value = ''
}

async function saveProfile() {
  if (!form.name.trim()) {
    errorMessage.value = '请填写统计口径名称'
    return
  }
  const trimmed = overridesText.value.trim()
  if (trimmed) {
    try {
      const parsed = JSON.parse(trimmed)
      if (typeof parsed !== 'object' || parsed === null || Array.isArray(parsed)) {
        throw new Error('阈值覆盖必须是 JSON 对象')
      }
      overridesError.value = ''
      form.delay_threshold_overrides = trimmed
    } catch (err) {
      overridesError.value = `阈值覆盖 JSON 不合法：${err instanceof Error ? err.message : String(err)}`
      return
    }
  } else {
    overridesError.value = ''
    form.delay_threshold_overrides = null
  }
  saving.value = true
  try {
    if (editingId.value) {
      await updateCalculationProfile(projectId, editingId.value, form)
    } else {
      await createCalculationProfile(projectId, form)
    }
    resetForm()
    await loadProfiles()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '统计口径保存失败'
  } finally {
    saving.value = false
  }
}

async function setDefault(profile: CalculationProfile) {
  await updateCalculationProfile(projectId, profile.id, { is_default: true })
  await loadProfiles()
}

async function removeProfile(profileId: number) {
  await deleteCalculationProfile(projectId, profileId)
  await loadProfiles()
}

onMounted(loadProfiles)
</script>

<style scoped>
.hint-text {
  font-size: 12px;
  color: var(--el-text-color-secondary);
  margin: -6px 0 12px;
  line-height: 1.6;
}
</style>

