<script setup lang="ts">
import { computed } from 'vue'

import type { ResumeRewriteResult } from '../../type'

const props = defineProps<{
  result: ResumeRewriteResult
}>()

const emit = defineEmits<{
  saveVersion: [result: ResumeRewriteResult]
  syncFeishuDoc: [result: ResumeRewriteResult]
}>()

const issueItems = computed(() => {
  return props.result.detected_issues.length
    ? props.result.detected_issues
    : ['当前描述偏泛，建议补足项目场景、技术方案和结果指标。']
})

const rewrittenItems = computed(() => {
  return props.result.rewritten_resume.length
    ? props.result.rewritten_resume
    : ['请补充更具体的个人贡献、技术细节和量化结果后再生成改写版本。']
})

const supplementItems = computed(() => {
  return props.result.supplement_suggestions.length
    ? props.result.supplement_suggestions
    : ['优先补充业务指标、技术决策依据和你的实际贡献。']
})

const keywordItems = computed(() => {
  return props.result.highlight_keywords.length
    ? props.result.highlight_keywords
    : ['Agent', 'Tool Calling', 'RAG', '工作流编排']
})
</script>

<template>
  <section class="resume-rewrite-card">
    <div class="card-header">
      <div class="header-main">
        <span class="card-badge">Resume Rewrite</span>
        <h3>{{ result.target_role }}</h3>
        <p>{{ result.overall_strategy }}</p>
      </div>
      <div class="header-side">
        <span class="side-label">输出形态</span>
        <strong>可直接复用</strong>
      </div>
    </div>

    <section class="rewrite-block rewritten-block">
      <div class="block-header">
        <span class="block-dot primary"></span>
        <h4>改写版本</h4>
      </div>
      <ol class="ordered-list">
        <li v-for="item in rewrittenItems" :key="item">{{ item }}</li>
      </ol>
    </section>

    <div class="content-grid">
      <section class="rewrite-block">
        <div class="block-header">
          <span class="block-dot warning"></span>
          <h4>当前问题</h4>
        </div>
        <ul class="unordered-list">
          <li v-for="item in issueItems" :key="item">{{ item }}</li>
        </ul>
      </section>

      <section class="rewrite-block">
        <div class="block-header">
          <span class="block-dot success"></span>
          <h4>建议补充</h4>
        </div>
        <ul class="unordered-list">
          <li v-for="item in supplementItems" :key="item">{{ item }}</li>
        </ul>
      </section>
    </div>

    <section class="keyword-strip">
      <span class="keyword-label">建议强化关键词</span>
      <div class="keyword-list">
        <span v-for="item in keywordItems" :key="item" class="keyword-pill">
          {{ item }}
        </span>
      </div>
    </section>

    <div class="action-row">
      <button type="button" class="action-btn secondary" @click="emit('syncFeishuDoc', result)">
        同步到飞书文档
      </button>
      <button type="button" class="action-btn" @click="emit('saveVersion', result)">
        保存到求职工作台
      </button>
    </div>
  </section>
</template>

<style scoped lang="scss">
.resume-rewrite-card {
  width: min(920px, 100%);
  padding: 22px;
  border-radius: 24px;
  border: 1px solid #eadfcf;
  background:
    radial-gradient(circle at top left, rgba(255, 229, 184, 0.34), transparent 30%),
    linear-gradient(180deg, #fffdf8 0%, #f9fbff 100%);
  box-shadow: 0 16px 32px rgba(123, 101, 61, 0.1);
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
    color: #5a2e0f;
  }

  p {
    margin: 0;
    font-size: 14px;
    line-height: 1.7;
    color: #6e5b49;
  }
}

.card-badge {
  display: inline-flex;
  padding: 6px 12px;
  border-radius: 999px;
  background: #fff1d6;
  color: #b26711;
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.05em;
  text-transform: uppercase;
}

.header-side {
  min-width: 138px;
  padding: 14px 16px;
  border-radius: 20px;
  background: linear-gradient(160deg, #7d531f 0%, #b97818 100%);
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

.rewrite-block {
  padding: 18px;
  border-radius: 20px;
  border: 1px solid #ecdfcf;
  background: rgba(255, 255, 255, 0.82);
}

.rewritten-block {
  margin-top: 18px;
}

.content-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 16px;
  margin-top: 16px;
}

.block-header {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 14px;

  h4 {
    margin: 0;
    font-size: 15px;
    color: #5a2e0f;
  }
}

.block-dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;

  &.primary {
    background: #c48317;
    box-shadow: 0 0 0 4px rgba(196, 131, 23, 0.12);
  }

  &.warning {
    background: #d97706;
    box-shadow: 0 0 0 4px rgba(217, 119, 6, 0.12);
  }

  &.success {
    background: #2f855a;
    box-shadow: 0 0 0 4px rgba(47, 133, 90, 0.12);
  }
}

.ordered-list,
.unordered-list {
  margin: 0;
  padding-left: 20px;
  color: #55463b;
  font-size: 14px;
  line-height: 1.75;
}

.ordered-list li + li,
.unordered-list li + li {
  margin-top: 8px;
}

.keyword-strip {
  display: grid;
  gap: 10px;
  margin-top: 16px;
  padding: 16px 18px;
  border-radius: 20px;
  border: 1px solid #eee2d4;
  background: rgba(255, 250, 243, 0.86);
}

.keyword-label {
  font-size: 13px;
  font-weight: 700;
  color: #7a4d16;
}

.keyword-list {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
}

.keyword-pill {
  display: inline-flex;
  padding: 7px 12px;
  border-radius: 999px;
  background: #fff2de;
  color: #9a5a00;
  font-size: 12px;
  font-weight: 700;
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
  background: linear-gradient(135deg, #9a6317 0%, #c48317 100%);
  color: white;
  font-size: 13px;
  font-weight: 700;
  cursor: pointer;

  &.secondary {
    background: #fff7e8;
    color: #9a6317;
    border: 1px solid #efddb6;
  }
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
}
</style>
