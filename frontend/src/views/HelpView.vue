<template>
  <main class="page-shell dashboard-shell help-page">
    <section class="page-heading">
      <div>
        <p class="eyebrow">help</p>
        <h1>帮助中心</h1>
      </div>
      <div class="toolbar">
        <el-button @click="router.push('/getting-started')">新手引导</el-button>
        <el-button @click="router.push('/about')">版本信息</el-button>
        <el-button type="primary" @click="router.push('/maintenance')">系统维护</el-button>
      </div>
    </section>

    <section class="table-surface">
      <div class="section-title">
        <h2>快速开始</h2>
        <span>本地单机</span>
      </div>
      <ol>
        <li>双击 `start.bat` 启动系统。</li>
        <li>创建普通项目，或使用“创建示例项目”体验完整流程。</li>
        <li>导入 `sample_data` 目录中的示例 Excel，确认字段映射并发布批次。</li>
        <li>查看 Dashboard、预警、整改闭环和报表中心。</li>
      </ol>
    </section>

    <section class="help-grid">
      <article v-for="section in sections" :key="section.title" class="table-surface">
        <div class="section-title">
          <h2>{{ section.title }}</h2>
          <span>{{ section.tag }}</span>
        </div>
        <p>{{ section.body }}</p>
        <ul>
          <li v-for="item in section.items" :key="item">{{ item }}</li>
        </ul>
      </article>
    </section>
  </main>
</template>

<script setup lang="ts">
import { useRouter } from 'vue-router'

const router = useRouter()

const sections = [
  {
    title: '如何准备 Excel',
    tag: 'Excel',
    body: '建议每行对应一个施工任务，表头尽量包含任务名称、楼栋、楼层、专业、计划时间和实际进度信息。',
    items: ['支持单 Sheet 和多 Sheet。', '同一 Sheet 内不要混入说明页或问题清单。', '可以使用 sample_data 目录中的示例文件先试导入。'],
  },
  {
    title: '字段映射说明',
    tag: '字段',
    body: '系统会自动推荐字段映射，导入前仍建议确认关键字段是否正确。',
    items: ['任务名称是必填字段。', '实际完成率、累计完成量或实际完成量至少需要一类可计算字段。', '施工单位、责任人、备注等可保存为扩展字段用于追溯。'],
  },
  {
    title: '统计口径说明',
    tag: '口径',
    body: '系统会根据 Excel 字段自动推荐统计口径，所有图表均按当前筛选范围计算。',
    items: ['有权重字段时优先支持权重统计。', '有工程量字段时支持工程量统计。', '只有百分比字段时可使用完成率平均或任务平均。'],
  },
  {
    title: 'Dashboard V2 使用说明',
    tag: '看板',
    body: 'Dashboard V2 是默认看板，用于查看当前实际进度、按计划应完成进度、进度偏差和整改摘要。',
    items: ['可按日期、Sheet、专业、楼栋、楼层和施工单位筛选。', '计划开始时间未到的任务暂不纳入滞后判断。', '楼栋视图采用 2.5D 楼栋立面进度图；后续接入 BIM / IFC / glTF 模型时可扩展为真实 3D 进度展示。'],
  },
  {
    title: '预警与整改闭环说明',
    tag: '闭环',
    body: '预警用于发现进度风险，整改闭环用于记录责任、措施、状态和复查结果。',
    items: ['可从预警记录生成整改项。', '也可从滞后项或整改页面手动创建。', '未关闭整改项会显示在工作台和 Dashboard。'],
  },
  {
    title: 'Word / PDF / Excel 报表说明',
    tag: '报表',
    body: '报表中心提供当前看板 Excel、Word 周报、PDF 周报、整改跟踪表和整改清单。',
    items: ['当前看板 Excel 适合数据核对和内部分析。', 'Word / PDF 周报适合会议汇报、归档和打印。', '整改类报表适合跟踪问题闭环和下发施工单位。'],
  },
  {
    title: '备份恢复说明',
    tag: '维护',
    body: '系统维护页和 backup.bat 可用于本地备份；恢复前应先停止系统并保留当前备份。',
    items: ['导入大批量数据前建议先备份。', '迁移电脑前复制整个 portable 目录。', '恢复备份后建议重启系统。'],
  },
  {
    title: '安装包使用说明',
    tag: '安装包',
    body: '本地安装包不需要单独服务器，双击根目录中文脚本即可启动。',
    items: ['数据默认保存在安装包内的数据、上传、导出和备份目录。', '不要手动删除 data、uploads、exports 和 backups。', '迁移电脑时复制整个安装包文件夹。'],
  },
  {
    title: '常见问题',
    tag: 'FAQ',
    body: '遇到页面无法加载、报表无法导出或导入校验不通过时，优先检查服务状态、发布批次和字段映射。',
    items: ['后端服务不可用时请重新启动系统。', '当前暂无可导出数据时请先导入并发布批次。', '字段缺失时请回到字段映射页确认任务名称和进度字段。'],
  },
]
</script>

<style scoped>
.help-page ol,
.help-page ul {
  margin: 0;
  padding-left: 20px;
  line-height: 1.9;
}

.help-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
  gap: 16px;
}

.help-grid p {
  margin: 0 0 10px;
  color: #475569;
  line-height: 1.7;
}
</style>
