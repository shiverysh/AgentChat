<template>
  <div class="eval-dashboard">
    <div class="eval-header">
      <div>
        <h3>Agent Eval</h3>
        <p>展示规则评分、LLM Judge、版本对比和 case 级明细，方便做 Prompt / Tool / Workflow 迭代。</p>
      </div>
      <el-button type="primary" :icon="RefreshRight" @click="handleRefresh" :loading="refreshing">
        刷新评测数据
      </el-button>
    </div>

    <div class="run-panel">
      <div class="run-panel__header">
        <div>
          <div class="run-panel__title">一键运行 Eval</div>
          <p class="run-panel__desc">配置 Tool 范围、Judge 权重和版本标记，运行完成后会自动刷新 `latest / history / compare` 报告。</p>
        </div>
        <div class="run-panel__actions">
          <el-tag :type="runStatusTagType" effect="plain">{{ runStatusLabel }}</el-tag>
          <el-button
            type="primary"
            @click="handleStartRun"
            :loading="startingRun"
            :disabled="isRunBusy"
          >
            运行 Eval
          </el-button>
        </div>
      </div>

      <div class="run-form-grid">
        <div class="run-form-item">
          <label>版本标签</label>
          <el-input
            v-model="runForm.run_label"
            maxlength="64"
            placeholder="例如 baseline / v3 / prompt_fix"
            :disabled="isRunBusy"
          />
        </div>

        <div class="run-form-item">
          <label>Tool 范围</label>
          <el-select v-model="runForm.tool" :disabled="isRunBusy">
            <el-option label="全部 Tool" value="all" />
            <el-option label="resume_match" value="resume_match" />
            <el-option label="resume_rewrite" value="resume_rewrite" />
            <el-option label="interview_followup" value="interview_followup" />
          </el-select>
        </div>

        <div class="run-form-item">
          <label>Judge 开关</label>
          <el-switch v-model="runForm.enable_judge" :disabled="isRunBusy" />
        </div>

        <div class="run-form-item">
          <label>Judge 权重</label>
          <el-input-number
            v-model="runForm.judge_weight"
            :min="0"
            :max="1"
            :step="0.05"
            :precision="2"
            :disabled="isRunBusy || !runForm.enable_judge"
          />
        </div>

        <div class="run-form-item">
          <label>版本对比</label>
          <el-switch
            v-model="runForm.compare_latest"
            :disabled="isRunBusy"
            inline-prompt
            active-text="开"
            inactive-text="关"
          />
        </div>
      </div>

      <div class="run-status-card">
        <div class="run-status-card__meta">
          <div class="run-status-card__item">
            <span class="meta-label">当前任务</span>
            <span class="meta-value">{{ runStatus.task_id || '暂无' }}</span>
          </div>
          <div class="run-status-card__item">
            <span class="meta-label">当前阶段</span>
            <span class="meta-value">{{ runStatus.progress?.stage || 'idle' }}</span>
          </div>
          <div class="run-status-card__item">
            <span class="meta-label">完成进度</span>
            <span class="meta-value">{{ runProgressText }}</span>
          </div>
          <div class="run-status-card__item" v-if="runStatus.result">
            <span class="meta-label">最新结果</span>
            <span class="meta-value">
              {{ formatPercent(runStatus.result.summary.pass_rate) }} / {{ formatScore(runStatus.result.summary.average_score) }}
            </span>
          </div>
        </div>

        <div class="run-status-card__progress">
          <el-progress
            :percentage="runProgressPercent"
            :status="runProgressBarStatus"
            :stroke-width="10"
          />
          <div class="run-status-card__message">
            {{ runStatus.progress?.message || '尚未发起 Eval 任务' }}
          </div>
        </div>

        <el-alert
          v-if="runStatus.error"
          type="error"
          :closable="false"
          :title="runStatus.error"
          class="run-status-card__alert"
        />

        <div v-if="runStatus.logs.length" class="run-log-list">
          <div class="run-log-list__title">执行日志</div>
          <div class="run-log-list__items">
            <div
              v-for="item in runStatus.logs.slice().reverse()"
              :key="`${item.time}-${item.message}`"
              class="run-log-item"
            >
              <span class="run-log-item__time">{{ formatTime(item.time) }}</span>
              <span class="run-log-item__message">{{ item.message }}</span>
            </div>
          </div>
        </div>
      </div>
    </div>

    <div class="flow-strip">
      <div
        v-for="(step, index) in flowSteps"
        :key="step.title"
        class="flow-card"
      >
        <div class="flow-index">{{ index + 1 }}</div>
        <div class="flow-title">{{ step.title }}</div>
        <div class="flow-desc">{{ step.desc }}</div>
      </div>
    </div>

    <div v-if="loading" class="panel-loading" v-loading="loading"></div>

    <el-empty
      v-else-if="!overview?.latest_report && !overview?.history_reports.length && !overview?.compare_reports.length"
      description="暂未发现 Eval 报告。可直接使用上方的“一键运行 Eval”生成第一版报告。"
    />

    <template v-else>
      <div class="kpi-grid" v-if="selectedCompareReport">
        <div class="kpi-card kpi-card--compare">
          <div class="kpi-label">综合平均分变化</div>
          <div class="kpi-value" :class="deltaClass(selectedCompareReport.overall_delta.average_score_delta)">
            {{ formatDelta(selectedCompareReport.overall_delta.average_score_delta) }}
          </div>
          <div class="kpi-sub">{{ selectedCompareReport.current_label }} vs {{ selectedCompareReport.baseline_label }}</div>
        </div>
        <div class="kpi-card kpi-card--compare">
          <div class="kpi-label">通过率变化</div>
          <div class="kpi-value" :class="deltaClass(selectedCompareReport.overall_delta.pass_rate_delta)">
            {{ formatDelta(selectedCompareReport.overall_delta.pass_rate_delta, true) }}
          </div>
          <div class="kpi-sub">版本对比</div>
        </div>
        <div class="kpi-card kpi-card--compare">
          <div class="kpi-label">Judge 平均分变化</div>
          <div class="kpi-value" :class="deltaClass(selectedCompareReport.overall_delta.judge_average_score_delta)">
            {{ formatDelta(selectedCompareReport.overall_delta.judge_average_score_delta) }}
          </div>
          <div class="kpi-sub">主观质量变化</div>
        </div>
        <div class="kpi-card kpi-card--compare">
          <div class="kpi-label">平均耗时变化</div>
          <div class="kpi-value" :class="deltaClass(-1 * (selectedCompareReport.overall_delta.average_elapsed_seconds_delta || 0))">
            {{ formatDelta(selectedCompareReport.overall_delta.average_elapsed_seconds_delta, false, 's') }}
          </div>
          <div class="kpi-sub">负值代表更快</div>
        </div>
      </div>

      <div class="kpi-grid" v-else-if="activeEvalReport">
        <div class="kpi-card">
          <div class="kpi-label">样例总数</div>
          <div class="kpi-value">{{ activeEvalReport.summary.total_cases }}</div>
          <div class="kpi-sub">当前版本 {{ activeEvalReport.run_label }}</div>
        </div>
        <div class="kpi-card">
          <div class="kpi-label">通过率</div>
          <div class="kpi-value">{{ formatPercent(activeEvalReport.summary.pass_rate) }}</div>
          <div class="kpi-sub">{{ activeEvalReport.summary.passed_cases }}/{{ activeEvalReport.summary.total_cases }}</div>
        </div>
        <div class="kpi-card">
          <div class="kpi-label">综合平均分</div>
          <div class="kpi-value">{{ formatScore(activeEvalReport.summary.average_score) }}</div>
          <div class="kpi-sub">规则 + Judge 融合</div>
        </div>
        <div class="kpi-card">
          <div class="kpi-label">单样例平均耗时</div>
          <div class="kpi-value">{{ formatSeconds(activeEvalReport.summary.runtime?.average_elapsed_seconds) }}</div>
          <div class="kpi-sub">越低越稳定</div>
        </div>
      </div>

      <div class="eval-layout">
        <aside class="eval-sidebar">
          <div class="sidebar-block" v-if="overview?.latest_summary">
            <div class="sidebar-title">当前最新</div>
            <div
              class="report-item"
              :class="{ active: selectedTarget.category === 'latest' }"
              @click="selectLatestReport"
            >
              <div class="report-top">
                <span class="report-name">{{ overview.latest_summary.run_label }}</span>
                <el-tag size="small" type="primary">latest</el-tag>
              </div>
              <div class="report-meta">
                <span>{{ formatTime(overview.latest_summary.generated_at) }}</span>
                <span>{{ formatPercent(overview.latest_summary.pass_rate) }}</span>
              </div>
              <div class="report-score">综合分 {{ formatScore(overview.latest_summary.average_score) }}</div>
            </div>
          </div>

          <div class="sidebar-block">
            <div class="sidebar-title">历史版本</div>
            <div v-if="overview?.history_reports.length" class="report-list">
              <div
                v-for="item in overview.history_reports"
                :key="item.report_name"
                class="report-item"
                :class="{ active: isHistorySelected(item.report_name) }"
                @click="selectHistoryReport(item.report_name)"
              >
                <div class="report-top">
                  <span class="report-name">{{ item.run_label }}</span>
                  <el-tag v-if="item.judge_enabled" size="small" type="success">Judge</el-tag>
                </div>
                <div class="report-meta">
                  <span>{{ formatTime(item.generated_at) }}</span>
                  <span>{{ formatPercent(item.pass_rate) }}</span>
                </div>
                <div class="report-score">综合分 {{ formatScore(item.average_score) }}</div>
              </div>
            </div>
            <el-empty v-else description="暂无历史版本" :image-size="56" />
          </div>

          <div class="sidebar-block">
            <div class="sidebar-title">版本对比</div>
            <div v-if="overview?.compare_reports.length" class="report-list">
              <div
                v-for="item in overview.compare_reports"
                :key="item.report_name"
                class="report-item compare-item"
                :class="{ active: isCompareSelected(item.report_name) }"
                @click="selectCompareReport(item.report_name)"
              >
                <div class="report-top">
                  <span class="report-name">{{ item.current_label }}</span>
                  <span class="compare-arrow">vs</span>
                  <span class="report-name">{{ item.baseline_label }}</span>
                </div>
                <div class="report-meta">
                  <span>{{ formatTime(item.generated_at) }}</span>
                  <span :class="deltaClass(item.overall_delta.average_score_delta)">
                    {{ formatDelta(item.overall_delta.average_score_delta) }}
                  </span>
                </div>
              </div>
            </div>
            <el-empty v-else description="暂无版本对比" :image-size="56" />
          </div>
        </aside>

        <section class="eval-main">
          <div class="detail-card" v-loading="detailLoading">
            <div class="detail-header">
              <div>
                <h4>{{ detailTitle }}</h4>
                <p>{{ detailSubtitle }}</p>
              </div>
              <div class="detail-tags" v-if="activeEvalReport">
                <el-tag size="small" effect="plain">权重 {{ activeEvalReport.judge_weight }}</el-tag>
                <el-tag size="small" type="success" effect="plain" v-if="activeEvalReport.judge_enabled">Judge 已启用</el-tag>
                <el-tag size="small" type="info" effect="plain">{{ formatTime(activeEvalReport.generated_at) }}</el-tag>
              </div>
            </div>

            <div class="charts-grid">
              <div class="chart-card">
                <div class="chart-title">Tool 评分对比</div>
                <div ref="toolScoreChartRef" class="chart-body"></div>
                <div v-if="!toolChartHasData" class="chart-empty">暂无可视化数据</div>
              </div>
              <div class="chart-card">
                <div class="chart-title">版本趋势</div>
                <div ref="historyTrendChartRef" class="chart-body"></div>
                <div v-if="!historyChartHasData" class="chart-empty">历史版本不足，暂无趋势</div>
              </div>
            </div>

            <template v-if="selectedCompareReport">
              <div class="table-card">
                <div class="table-title">Tool 级变化</div>
                <el-table :data="compareToolRows" stripe>
                  <el-table-column prop="tool" label="Tool" min-width="180" />
                  <el-table-column label="综合平均分变化" min-width="140">
                    <template #default="{ row }">
                      <span :class="deltaClass(row.average_score_delta)">{{ formatDelta(row.average_score_delta) }}</span>
                    </template>
                  </el-table-column>
                  <el-table-column label="规则平均分变化" min-width="140">
                    <template #default="{ row }">
                      <span :class="deltaClass(row.rule_average_score_delta)">{{ formatDelta(row.rule_average_score_delta) }}</span>
                    </template>
                  </el-table-column>
                  <el-table-column label="Judge 平均分变化" min-width="140">
                    <template #default="{ row }">
                      <span :class="deltaClass(row.judge_average_score_delta)">{{ formatDelta(row.judge_average_score_delta) }}</span>
                    </template>
                  </el-table-column>
                  <el-table-column label="通过率变化" min-width="120">
                    <template #default="{ row }">
                      <span :class="deltaClass(row.pass_rate_delta)">{{ formatDelta(row.pass_rate_delta, true) }}</span>
                    </template>
                  </el-table-column>
                  <el-table-column label="平均耗时变化" min-width="120">
                    <template #default="{ row }">
                      <span>{{ formatDelta(row.average_elapsed_seconds_delta, false, 's') }}</span>
                    </template>
                  </el-table-column>
                </el-table>
              </div>
            </template>

            <template v-else-if="activeEvalReport">
              <div class="table-card">
                <div class="table-title">Case 级明细</div>
                <el-table :data="activeEvalReport.cases" stripe>
                  <el-table-column prop="case_id" label="Case" min-width="220" show-overflow-tooltip />
                  <el-table-column prop="tool" label="Tool" min-width="150" />
                  <el-table-column label="综合分" min-width="110">
                    <template #default="{ row }">{{ formatScore(row.overall_score) }}</template>
                  </el-table-column>
                  <el-table-column label="规则分" min-width="110">
                    <template #default="{ row }">{{ formatScore(row.rule_score) }}</template>
                  </el-table-column>
                  <el-table-column label="Judge 分" min-width="110">
                    <template #default="{ row }">{{ row.judge_score == null ? '-' : formatScore(row.judge_score) }}</template>
                  </el-table-column>
                  <el-table-column label="结果" min-width="90">
                    <template #default="{ row }">
                      <el-tag :type="row.passed ? 'success' : 'danger'" size="small">
                        {{ row.passed ? 'PASS' : 'FAIL' }}
                      </el-tag>
                    </template>
                  </el-table-column>
                  <el-table-column label="说明" min-width="280" show-overflow-tooltip>
                    <template #default="{ row }">
                      {{ (row.notes || []).join(' / ') || '-' }}
                    </template>
                  </el-table-column>
                </el-table>
              </div>
            </template>
          </div>
        </section>
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { RefreshRight } from '@element-plus/icons-vue'
import * as echarts from 'echarts/core'
import type { ECharts as EChartsInstance } from 'echarts/core'
import { BarChart, LineChart } from 'echarts/charts'
import { GridComponent, LegendComponent, TitleComponent, TooltipComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import {
  getEvalDashboardRunStatusAPI,
  getEvalDashboardOverviewAPI,
  getEvalDashboardReportAPI,
  type EvalCompareReport,
  type EvalDashboardOverview,
  type EvalDashboardReport,
  type EvalReportSummary,
  type EvalRunRequest,
  type EvalRunStatus,
  startEvalDashboardRunAPI,
} from '../../../apis/eval-dashboard'

echarts.use([TitleComponent, TooltipComponent, LegendComponent, GridComponent, BarChart, LineChart, CanvasRenderer])

type DetailTarget =
  | { category: 'latest' }
  | { category: 'history' | 'compare'; reportName: string }

const flowSteps = [
  {
    title: '样例集定义',
    desc: '按 Tool 维度定义 JD、简历、项目输入和通过阈值。',
  },
  {
    title: 'Agent 执行',
    desc: '运行 resume_match、resume_rewrite、interview_followup 产出结构化结果。',
  },
  {
    title: '规则评分',
    desc: '检查数量、关键词覆盖、事实保留和风险项等硬指标。',
  },
  {
    title: 'Judge 复核',
    desc: '补岗位贴合度、建议质量和回答深度等语义判断。',
  },
  {
    title: '版本对比',
    desc: '沉淀 latest / history / compare 报告，驱动 Prompt 与 Workflow 迭代。',
  },
]

const createIdleRunStatus = (): EvalRunStatus => ({
  task_id: null,
  status: 'idle',
  created_at: null,
  started_at: null,
  finished_at: null,
  config: null,
  progress: null,
  logs: [],
  result: null,
  error: null,
  is_active: false,
})

const overview = ref<EvalDashboardOverview | null>(null)
const selectedTarget = ref<DetailTarget>({ category: 'latest' })
const selectedDetail = ref<EvalDashboardReport | EvalCompareReport | null>(null)
const runForm = ref<EvalRunRequest>({
  run_label: 'manual_eval',
  tool: 'all',
  enable_judge: true,
  judge_weight: 0.35,
  compare_latest: true,
})
const runStatus = ref<EvalRunStatus>(createIdleRunStatus())

const loading = ref(false)
const refreshing = ref(false)
const detailLoading = ref(false)
const startingRun = ref(false)

const toolScoreChartRef = ref<HTMLElement | null>(null)
const historyTrendChartRef = ref<HTMLElement | null>(null)
let runStatusTimer: ReturnType<typeof window.setTimeout> | null = null

let toolScoreChart: EChartsInstance | null = null
let historyTrendChart: EChartsInstance | null = null

const toolChartHasData = ref(false)
const historyChartHasData = ref(false)
const isRunBusy = computed(() => ['queued', 'running'].includes(runStatus.value.status))
const runProgressPercent = computed(() => Math.round((runStatus.value.progress?.percent || 0) * 100))
const runProgressText = computed(() => {
  const progress = runStatus.value.progress
  if (!progress) {
    return '0 / 0'
  }
  return `${progress.completed_cases || 0} / ${progress.total_cases || 0}`
})
const runStatusLabel = computed(() => {
  switch (runStatus.value.status) {
    case 'queued':
      return '排队中'
    case 'running':
      return '运行中'
    case 'success':
      return '已完成'
    case 'error':
      return '执行失败'
    default:
      return '未运行'
  }
})
const runStatusTagType = computed(() => {
  switch (runStatus.value.status) {
    case 'queued':
      return 'warning'
    case 'running':
      return 'primary'
    case 'success':
      return 'success'
    case 'error':
      return 'danger'
    default:
      return 'info'
  }
})
const runProgressBarStatus = computed(() => {
  if (runStatus.value.status === 'error') {
    return 'exception'
  }
  if (runStatus.value.status === 'success') {
    return 'success'
  }
  return undefined
})

const activeEvalReport = computed(() => {
  if (selectedDetail.value && !isCompareReport(selectedDetail.value)) {
    return selectedDetail.value
  }
  return overview.value?.latest_report || null
})

const selectedCompareReport = computed(() => {
  if (selectedDetail.value && isCompareReport(selectedDetail.value)) {
    return selectedDetail.value
  }
  return null
})

const detailTitle = computed(() => {
  if (selectedCompareReport.value) {
    return `版本对比：${selectedCompareReport.value.current_label} vs ${selectedCompareReport.value.baseline_label}`
  }
  if (selectedDetail.value && !isCompareReport(selectedDetail.value)) {
    return `评测版本：${selectedDetail.value.run_label}`
  }
  return 'Agent Eval 详情'
})

const detailSubtitle = computed(() => {
  if (selectedCompareReport.value) {
    return '查看综合平均分、通过率和耗时在不同版本之间的变化。'
  }
  if (activeEvalReport.value) {
    return '当前展示规则评分、Judge 评分和 case 级明细。'
  }
  return '请选择一个评测版本查看详情。'
})

const trendReports = computed(() => {
  const seen = new Set<string>()
  const result: EvalReportSummary[] = []

  if (overview.value?.latest_summary) {
    result.push(overview.value.latest_summary)
    seen.add(overview.value.latest_summary.report_name)
  }

  for (const item of overview.value?.history_reports || []) {
    if (!seen.has(item.report_name)) {
      result.push(item)
      seen.add(item.report_name)
    }
  }

  return result.slice().reverse()
})

const compareToolRows = computed(() => {
  if (!selectedCompareReport.value) {
    return []
  }

  return Object.entries(selectedCompareReport.value.tool_deltas || {}).map(([tool, delta]) => ({
    tool,
    ...delta,
  }))
})

const initCharts = () => {
  if (toolScoreChartRef.value) {
    toolScoreChart?.dispose()
    toolScoreChart = echarts.init(toolScoreChartRef.value)
    toolScoreChart.setOption({
      color: ['#1d4ed8', '#38bdf8', '#14b8a6'],
      tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
      legend: { top: 10 },
      grid: { left: '4%', right: '4%', bottom: 36, top: 48, containLabel: true },
      xAxis: { type: 'category', data: [] },
      yAxis: { type: 'value', max: 100, axisLabel: { formatter: '{value}%' } },
      series: [],
    })
  }

  if (historyTrendChartRef.value) {
    historyTrendChart?.dispose()
    historyTrendChart = echarts.init(historyTrendChartRef.value)
    historyTrendChart.setOption({
      color: ['#2563eb', '#22c55e', '#7c3aed'],
      tooltip: { trigger: 'axis' },
      legend: { top: 10 },
      grid: { left: '4%', right: '4%', bottom: 36, top: 48, containLabel: true },
      xAxis: { type: 'category', data: [] },
      yAxis: { type: 'value', max: 100, axisLabel: { formatter: '{value}%' } },
      series: [],
    })
  }
}

const updateToolScoreChart = () => {
  const report = activeEvalReport.value
  if (!toolScoreChart) return

  if (!report) {
    toolChartHasData.value = false
    toolScoreChart.setOption({
      xAxis: { data: [] },
      legend: { data: [] },
      series: [],
    })
    return
  }

  const toolSummary = report.summary.tool_summary || {}
  const toolNames = Object.keys(toolSummary)
  if (!toolNames.length) {
    toolChartHasData.value = false
    toolScoreChart.setOption({
      xAxis: { data: [] },
      legend: { data: [] },
      series: [],
    })
    return
  }

  const overallScores = toolNames.map(tool => Number(toolSummary[tool]?.average_score || 0) * 100)
  const ruleScores = toolNames.map(tool => Number(toolSummary[tool]?.rule_average_score || 0) * 100)
  const judgeScores = toolNames.map(tool => Number(toolSummary[tool]?.judge_average_score || 0) * 100)
  const hasJudgeSeries = judgeScores.some(score => score > 0)

  const series = [
    { name: '综合分', type: 'bar', data: overallScores, barMaxWidth: 26 },
    { name: '规则分', type: 'bar', data: ruleScores, barMaxWidth: 26 },
  ]

  if (hasJudgeSeries) {
    series.push({ name: 'Judge 分', type: 'bar', data: judgeScores, barMaxWidth: 26 } as any)
  }

  toolChartHasData.value = true
  toolScoreChart.setOption({
    xAxis: { data: toolNames },
    legend: { data: series.map(item => item.name) },
    series,
  })
}

const updateHistoryTrendChart = () => {
  if (!historyTrendChart) return

  const reports = trendReports.value
  if (!reports.length) {
    historyChartHasData.value = false
    historyTrendChart.setOption({
      xAxis: { data: [] },
      legend: { data: [] },
      series: [],
    })
    return
  }

  const labels = reports.map(item => item.run_label)
  const averageScores = reports.map(item => Number(item.average_score || 0) * 100)
  const passRates = reports.map(item => Number(item.pass_rate || 0) * 100)
  const judgeScores = reports.map(item => Number(item.judge_average_score || 0) * 100)
  const hasJudge = judgeScores.some(score => score > 0)

  const series: any[] = [
    {
      name: '综合平均分',
      type: 'line',
      smooth: true,
      data: averageScores,
    },
    {
      name: '通过率',
      type: 'line',
      smooth: true,
      data: passRates,
    },
  ]

  if (hasJudge) {
    series.push({
      name: 'Judge 平均分',
      type: 'line',
      smooth: true,
      lineStyle: { type: 'dashed' },
      data: judgeScores,
    })
  }

  historyChartHasData.value = reports.length > 0
  historyTrendChart.setOption({
    xAxis: { data: labels },
    legend: { data: series.map(item => item.name) },
    series,
  })
}

const resizeCharts = () => {
  toolScoreChart?.resize()
  historyTrendChart?.resize()
}

const fetchOverview = async (preserveSelection = false) => {
  loading.value = true
  try {
    const res = await getEvalDashboardOverviewAPI()
    if (res.data.status_code !== 200) {
      throw new Error(res.data.status_message || '获取 Eval 看板失败')
    }

    overview.value = res.data.data

    if (!preserveSelection) {
      if (overview.value.latest_report) {
        selectedTarget.value = { category: 'latest' }
        selectedDetail.value = overview.value.latest_report
      } else if (overview.value.history_reports.length) {
        await selectHistoryReport(overview.value.history_reports[0].report_name)
      } else if (overview.value.compare_reports.length) {
        await selectCompareReport(overview.value.compare_reports[0].report_name)
      } else {
        selectedDetail.value = null
      }
      return
    }

    if (selectedTarget.value.category === 'latest') {
      selectedDetail.value = overview.value.latest_report
      return
    }

    const sourceList = selectedTarget.value.category === 'history'
      ? overview.value.history_reports
      : overview.value.compare_reports
    const exists = sourceList.some(item => item.report_name === selectedTarget.value.reportName)
    if (exists) {
      await fetchReportDetail(selectedTarget.value.category, selectedTarget.value.reportName)
    } else if (overview.value.latest_report) {
      selectedTarget.value = { category: 'latest' }
      selectedDetail.value = overview.value.latest_report
    }
  } catch (error: any) {
    console.error('获取 Eval 看板失败:', error)
    ElMessage.error(error?.message || '获取 Eval 看板失败')
  } finally {
    loading.value = false
  }
}

const fetchReportDetail = async (category: 'history' | 'compare', reportName: string) => {
  detailLoading.value = true
  try {
    const res = await getEvalDashboardReportAPI(category, reportName)
    if (res.data.status_code !== 200) {
      throw new Error(res.data.status_message || '获取报告详情失败')
    }
    selectedDetail.value = res.data.data as EvalDashboardReport | EvalCompareReport
  } catch (error: any) {
    console.error('获取 Eval 报告详情失败:', error)
    ElMessage.error(error?.message || '获取报告详情失败')
  } finally {
    detailLoading.value = false
  }
}

const selectLatestReport = () => {
  selectedTarget.value = { category: 'latest' }
  selectedDetail.value = overview.value?.latest_report || null
}

const selectHistoryReport = async (reportName: string) => {
  selectedTarget.value = { category: 'history', reportName }
  await fetchReportDetail('history', reportName)
}

const selectCompareReport = async (reportName: string) => {
  selectedTarget.value = { category: 'compare', reportName }
  await fetchReportDetail('compare', reportName)
}

const isHistorySelected = (reportName: string) => {
  return selectedTarget.value.category === 'history' && selectedTarget.value.reportName === reportName
}

const isCompareSelected = (reportName: string) => {
  return selectedTarget.value.category === 'compare' && selectedTarget.value.reportName === reportName
}

const handleRefresh = async () => {
  refreshing.value = true
  await fetchOverview(true)
  await fetchRunStatus(runStatus.value.task_id || undefined, { silent: true, refreshOnFinish: false })
  refreshing.value = false
  ElMessage.success('Eval 看板已刷新')
}

const stopRunStatusPolling = () => {
  if (runStatusTimer) {
    window.clearTimeout(runStatusTimer)
    runStatusTimer = null
  }
}

const scheduleRunStatusPolling = (taskId?: string) => {
  stopRunStatusPolling()
  runStatusTimer = window.setTimeout(() => {
    void fetchRunStatus(taskId)
  }, 2500)
}

const fetchRunStatus = async (
  taskId?: string,
  options: { silent?: boolean; refreshOnFinish?: boolean } = {},
) => {
  const previousStatus = runStatus.value.status
  try {
    const res = await getEvalDashboardRunStatusAPI(taskId)
    if (res.data.status_code !== 200) {
      throw new Error(res.data.status_message || '获取 Eval 运行状态失败')
    }

    runStatus.value = res.data.data || createIdleRunStatus()

    if (isRunBusy.value) {
      scheduleRunStatusPolling(runStatus.value.task_id || undefined)
      return
    }

    stopRunStatusPolling()
    if (options.refreshOnFinish !== false && ['queued', 'running'].includes(previousStatus)) {
      if (runStatus.value.status === 'success') {
        await fetchOverview(true)
        ElMessage.success('Eval 已完成，报告已刷新')
      } else if (runStatus.value.status === 'error') {
        ElMessage.error(runStatus.value.error || 'Eval 执行失败')
      }
    }
  } catch (error: any) {
    stopRunStatusPolling()
    if (!options.silent) {
      ElMessage.error(error?.response?.data?.detail || error?.message || '获取 Eval 运行状态失败')
    }
  }
}

const handleStartRun = async () => {
  if (isRunBusy.value) {
    ElMessage.warning('当前已有 Eval 任务在运行，请等待完成')
    return
  }

  startingRun.value = true
  try {
    const payload: EvalRunRequest = {
      ...runForm.value,
      run_label: runForm.value.run_label.trim() || 'manual_eval',
      judge_weight: Number(runForm.value.judge_weight || 0),
    }
    const res = await startEvalDashboardRunAPI(payload)
    if (res.data.status_code !== 200) {
      throw new Error(res.data.status_message || '启动 Eval 任务失败')
    }

    runStatus.value = res.data.data
    ElMessage.success('Eval 任务已启动')
    scheduleRunStatusPolling(runStatus.value.task_id || undefined)
  } catch (error: any) {
    ElMessage.error(error?.response?.data?.detail || error?.message || '启动 Eval 任务失败')
  } finally {
    startingRun.value = false
  }
}

const isCompareReport = (value: EvalDashboardReport | EvalCompareReport): value is EvalCompareReport => {
  return typeof value === 'object' && value !== null && 'overall_delta' in value && !('summary' in value)
}

const formatScore = (value?: number | null) => {
  if (value == null) return '-'
  return `${(Number(value) * 100).toFixed(1)}`
}

const formatPercent = (value?: number | null) => {
  if (value == null) return '-'
  return `${(Number(value) * 100).toFixed(1)}%`
}

const formatSeconds = (value?: number | null) => {
  if (value == null) return '-'
  return `${Number(value).toFixed(2)}s`
}

const formatTime = (value?: string) => {
  if (!value) return '-'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return date.toLocaleString('zh-CN', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  })
}

