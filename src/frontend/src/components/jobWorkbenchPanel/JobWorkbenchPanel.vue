<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'

import type { JobWorkbenchData, JobWorkbenchItem, JobWorkbenchItemType } from '../../type'

const props = defineProps<{
  data: JobWorkbenchData | null
  loading?: boolean
}>()

const emit = defineEmits<{
  refresh: []
}>()

const typeMetaMap: Record<JobWorkbenchItemType, { title: string; empty: string }> = {
  resume_version: {
    title: '简历版本',
    empty: '还没有保存的简历版本',
  },
  job_application: {
    title: '投递记录',
    empty: '还没有岗位投递记录',
  },
  interview_plan: {
    title: '面试计划',
    empty: '还没有面试准备计划',
  },
  followup_note: {
    title: '追问笔记',
    empty: '还没有追问笔记',
  },
}

const groupedItems = computed(() => {
  const items = props.data?.items || []
  const groups: Record<JobWorkbenchItemType, JobWorkbenchItem[]> = {
    resume_version: [],
    job_application: [],
    interview_plan: [],
    followup_note: [],
  }

  items.forEach(item => {
    groups[item.item_type]?.push(item)
  })

  return groups
})

const orderedItemTypes = computed<JobWorkbenchItemType[]>(() => [
  'resume_version',
  'job_application',
  'interview_plan',
  'followup_note',
])

const collapseStorageKey = 'job_workbench_panel_collapsed'
const isCollapsed = ref(true)

const recentItems = computed(() => {
  const items = props.data?.items || []
  return items.slice(0, 4)
})

const hasWorkbenchContent = computed(() => {
  return Number(props.data?.stats.total || 0) > 0
})

const toggleCollapsed = () => {
  isCollapsed.value = !isCollapsed.value
}

onMounted(() => {
  const cached = window.localStorage.getItem(collapseStorageKey)
  if (cached === null) {
    isCollapsed.value = true
    return
  }
  isCollapsed.value = cached === 'true'
})

watch(isCollapsed, value => {
  window.localStorage.setItem(collapseStorageKey, String(value))
})
</script>

<template>
  <section class="job-workbench-panel" :class="{ collapsed: isCollapsed }">
    <div class="panel-head">
      <div>
        <span class="panel-badge">MCP Workbench</span>
        <h3>求职工作台</h3>
        <p>
          {{
            isCollapsed
              ? '已折叠为紧凑视图，只保留统计与最近记录摘要。'
              : '这里展示通过 MCP 保存下来的简历版本、投递记录、面试计划和追问笔记。'
          }}
        </p>
      </div>
      <div class="panel-actions">
        <button class="toggle-btn" type="button" @click="toggleCollapsed">
          <span class="toggle-icon">{{ isCollapsed ? '▸' : '▾' }}</span>
          <span>{{ isCollapsed ? '展开工作台' : '收起工作台' }}</span>
        </button>
        <button class="refresh-btn" type="button" @click="emit('refresh')">
          刷新
        </button>
      </div>
    </div>

    <div class="stats-row">
      <span class="stat-pill">总数 {{ props.data?.stats.total || 0 }}</span>
      <span class="stat-pill">版本 {{ props.data?.stats.resume_version || 0 }}</span>
      <span class="stat-pill">投递 {{ props.data?.stats.job_application || 0 }}</span>
      <span class="stat-pill">计划 {{ props.data?.stats.interview_plan || 0 }}</span>
      <span class="stat-pill">笔记 {{ props.data?.stats.followup_note || 0 }}</span>
    </div>

    <div v-if="props.loading" class="loading-state">
      正在刷新工作台内容...
    </div>

    <div v-else-if="isCollapsed" class="collapsed-summary">
      <div v-if="hasWorkbenchContent" class="summary-list">
        <article
          v-for="item in recentItems"
          :key="item.id"
          class="summary-item"
        >
          <div class="summary-item__type">{{ typeMetaMap[item.item_type].title }}</div>
          <div class="summary-item__title" :title="item.title">{{ item.title }}</div>
          <div class="summary-item__meta">
            <span v-if="item.status">{{ item.status }}</span>
            <span v-if="item.display_time">{{ item.display_time }}</span>
          </div>
        </article>
      </div>
      <div v-else class="empty-state">
        当前工作台还没有内容，后续通过工具写入后会展示在这里。
      </div>
    </div>

    <div v-else class="panel-grid">
      <section
        v-for="itemType in orderedItemTypes"
        :key="itemType"
        class="panel-section"
      >
        <div class="section-head">
          <strong>{{ typeMetaMap[itemType].title }}</strong>
          <span>{{ groupedItems[itemType].length }}</span>
        </div>

        <div v-if="groupedItems[itemType].length" class="item-list">
          <article
            v-for="item in groupedItems[itemType].slice(0, 3)"
            :key="item.id"
            class="workbench-item"
          >
            <div class="item-head">
              <strong>{{ item.title }}</strong>
              <span>{{ item.display_time || '' }}</span>
            </div>
            <p v-if="item.summary" class="item-summary">{{ item.summary }}</p>
            <div v-if="item.status || item.tags?.length" class="item-meta">
              <span v-if="item.status" class="meta-pill status">{{ item.status }}</span>
              <span
                v-for="tag in item.tags || []"
                :key="`${item.id}-${tag}`"
                class="meta-pill"
              >
                {{ tag }}
              </span>
            </div>
          </article>
        </div>

        <div v-else class="empty-state">
          {{ typeMetaMap[itemType].empty }}
        </div>
      </section>
    </div>
  </section>
