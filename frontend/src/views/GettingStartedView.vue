<template>
  <main class="page-shell dashboard-shell help-page">
    <section class="page-heading">
      <div>
        <p class="eyebrow">getting started</p>
        <h1>新手引导</h1>
      </div>
      <div class="toolbar">
        <el-button @click="router.push('/projects/new')">去创建项目</el-button>
        <el-button type="primary" @click="router.push('/help')">去帮助中心</el-button>
      </div>
    </section>

    <section class="getting-started-grid">
      <article v-for="step in steps" :key="step.title" class="table-surface step-card">
        <div class="section-title">
          <h2>{{ step.title }}</h2>
          <span>{{ step.tag }}</span>
        </div>
        <p>{{ step.body }}</p>
        <div class="toolbar">
          <el-button v-for="action in step.actions" :key="action.label" :type="action.primary ? 'primary' : 'default'" @click="router.push(action.path)">
            {{ action.label }}
          </el-button>
        </div>
      </article>
    </section>
  </main>
</template>

<script setup lang="ts">
import { useRouter } from 'vue-router'

const router = useRouter()

type GuideAction = {
  label: string
  path: string
  primary?: boolean
}

type GuideStep = {
  title: string
  tag: string
  body: string
  actions: GuideAction[]
}

const steps: GuideStep[] = [
  { title: '第一步：创建项目', tag: '项目', body: '先建立一个工程项目，再进入导入和分析流程。', actions: [{ label: '去创建项目', path: '/projects/new', primary: true }] },
  { title: '第二步：导入 Excel', tag: '导入', body: '上传单 Sheet 或多 Sheet 进度表，确认表头后继续导入。', actions: [{ label: '去导入 Excel', path: '/projects', primary: true }] },
  { title: '第三步：查看 Dashboard', tag: '看板', body: '查看总体进度、计划偏差、专业统计和楼层统计。', actions: [{ label: '去 Dashboard', path: '/' }] },
  { title: '第四步：运行预警', tag: '预警', body: '查看滞后项和风险记录，便于周会前集中筛查。', actions: [{ label: '去预警记录', path: '/projects' }] },
  { title: '第五步：生成整改项', tag: '整改', body: '从预警或滞后项生成整改闭环记录。', actions: [{ label: '去整改闭环', path: '/projects' }] },
  { title: '第六步：导出报表', tag: '报表', body: '导出 Word、PDF、Excel 报表，形成汇报材料。', actions: [{ label: '去报表中心', path: '/projects' }] },
  { title: '第七步：备份数据', tag: '维护', body: '定期备份数据库、上传文件和导出文件。', actions: [{ label: '去系统维护', path: '/maintenance' }] },
]
</script>

<style scoped>
.getting-started-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
  gap: 16px;
}

.step-card p {
  margin: 0 0 12px;
  color: #475569;
  line-height: 1.75;
}
</style>