const formatDelta = (value?: number, percent = false, suffix = '') => {
  if (value == null) return '-'
  const actual = percent ? Number(value) * 100 : Number(value)
  const sign = actual > 0 ? '+' : ''
  const finalSuffix = percent ? '%' : suffix
  return `${sign}${actual.toFixed(2)}${finalSuffix}`
}

const deltaClass = (value?: number | null) => {
  if (value == null || value === 0) return 'delta-neutral'
  return value > 0 ? 'delta-positive' : 'delta-negative'
}

watch(
  () => [activeEvalReport.value, trendReports.value],
  async () => {
    await nextTick()
    updateToolScoreChart()
    updateHistoryTrendChart()
    resizeCharts()
  },
  { deep: true }
)

onMounted(async () => {
  await nextTick()
  initCharts()
  await fetchOverview()
  await fetchRunStatus(undefined, { silent: true, refreshOnFinish: false })
  if (isRunBusy.value) {
    scheduleRunStatusPolling(runStatus.value.task_id || undefined)
  }
  window.addEventListener('resize', resizeCharts)
})

onBeforeUnmount(() => {
  window.removeEventListener('resize', resizeCharts)
  stopRunStatusPolling()
  toolScoreChart?.dispose()
  historyTrendChart?.dispose()
  toolScoreChart = null
  historyTrendChart = null
})
</script>

