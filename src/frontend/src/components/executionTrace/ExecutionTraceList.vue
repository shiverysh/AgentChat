<script setup lang="ts">
import type { ExecutionRecord, ExecutionRecordKind } from '../../type'

const props = defineProps<{
  records: ExecutionRecord[]
}>()

const kindLabelMap: Record<ExecutionRecordKind, string> = {
  tool: '工具',
  mcp: 'MCP',
  skill: 'Skill',
  mcp_tool: 'MCP 工具',
  skill_tool: 'Skill 工具',
}

function getKindLabel(kind: ExecutionRecordKind) {
  return kindLabelMap[kind] || '执行'
}

function getDisplayTitle(record: ExecutionRecord) {
  if ((record.kind === 'mcp_tool' || record.kind === 'skill_tool') && record.parentName) {
    return `${record.parentName} / ${record.name}`
  }
  return record.name
}

function getStatusLabel(status: ExecutionRecord['status']) {
  if (status === 'START') return '执行中'
  if (status === 'END') return '已完成'
  return '失败'
}
</script>

<template>
  <section class="execution-trace-list">
    <div class="trace-list-header">
      <span class="trace-list-badge">Agent Trace</span>
      <strong>执行轨迹</strong>
      <span class="trace-list-count">{{ props.records.length }}</span>
    </div>

    <div
      v-for="record in props.records"
      :key="record.id"
      class="trace-row"
      :class="[`status-${record.status.toLowerCase()}`, `kind-${record.kind}`]"
    >
      <div class="trace-row-head">
        <span class="trace-kind">{{ getKindLabel(record.kind) }}</span>
        <span class="trace-title">{{ getDisplayTitle(record) }}</span>
        <span class="trace-status">{{ getStatusLabel(record.status) }}</span>
      </div>
      <p v-if="record.message" class="trace-message">{{ record.message }}</p>
    </div>
  </section>
</template>

<style scoped lang="scss">
.execution-trace-list {
  display: grid;
  gap: 10px;
  margin-bottom: 12px;
  padding: 16px;
  border-radius: 20px;
  border: 1px solid #dbe5f1;
  background: linear-gradient(180deg, #fdfefe 0%, #f5f9ff 100%);
  box-shadow: 0 12px 24px rgba(92, 120, 158, 0.08);
}

.trace-list-header {
  display: flex;
  align-items: center;
  gap: 10px;

  strong {
    color: #17345f;
    font-size: 15px;
  }
}

.trace-list-badge {
  display: inline-flex;
  padding: 5px 10px;
  border-radius: 999px;
  background: #eaf2ff;
  color: #1b65ca;
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.04em;
  text-transform: uppercase;
}

.trace-list-count {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 22px;
  height: 22px;
  padding: 0 8px;
  border-radius: 999px;
  background: #17345f;
  color: white;
  font-size: 12px;
  font-weight: 700;
}

.trace-row {
  padding: 12px 14px;
  border-radius: 16px;
  border: 1px solid #dfe8f4;
  background: rgba(255, 255, 255, 0.92);
}

.trace-row-head {
  display: flex;
  align-items: center;
  gap: 10px;
}

.trace-kind {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  height: 24px;
  padding: 0 10px;
  border-radius: 999px;
  background: #edf4ff;
  color: #1f5fb7;
  font-size: 12px;
  font-weight: 700;
}

.trace-title {
  flex: 1;
  min-width: 0;
  font-size: 14px;
  font-weight: 700;
  color: #17345f;
  word-break: break-word;
}

.trace-status {
  flex-shrink: 0;
  padding: 4px 9px;
  border-radius: 999px;
  font-size: 12px;
  font-weight: 700;
}

.trace-message {
  margin: 10px 0 0;
  color: #5d6b7f;
  font-size: 13px;
  line-height: 1.6;
  display: -webkit-box;
  -webkit-line-clamp: 3;
  -webkit-box-orient: vertical;
  overflow: hidden;
  word-break: break-word;
}

.status-start {
  border-color: #cfe1ff;
  background: linear-gradient(180deg, #ffffff 0%, #f5f9ff 100%);

  .trace-status {
    background: #eaf3ff;
    color: #1f6fd6;
  }
}

.status-end {
  border-color: #d6ead8;
  background: linear-gradient(180deg, #ffffff 0%, #f7fdf8 100%);

  .trace-status {
    background: #e8f7ea;
    color: #2d8a45;
  }
}

.status-error {
  border-color: #f3d2d5;
  background: linear-gradient(180deg, #ffffff 0%, #fff8f8 100%);

  .trace-status {
    background: #fdeced;
    color: #c44d56;
  }
}

@media (max-width: 768px) {
  .trace-row-head {
    flex-wrap: wrap;
  }

  .trace-title {
    width: 100%;
  }
}
</style>
