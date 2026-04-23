<script setup lang="ts">
import { computed } from 'vue'

import type { ResumeMatchResult } from '../../type'

const props = defineProps<{
  result: ResumeMatchResult
}>()

const emit = defineEmits<{
  recordApplication: [result: ResumeMatchResult]
}>()

const scoreWidth = computed(() => {
  const value = Math.max(0, Math.min(100, props.result.match_score || 0))
  return `${value}%`
})

const scoreLevel = computed(() => {
  const score = props.result.match_score || 0
  if (score >= 80) return 'high'
  if (score >= 60) return 'medium'
  return 'low'
})

const scoreLabel = computed(() => {
  if (scoreLevel.value === 'high') return '较高匹配'
  if (scoreLevel.value === 'medium') return '中等匹配'
  return '需要补强'
})

const strengthItems = computed(() => {
  return props.result.matched_strengths.length
    ? props.result.matched_strengths
    : ['当前简历中已有部分相关背景，可进一步突出岗位关键词。']
})

const gapItems = computed(() => {
  return props.result.missing_requirements.length
    ? props.result.missing_requirements
    : ['暂未识别出明显缺口，建议继续补充结果指标与关键技术细节。']
})

const suggestionItems = computed(() => {
  return props.result.revision_suggestions.length
    ? props.result.revision_suggestions
    : ['优先补充与岗位关键词强相关的项目职责、技术栈和量化结果。']
})

const interviewItems = computed(() => {
  return props.result.interview_focus.length
    ? props.result.interview_focus
    : ['围绕项目背景、技术方案、效果指标和个人贡献整理面试回答。']
})
</script>

<template>
  <section class="resume-match-card" :class="`score-${scoreLevel}`">
    <div class="card-header">
      <div class="header-main">
        <span class="card-badge">Resume Match</span>
        <h3>{{ result.target_role }}</h3>
        <p>{{ result.overall_summary }}</p>
      </div>
      <div class="score-panel">
        <span class="score-label">{{ scoreLabel }}</span>
        <strong>{{ result.match_score }}</strong>
        <span class="score-unit">/ 100</span>
      </div>
    </div>

    <div class="score-bar">
      <div class="score-bar-fill" :style="{ width: scoreWidth }"></div>
    </div>

    <div class="content-grid">
      <section class="content-block strengths">
        <div class="block-header">
          <span class="block-dot"></span>
          <h4>匹配优势</h4>
        </div>
        <div class="pill-list">
          <span v-for="item in strengthItems" :key="item" class="pill success">
            {{ item }}
          </span>
        </div>
      </section>

      <section class="content-block gaps">
        <div class="block-header">
          <span class="block-dot"></span>
          <h4>主要缺口</h4>
        </div>
        <div class="pill-list">
          <span v-for="item in gapItems" :key="item" class="pill warning">
            {{ item }}
          </span>
        </div>
      </section>

      <section class="content-block suggestions">
        <div class="block-header">
          <span class="block-dot"></span>
          <h4>简历修改建议</h4>
        </div>
        <ol class="ordered-list">
          <li v-for="item in suggestionItems" :key="item">{{ item }}</li>
        </ol>
      </section>

      <section class="content-block interview">
        <div class="block-header">
          <span class="block-dot"></span>
          <h4>面试准备重点</h4>
        </div>
        <ul class="unordered-list">
          <li v-for="item in interviewItems" :key="item">{{ item }}</li>
        </ul>
      </section>
    </div>

    <div class="action-row">
      <button type="button" class="action-btn" @click="emit('recordApplication', result)">
        记录岗位投递
      </button>
    </div>
  </section>
</template>

<style lang="scss" scoped>
.resume-match-card {
  width: min(920px, 100%);
  padding: 22px;
  border-radius: 24px;
  border: 1px solid #dbe5f1;
  background:
    radial-gradient(circle at top right, rgba(255, 235, 199, 0.36), transparent 30%),
    linear-gradient(180deg, #ffffff 0%, #f8fbff 100%);
  box-shadow: 0 16px 32px rgba(83, 112, 150, 0.1);
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
    color: #17345f;
  }

  p {
    margin: 0;
    font-size: 14px;
    line-height: 1.7;
    color: #59687d;
  }
}

.card-badge {
  display: inline-flex;
  padding: 6px 12px;
  border-radius: 999px;
  background: #edf4ff;
  color: #1b65ca;
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.05em;
  text-transform: uppercase;
}

.score-panel {
  min-width: 120px;
  padding: 14px 16px;
  border-radius: 20px;
  background: #17345f;
  color: white;
  text-align: center;

  strong {
    display: inline-block;
    margin-top: 6px;
    font-size: 34px;
    line-height: 1;
  }
}

.score-label,
.score-unit {
  display: block;
}

.score-label {
  font-size: 12px;
  color: rgba(255, 255, 255, 0.72);
}

.score-unit {
  margin-top: 4px;
  font-size: 12px;
  color: rgba(255, 255, 255, 0.72);
}

.score-bar {
  height: 10px;
  margin-top: 18px;
  border-radius: 999px;
  background: #e8eef7;
  overflow: hidden;
}

.score-bar-fill {
  height: 100%;
  border-radius: inherit;
  background: linear-gradient(90deg, #3b82f6 0%, #66b3ff 45%, #f0bf5a 100%);
}

.content-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 16px;
  margin-top: 18px;
}

.content-block {
  min-height: 180px;
  padding: 18px;
  border-radius: 20px;
  border: 1px solid #e3ebf5;
  background: rgba(255, 255, 255, 0.78);
}

.block-header {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 14px;

  h4 {
    margin: 0;
    font-size: 15px;
    color: #17345f;
  }
}

.block-dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  background: linear-gradient(135deg, #1f6fd6 0%, #d9a441 100%);
}

.pill-list {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
}

.pill {
  display: inline-flex;
  padding: 9px 12px;
  border-radius: 14px;
  font-size: 13px;
  line-height: 1.5;
}

.action-row {
  display: flex;
  justify-content: flex-end;
  margin-top: 16px;
}

.action-btn {
  border: 0;
  padding: 10px 14px;
  border-radius: 14px;
  background: linear-gradient(135deg, #1b65ca 0%, #3b82f6 100%);
  color: white;
  font-size: 13px;
  font-weight: 700;
  cursor: pointer;
}

.pill.success {
  background: #eef8f2;
  color: #19653d;
}

.pill.warning {
  background: #fff4ea;
  color: #9b5f12;
}

.ordered-list,
.unordered-list {
  margin: 0;
  padding-left: 18px;
  display: grid;
  gap: 10px;
  color: #495a71;
  font-size: 13px;
  line-height: 1.65;
}

.score-low .score-panel {
  background: #7b2f18;
}

.score-medium .score-panel {
  background: #7c5b10;
}

.score-high .score-panel {
  background: #17345f;
}

@media (max-width: 768px) {
  .resume-match-card {
    padding: 18px;
  }

  .card-header {
    flex-direction: column;
  }

  .score-panel {
    width: 100%;
  }

  .content-grid {
    grid-template-columns: 1fr;
  }
}
</style>
