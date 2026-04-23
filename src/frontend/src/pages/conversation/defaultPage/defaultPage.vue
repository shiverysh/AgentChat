<script setup lang="ts">
import { computed, onMounted, ref } from "vue"
import { useRouter } from "vue-router"
import { ElMessage } from "element-plus"

import { getAgentsAPI, type AgentResponse } from "../../../apis/agent"
import { createDialogAPI, getDialogListAPI } from "../../../apis/history"
import { useHistoryChatStore } from "../../../store/history_chat_msg"
import {
  JOB_ASSISTANT_DESCRIPTION,
  JOB_ASSISTANT_HIGHLIGHTS,
  JOB_ASSISTANT_NAME,
  JOB_ASSISTANT_QUICK_PROMPTS,
  isJobAssistantAgentName
} from "../../../constants/jobAssistant"

const router = useRouter()
const historyChatStore = useHistoryChatStore()

const shouldShow = ref(false)
const loading = ref(true)
const agents = ref<AgentResponse[]>([])

const featuredAgent = computed(() => {
  return agents.value.find(agent => isJobAssistantAgentName(agent.name)) || null
})

const getAgentIdentifier = (agent: AgentResponse) => {
  return String((agent as any).id || agent.agent_id)
}

const fetchAgents = async () => {
  try {
    const response = await getAgentsAPI()
    if (response.data.status_code === 200) {
      agents.value = response.data.data
    }
  } catch (error) {
    console.error("获取智能体列表失败:", error)
  }
}

const startJobAssistant = async (initialMessage = "") => {
  if (!featuredAgent.value) {
    await fetchAgents()
  }

  const agent = agents.value.find(item => isJobAssistantAgentName(item.name))
  if (!agent) {
    ElMessage.warning(`${JOB_ASSISTANT_NAME} 尚未初始化，请先确认后端默认 Agent 已同步`)
    return
  }

  try {
    const dialogName = `与${agent.name}的对话`
    const response = await createDialogAPI({
      name: dialogName,
      agent_id: getAgentIdentifier(agent),
      agent_type: "Agent"
    })

    if (response.data.status_code !== 200) {
      ElMessage.error(response.data.status_message || "创建会话失败")
      return
    }

    const dialogId = response.data.data.dialog_id
    if (!dialogId) {
      ElMessage.error("会话创建成功，但未返回会话 ID")
      return
    }

    historyChatStore.dialogId = dialogId
    historyChatStore.name = dialogName
    historyChatStore.logo = agent.logo_url

    router.push({
      path: "/conversation/chatPage",
      query: {
        dialog_id: dialogId,
        ...(initialMessage ? { message: initialMessage } : {})
      }
    })
  } catch (error) {
    console.error("创建求职面试助手会话失败:", error)
    ElMessage.error("创建会话失败，请稍后重试")
  }
}

const openAgentPage = () => {
  router.push("/agent")
}

onMounted(async () => {
  try {
    const response = await getDialogListAPI()
    if (response.data.status_code === 200 && response.data.data && response.data.data.length > 0) {
      return
    }
    shouldShow.value = true
    await fetchAgents()
  } catch (_) {
    shouldShow.value = true
    await fetchAgents()
  } finally {
    loading.value = false
  }
})
</script>

<template>
  <div v-if="shouldShow" class="default-page">
    <div class="hero-panel">
      <div class="hero-copy">
        <span class="eyebrow">Job-Focused Agent Experience</span>
        <h1 class="title">{{ JOB_ASSISTANT_NAME }}</h1>
        <p class="description">
          {{ JOB_ASSISTANT_DESCRIPTION }}
        </p>

        <div class="highlight-list">
          <div
            v-for="item in JOB_ASSISTANT_HIGHLIGHTS"
            :key="item"
            class="highlight-item"
          >
            <span class="highlight-dot"></span>
            <span>{{ item }}</span>
          </div>
        </div>

        <div class="hero-actions">
          <button class="primary-btn" @click="startJobAssistant()">
            进入助手
          </button>
          <button class="secondary-btn" @click="openAgentPage">
            查看全部智能体
          </button>
        </div>

        <p v-if="!loading && !featuredAgent" class="status-note">
          当前前端入口已就绪，但还未检测到默认 Agent。请先确认后端初始化是否已创建“求职面试助手”。
        </p>
      </div>

      <div class="hero-preview">
        <div class="preview-card">
          <div class="preview-header">
            <span class="preview-badge">结构化输出</span>
            <span class="preview-score">82 / 100</span>
          </div>
          <div class="preview-body">
            <div class="preview-row">
              <span class="row-label">匹配优势</span>
              <span class="row-value">Agent 项目经验 / Tool 调用链路</span>
            </div>
            <div class="preview-row">
              <span class="row-label">主要缺口</span>
              <span class="row-value">MCP 实战 / 指标量化表达</span>
            </div>
            <div class="preview-row">
              <span class="row-label">下一步</span>
              <span class="row-value">补充项目结果与面试问答框架</span>
            </div>
          </div>
        </div>
      </div>
    </div>

    <div class="prompt-section">
      <div class="section-head">
        <h2>快捷演示入口</h2>
        <p>直接带着预置问题进入对话，适合本地演示和面试准备。</p>
      </div>

      <div class="prompt-grid">
        <button
          v-for="item in JOB_ASSISTANT_QUICK_PROMPTS"
          :key="item.label"
          class="prompt-card"
          @click="startJobAssistant(item.prompt)"
        >
          <div class="prompt-card-header">
            <span class="prompt-title">{{ item.label }}</span>
            <span class="prompt-short">{{ item.shortLabel }}</span>
          </div>
          <p class="prompt-description">{{ item.description }}</p>
          <span class="prompt-action">一键进入</span>
        </button>
      </div>
    </div>
  </div>
