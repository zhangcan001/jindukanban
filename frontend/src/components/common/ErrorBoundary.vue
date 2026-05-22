<template>
  <div v-if="hasError" class="error-boundary">
    <el-result icon="warning" :title="title" :sub-title="subTitle">
      <template #extra>
        <el-button type="primary" @click="retry">重试</el-button>
        <el-button @click="goHome">返回工作台</el-button>
      </template>
    </el-result>
  </div>
  <slot v-else />
</template>

<script setup lang="ts">
import { onErrorCaptured, ref } from 'vue'
import { useRouter } from 'vue-router'

import { reportError } from '../../utils/errorHandler'

interface Props {
  /** 覆盖默认标题，比如"看板加载失败" */
  fallbackTitle?: string
}

const props = withDefaults(defineProps<Props>(), {
  fallbackTitle: '此区域出错了',
})
const emit = defineEmits<{ retry: [] }>()

const hasError = ref(false)
const errorMessage = ref('')
const router = useRouter()

const title = props.fallbackTitle
const subTitle = ref('')

onErrorCaptured((err, _instance, info) => {
  hasError.value = true
  errorMessage.value = err instanceof Error ? err.message : String(err)
  subTitle.value = errorMessage.value
  reportError(err, `boundary:${info}`)
  // 返回 false 阻止错误继续向上冒泡——boundary 的本意就是把错误吞在这一层
  return false
})

function retry(): void {
  hasError.value = false
  errorMessage.value = ''
  subTitle.value = ''
  emit('retry')
}

function goHome(): void {
  hasError.value = false
  router.push('/').catch(() => undefined)
}
</script>

<style scoped>
.error-boundary {
  padding: 24px;
  min-height: 320px;
  display: flex;
  align-items: center;
  justify-content: center;
}
</style>