</template>

<style scoped lang="scss">
.job-workbench-panel {
  margin-bottom: 20px;
  padding: 22px;
  border-radius: 24px;
  border: 1px solid #d8e3ef;
  background:
    radial-gradient(circle at top left, rgba(212, 235, 255, 0.42), transparent 28%),
    linear-gradient(180deg, #ffffff 0%, #f5f9ff 100%);
  box-shadow: 0 18px 36px rgba(73, 109, 161, 0.08);
}

.panel-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;

  h3 {
    margin: 12px 0 8px;
    color: #17345f;
    font-size: 24px;
  }

  p {
    margin: 0;
    color: #5a6c84;
    font-size: 14px;
    line-height: 1.7;
  }
}

.panel-actions {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
  flex-shrink: 0;
}

.panel-badge {
  display: inline-flex;
  padding: 6px 12px;
  border-radius: 999px;
  background: #eaf2ff;
  color: #1b65ca;
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.05em;
  text-transform: uppercase;
}

.toggle-btn,
.refresh-btn {
  border: 0;
  padding: 10px 14px;
  border-radius: 14px;
  font-size: 13px;
  font-weight: 700;
  cursor: pointer;
}

.toggle-btn {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  background: #eef4ff;
  color: #17345f;
}

.toggle-icon {
  font-size: 12px;
}

.refresh-btn {
  background: #17345f;
  color: white;
}

.stats-row {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  margin-top: 18px;
}

.stat-pill {
  display: inline-flex;
  align-items: center;
  padding: 8px 12px;
  border-radius: 999px;
  background: #f0f5fb;
  color: #304763;
  font-size: 13px;
  font-weight: 700;
}

.loading-state,
.empty-state {
  color: #687b92;
  font-size: 13px;
  line-height: 1.6;
}

.loading-state {
  margin-top: 18px;
}

.collapsed-summary {
  margin-top: 18px;
}

.summary-list {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: 12px;
}

.summary-item {
  padding: 14px;
  border-radius: 18px;
  border: 1px solid #e1eaf5;
  background: rgba(255, 255, 255, 0.88);
}

.summary-item__type {
  margin-bottom: 8px;
  font-size: 11px;
  font-weight: 700;
  color: #1b65ca;
  letter-spacing: 0.04em;
  text-transform: uppercase;
}

.summary-item__title {
  color: #17345f;
  font-size: 14px;
  font-weight: 700;
  line-height: 1.5;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.summary-item__meta {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 10px;
  color: #708297;
  font-size: 12px;
}

.panel-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 16px;
  margin-top: 18px;
}

.panel-section {
  padding: 16px;
  border-radius: 20px;
  border: 1px solid #e1eaf5;
  background: rgba(255, 255, 255, 0.82);
}

.section-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  margin-bottom: 12px;

  strong {
    color: #17345f;
    font-size: 15px;
  }

  span {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    min-width: 24px;
    height: 24px;
    padding: 0 8px;
    border-radius: 999px;
    background: #edf4ff;
    color: #1b65ca;
    font-size: 12px;
    font-weight: 700;
  }
}

.item-list {
  display: grid;
  gap: 10px;
}

.workbench-item {
  padding: 12px;
  border-radius: 16px;
  border: 1px solid #e5edf6;
  background: linear-gradient(180deg, #ffffff 0%, #f8fbff 100%);
}

.item-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 10px;

  strong {
    color: #17345f;
    font-size: 14px;
    line-height: 1.5;
  }

  span {
    flex-shrink: 0;
    color: #8091a7;
    font-size: 12px;
  }
}

.item-summary {
  margin: 8px 0 0;
  color: #5f7086;
  font-size: 13px;
  line-height: 1.6;
}

.item-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 10px;
}

.meta-pill {
  display: inline-flex;
  align-items: center;
  padding: 6px 10px;
  border-radius: 999px;
  background: #f3f6fa;
  color: #58718b;
  font-size: 12px;
  font-weight: 700;

  &.status {
    background: #e6f5eb;
    color: #2c7a4b;
  }
}

@media (max-width: 768px) {
  .panel-head {
    flex-direction: column;
  }

  .panel-actions {
    width: 100%;
  }

  .panel-grid {
    grid-template-columns: 1fr;
  }

  .summary-list {
    grid-template-columns: 1fr;
  }
}
</style>
