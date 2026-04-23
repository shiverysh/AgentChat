<script setup lang="ts">
import { computed } from 'vue'

import type { InterviewFollowupResult } from '../../type'

const props = defineProps<{
  result: InterviewFollowupResult
}>()

const emit = defineEmits<{
  createPlan: [result: InterviewFollowupResult]
  saveNotes: [result: InterviewFollowupResult]
  createCalendar: [result: InterviewFollowupResult]
}>()

const qaItems = computed(() => {
  return props.result.question_answer_pairs.length
    ? props.result.question_answer_pairs
    : [
        {
          dimension: '项目复盘',
          question: '请详细说明项目里你负责的关键部分。',
          answer_outline: '按业务背景、技术方案、个人动作和结果指标展开。',
          why_it_matters: '用于判断你对项目的真实参与深度。',
        },
      ]
})

const deepDiveItems = computed(() => {
  return props.result.deep_dive_points.length
    ? props.result.deep_dive_points
    : ['优先准备 Agent 设计、工具调用链路和结果评估方式。']
})

const riskItems = computed(() => {
  return props.result.risk_points.length
    ? props.result.risk_points
    : ['避免只讲概念，不讲你的具体动作、技术决策和结果。']
})
</script>

<template>
  <section class="interview-followup-card">
    <div class="card-header">
      <div class="header-main">
        <span class="card-badge">Interview Prep</span>
        <h3>{{ result.target_role }}</h3>
        <p>{{ result.overall_summary }}</p>
      </div>
      <div class="header-side">
        <span class="side-label">面试重心</span>
        <strong>追问演练</strong>
      </div>
    </div>

    <div class="content-grid">
      <section class="content-block qa-block">
        <div class="block-header">
          <span class="block-dot primary"></span>
          <h4>高频追问与回答框架</h4>
        </div>

        <div class="qa-list">
          <article v-for="(item, index) in qaItems" :key="`${item.question}-${index}`" class="qa-item">
            <div class="qa-head">
              <span v-if="item.dimension" class="dimension-pill">{{ item.dimension }}</span>
              <span class="qa-index">Q{{ index + 1 }}</span>
            </div>
            <h5>{{ item.question }}</h5>
            <p><strong>回答框架：</strong>{{ item.answer_outline }}</p>
            <p v-if="item.why_it_matters"><strong>面试官意图：</strong>{{ item.why_it_matters }}</p>
          </article>
        </div>
      </section>

      <div class="side-grid">
        <section class="content-block">
          <div class="block-header">
            <span class="block-dot success"></span>
            <h4>建议深挖</h4>
          </div>
          <ul class="unordered-list">
            <li v-for="item in deepDiveItems" :key="item">{{ item }}</li>
          </ul>
        </section>

        <section class="content-block risk-block">
          <div class="block-header">
            <span class="block-dot warning"></span>
            <h4>风险提醒</h4>
          </div>
          <ul class="unordered-list">
            <li v-for="item in riskItems" :key="item">{{ item }}</li>
          </ul>
        </section>
      </div>
    </div>

    <div class="action-row">
      <button type="button" class="action-btn secondary" @click="emit('saveNotes', result)">
        保存追问笔记
      </button>
      <button type="button" class="action-btn secondary-alt" @click="emit('createCalendar', result)">
        安排飞书日程
      </button>
      <button type="button" class="action-btn" @click="emit('createPlan', result)">
        生成面试计划
      </button>
    </div>
  </section>
</template>