<style scoped lang="scss">
.eval-dashboard {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.eval-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;

  h3 {
    margin: 0;
    font-size: 22px;
    color: #132238;
  }

  p {
    margin: 6px 0 0;
    color: #6c7a92;
    font-size: 13px;
    line-height: 1.6;
  }
}

.run-panel {
  padding: 18px;
  border-radius: 18px;
  background: linear-gradient(180deg, #ffffff 0%, #f5f8ff 100%);
  border: 1px solid #d8e4ff;
  box-shadow: 0 18px 32px rgba(15, 23, 42, 0.06);
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.run-panel__header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
}

.run-panel__title {
  font-size: 18px;
  font-weight: 800;
  color: #153255;
}

.run-panel__desc {
  margin: 6px 0 0;
  font-size: 13px;
  color: #68778f;
  line-height: 1.6;
}

.run-panel__actions {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.run-form-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: 14px;
}

.run-form-item {
  display: flex;
  flex-direction: column;
  gap: 8px;

  label {
    font-size: 12px;
    color: #607086;
    font-weight: 700;
  }
}

.run-status-card {
  padding: 16px;
  border-radius: 16px;
  background: rgba(255, 255, 255, 0.82);
  border: 1px solid #e4ebf7;
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.run-status-card__meta {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: 12px;
}

.run-status-card__item {
  padding: 12px 14px;
  border-radius: 14px;
  background: #f8fbff;
  border: 1px solid #e7eefb;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.meta-label {
  font-size: 12px;
  color: #7a879a;
}

.meta-value {
  font-size: 13px;
  color: #17324e;
  font-weight: 700;
  word-break: break-all;
}

.run-status-card__progress {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.run-status-card__message {
  font-size: 13px;
  color: #4b5b72;
  line-height: 1.6;
}

.run-status-card__alert {
  margin-top: 2px;
}

.run-log-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.run-log-list__title {
  font-size: 13px;
  font-weight: 700;
  color: #16304f;
}

.run-log-list__items {
  display: flex;
  flex-direction: column;
  gap: 8px;
  max-height: 220px;
  overflow-y: auto;
  padding-right: 4px;
}

.run-log-item {
  display: grid;
  grid-template-columns: 96px minmax(0, 1fr);
  gap: 12px;
  padding: 10px 12px;
  border-radius: 12px;
  background: #f8fbff;
  border: 1px solid #e7eefb;
}

.run-log-item__time {
  font-size: 12px;
  color: #8190a7;
}

.run-log-item__message {
  min-width: 0;
  font-size: 12px;
  color: #2a3a51;
  line-height: 1.6;
}

.flow-strip {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: 14px;
}

.flow-card {
  position: relative;
  padding: 18px 16px 16px;
  border-radius: 16px;
  background: linear-gradient(180deg, #ffffff 0%, #f3f8ff 100%);
  border: 1px solid #d9e7ff;
  box-shadow: 0 14px 28px rgba(17, 24, 39, 0.06);
}

.flow-index {
  width: 28px;
  height: 28px;
  border-radius: 999px;
  background: #1d4ed8;
  color: #fff;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-size: 13px;
  font-weight: 700;
  margin-bottom: 12px;
}

.flow-title {
  font-size: 14px;
  font-weight: 700;
  color: #16304f;
  margin-bottom: 8px;
}

.flow-desc {
  font-size: 12px;
  color: #66758a;
  line-height: 1.6;
}

.panel-loading {
  min-height: 180px;
  border-radius: 16px;
  background: #fff;
}

.kpi-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 14px;
}

.kpi-card {
  padding: 18px;
  border-radius: 16px;
  background: linear-gradient(180deg, #ffffff 0%, #f8fbff 100%);
  border: 1px solid #e1ebff;
  box-shadow: 0 12px 28px rgba(17, 24, 39, 0.05);
}

.kpi-card--compare {
  background: linear-gradient(180deg, #ffffff 0%, #f5fbf8 100%);
}

.kpi-label {
  font-size: 12px;
  color: #6b7280;
  margin-bottom: 10px;
}

.kpi-value {
  font-size: 30px;
  font-weight: 800;
  color: #10263f;
  line-height: 1.15;
}

.kpi-sub {
  margin-top: 8px;
  font-size: 12px;
  color: #8290a6;
}

.eval-layout {
  display: grid;
  grid-template-columns: 320px minmax(0, 1fr);
  gap: 18px;
}

.eval-sidebar {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.sidebar-block,
.detail-card,
.chart-card,
.table-card {
  background: #fff;
  border-radius: 16px;
  border: 1px solid #e8edf5;
  box-shadow: 0 14px 32px rgba(15, 23, 42, 0.06);
}

.sidebar-block {
  padding: 16px;
}

.sidebar-title {
  font-size: 14px;
  font-weight: 700;
  color: #1c304f;
  margin-bottom: 12px;
}

.report-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.report-item {
  padding: 12px 13px;
  border-radius: 14px;
  border: 1px solid #e8edf5;
  background: linear-gradient(180deg, #fbfdff 0%, #f4f8ff 100%);
  cursor: pointer;
  transition: all 0.2s ease;
}

.report-item:hover {
  border-color: #b6d0ff;
  transform: translateY(-1px);
}

.report-item.active {
  border-color: #5b8ff9;
  background: linear-gradient(180deg, #eef5ff 0%, #f4f8ff 100%);
  box-shadow: 0 10px 20px rgba(37, 99, 235, 0.12);
}

.report-top,
.report-meta {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.report-name {
  font-size: 13px;
  font-weight: 700;
  color: #143253;
}

.report-meta {
  margin-top: 8px;
  font-size: 12px;
  color: #7b8698;
}

.report-score {
  margin-top: 8px;
  font-size: 12px;
  color: #2563eb;
  font-weight: 700;
}

.compare-arrow {
  color: #8aa0bf;
  font-size: 12px;
}

.eval-main {
  min-width: 0;
}

.detail-card {
  padding: 18px;
}

.detail-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 14px;
  margin-bottom: 18px;

  h4 {
    margin: 0;
    font-size: 18px;
    color: #132238;
  }

  p {
    margin: 6px 0 0;
    font-size: 13px;
    color: #6b7280;
  }
}

.detail-tags {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.charts-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(360px, 1fr));
  gap: 16px;
  margin-bottom: 18px;
}

.chart-card {
  position: relative;
  padding: 16px;
}

.chart-title,
.table-title {
  font-size: 14px;
  font-weight: 700;
  color: #1c304f;
  margin-bottom: 14px;
}

.chart-body {
  width: 100%;
  height: 320px;
}

.chart-empty {
  position: absolute;
  inset: 52px 16px 16px 16px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #94a3b8;
  font-size: 13px;
  pointer-events: none;
}

.table-card {
  padding: 16px;
}

.delta-positive {
  color: #059669;
  font-weight: 700;
}

.delta-negative {
  color: #dc2626;
  font-weight: 700;
}

.delta-neutral {
  color: #475569;
  font-weight: 700;
}

@media (max-width: 1320px) {
  .eval-layout {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 768px) {
  .eval-header {
    flex-direction: column;
  }

  .run-panel__header {
    flex-direction: column;
  }

  .run-log-item {
    grid-template-columns: 1fr;
    gap: 6px;
  }

  .charts-grid {
    grid-template-columns: 1fr;
  }
}
</style>