</template>

<style lang="scss" scoped>
.default-page {
  min-height: 100%;
  padding: 36px;
  background:
    radial-gradient(circle at top right, rgba(255, 236, 194, 0.32), transparent 26%),
    radial-gradient(circle at bottom left, rgba(181, 214, 255, 0.28), transparent 24%),
    linear-gradient(180deg, #f8fbff 0%, #f6f8fc 100%);
  overflow-y: auto;
}

.hero-panel {
  display: grid;
  grid-template-columns: minmax(0, 1.2fr) minmax(280px, 0.8fr);
  gap: 24px;
  padding: 28px;
  border-radius: 28px;
  background: rgba(255, 255, 255, 0.86);
  border: 1px solid rgba(205, 217, 234, 0.8);
  box-shadow: 0 22px 44px rgba(46, 75, 117, 0.08);
}

.hero-copy {
  display: flex;
  flex-direction: column;
}

.eyebrow {
  display: inline-flex;
  align-self: flex-start;
  padding: 6px 12px;
  border-radius: 999px;
  background: #ebf3ff;
  color: #1858ab;
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.04em;
  text-transform: uppercase;
}

.title {
  margin: 16px 0 10px;
  font-size: 40px;
  line-height: 1.05;
  color: #152641;
}

.description {
  margin: 0;
  max-width: 680px;
  font-size: 16px;
  line-height: 1.7;
  color: #516076;
}

.highlight-list {
  display: grid;
  gap: 12px;
  margin-top: 24px;
}

.highlight-item {
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 14px;
  color: #30445f;
}

.highlight-dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  background: linear-gradient(135deg, #1f6fd6 0%, #d9a441 100%);
  box-shadow: 0 0 0 4px rgba(31, 111, 214, 0.1);
}

.hero-actions {
  display: flex;
  gap: 12px;
  margin-top: 28px;
}

.primary-btn,
.secondary-btn,
.prompt-card {
  border: none;
  cursor: pointer;
}

.primary-btn,
.secondary-btn {
  height: 46px;
  padding: 0 18px;
  border-radius: 14px;
  font-size: 14px;
  font-weight: 600;
  transition: transform 0.2s ease, box-shadow 0.2s ease, background 0.2s ease;
}

.primary-btn {
  background: linear-gradient(135deg, #155fc3 0%, #4c9de4 100%);
  color: white;

  &:hover {
    transform: translateY(-1px);
    box-shadow: 0 12px 24px rgba(21, 95, 195, 0.2);
  }
}

.secondary-btn {
  background: #f2f6fb;
  color: #365071;
  border: 1px solid #d9e3f1;

  &:hover {
    background: #eaf1f9;
  }
}

.status-note {
  margin-top: 14px;
  font-size: 13px;
  color: #856404;
}

.hero-preview {
  display: flex;
  align-items: stretch;
}

.preview-card {
  width: 100%;
  padding: 20px;
  border-radius: 24px;
  background: linear-gradient(165deg, #17345f 0%, #1f4d8f 54%, #245fba 100%);
  color: white;
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.15);
}

.preview-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.preview-badge {
  padding: 4px 10px;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.12);
  font-size: 12px;
  font-weight: 700;
}

.preview-score {
  font-size: 22px;
  font-weight: 700;
}

.preview-body {
  display: grid;
  gap: 14px;
  margin-top: 20px;
}

.preview-row {
  padding: 14px;
  border-radius: 16px;
  background: rgba(255, 255, 255, 0.08);
}

.row-label {
  display: block;
  margin-bottom: 6px;
  font-size: 12px;
  color: rgba(255, 255, 255, 0.72);
}

.row-value {
  font-size: 14px;
  line-height: 1.55;
}

.prompt-section {
  margin-top: 24px;
  padding: 24px 28px 28px;
  border-radius: 28px;
  background: rgba(255, 255, 255, 0.92);
  border: 1px solid rgba(214, 223, 235, 0.8);
}

.section-head h2 {
  margin: 0;
  font-size: 24px;
  color: #1d2f4b;
}

.section-head p {
  margin: 8px 0 0;
  color: #5d6b7f;
  font-size: 14px;
}

.prompt-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 16px;
  margin-top: 18px;
}

.prompt-card {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  padding: 18px;
  border-radius: 20px;
  background: linear-gradient(180deg, #f8fbff 0%, #eef4fb 100%);
  border: 1px solid #d8e3f0;
  text-align: left;
  transition: transform 0.2s ease, box-shadow 0.2s ease, border-color 0.2s ease;

  &:hover {
    transform: translateY(-2px);
    border-color: #8db5eb;
    box-shadow: 0 16px 30px rgba(65, 119, 186, 0.12);
  }
}

.prompt-card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  width: 100%;
  gap: 10px;
}

.prompt-title {
  font-size: 16px;
  font-weight: 700;
  color: #17345f;
}

.prompt-short {
  padding: 3px 8px;
  border-radius: 999px;
  background: white;
  color: #5d7293;
  font-size: 12px;
  font-weight: 700;
}

.prompt-description {
  margin: 12px 0 18px;
  font-size: 14px;
  line-height: 1.65;
  color: #54657d;
}

.prompt-action {
  font-size: 13px;
  font-weight: 700;
  color: #1b65ca;
}

@media (max-width: 1024px) {
  .hero-panel {
    grid-template-columns: 1fr;
  }

  .prompt-grid {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 768px) {
  .default-page {
    padding: 18px;
  }

  .hero-panel,
  .prompt-section {
    padding: 20px;
  }

  .title {
    font-size: 32px;
  }

  .hero-actions {
    flex-direction: column;
  }

  .primary-btn,
  .secondary-btn {
    width: 100%;
  }
}
</style>