<style scoped lang="scss">
.interview-followup-card {
  width: min(920px, 100%);
  padding: 22px;
  border-radius: 24px;
  border: 1px solid #d9e6df;
  background:
    radial-gradient(circle at top right, rgba(187, 238, 225, 0.34), transparent 30%),
    linear-gradient(180deg, #fbfffd 0%, #f5fbff 100%);
  box-shadow: 0 16px 32px rgba(66, 121, 103, 0.1);
}

.card-header {
  display: flex;
  justify-content: space-between;
  gap: 18px;
  align-items: flex-start;
}

.header-main {
  h3 {
    margin: 12px 0 8px;
    font-size: 24px;
    color: #124a3d;
  }

  p {
    margin: 0;
    font-size: 14px;
    line-height: 1.7;
    color: #48675f;
  }
}

.card-badge {
  display: inline-flex;
  padding: 6px 12px;
  border-radius: 999px;
  background: #e7f7f1;
  color: #11785c;
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.05em;
  text-transform: uppercase;
}

.header-side {
  min-width: 138px;
  padding: 14px 16px;
  border-radius: 20px;
  background: linear-gradient(160deg, #0d5c49 0%, #159a75 100%);
  color: white;
  text-align: center;

  strong {
    display: block;
    margin-top: 6px;
    font-size: 24px;
    line-height: 1.2;
  }
}

.side-label {
  font-size: 12px;
  color: rgba(255, 255, 255, 0.76);
}

.content-grid {
  display: grid;
  grid-template-columns: minmax(0, 1.6fr) minmax(0, 1fr);
  gap: 16px;
  margin-top: 18px;
}

.side-grid {
  display: grid;
  gap: 16px;
}

.content-block {
  padding: 18px;
  border-radius: 20px;
  border: 1px solid #dbe8e1;
  background: rgba(255, 255, 255, 0.84);
}

.block-header {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 14px;

  h4 {
    margin: 0;
    font-size: 15px;
    color: #124a3d;
  }
}

.block-dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;

  &.primary {
    background: #169a76;
    box-shadow: 0 0 0 4px rgba(22, 154, 118, 0.12);
  }

  &.success {
    background: #287c52;
    box-shadow: 0 0 0 4px rgba(40, 124, 82, 0.12);
  }

  &.warning {
    background: #d05c46;
    box-shadow: 0 0 0 4px rgba(208, 92, 70, 0.12);
  }
}

.qa-list {
  display: grid;
  gap: 12px;
}

.qa-item {
  padding: 14px;
  border-radius: 18px;
  border: 1px solid #dcece5;
  background: linear-gradient(180deg, #ffffff 0%, #f6fbf9 100%);

  h5 {
    margin: 10px 0 8px;
    font-size: 15px;
    color: #124a3d;
    line-height: 1.6;
  }

  p {
    margin: 0;
    color: #506760;
    font-size: 13px;
    line-height: 1.7;
  }

  p + p {
    margin-top: 6px;
  }
}

.qa-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.action-row {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
  margin-top: 16px;
}

.action-btn {
  border: 0;
  padding: 10px 14px;
  border-radius: 14px;
  background: linear-gradient(135deg, #11785c 0%, #169a76 100%);
  color: white;
  font-size: 13px;
  font-weight: 700;
  cursor: pointer;

  &.secondary {
    background: #e8f7f1;
    color: #11785c;
  }

  &.secondary-alt {
    background: #edf4ff;
    color: #1b65ca;
  }
}

.dimension-pill,
.qa-index {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  height: 26px;
  padding: 0 10px;
  border-radius: 999px;
  font-size: 12px;
  font-weight: 700;
}

.dimension-pill {
  background: #e8f7f1;
  color: #11785c;
}

.qa-index {
  background: #eff6f3;
  color: #3c5b53;
}

.unordered-list {
  margin: 0;
  padding-left: 20px;
  color: #4b635c;
  font-size: 14px;
  line-height: 1.75;
}

.unordered-list li + li {
  margin-top: 8px;
}

.risk-block {
  border-color: #edd6d2;
  background: rgba(255, 250, 249, 0.9);
}

@media (max-width: 768px) {
  .card-header {
    flex-direction: column;
  }

  .header-side {
    width: 100%;
  }

  .content-grid {
    grid-template-columns: 1fr;
  }

  .action-row {
    flex-direction: column;
  }
}
</style>
