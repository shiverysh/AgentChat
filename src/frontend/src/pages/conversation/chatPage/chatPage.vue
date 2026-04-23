<script setup lang="ts">
import { ref, onMounted, nextTick, watch, computed } from "vue"
import { useRoute, useRouter } from 'vue-router'
import { MdPreview } from "md-editor-v3"
import "md-editor-v3/lib/style.css"
import { sendMessage, type Chat } from "../../../apis/chat"
import { getJobHuntWorkbenchAPI } from "../../../apis/job-hunt-workbench"
import { getMCPServersAPI, type MCPServer } from "../../../apis/mcp-server"
import { useHistoryChatStore } from "../../../store/history_chat_msg"
import { useUserStore } from "../../../store/user"
import { ElScrollbar, ElInput, ElButton, ElMessage, ElUpload, ElIcon } from "element-plus"
import { UploadFilled, Promotion, Loading, VideoPause, Check, Close } from '@element-plus/icons-vue'
import ExecutionTraceList from "../../../components/executionTrace/ExecutionTraceList.vue"
import JobWorkbenchPanel from "../../../components/jobWorkbenchPanel/JobWorkbenchPanel.vue"
import ResumeMatchCard from "../../../components/resumeMatchCard/ResumeMatchCard.vue"
import ResumeRewriteCard from "../../../components/resumeRewriteCard/ResumeRewriteCard.vue"
import InterviewFollowupCard from "../../../components/interviewFollowupCard/InterviewFollowupCard.vue"
import {
  JOB_ASSISTANT_HIGHLIGHTS,
  JOB_ASSISTANT_NAME,
  JOB_ASSISTANT_QUICK_PROMPTS,
  isJobAssistantAgentName
} from "../../../constants/jobAssistant"
import { parseExecutionRecordFromEvent, upsertExecutionRecord } from "../../../utils/executionTrace"
import { appendToolOutputCard, hydrateToolOutputCardsFromMessage, parseToolOutputFromEvent } from "../../../utils/toolOutput"
import type {
  InterviewFollowupResult,
  JobWorkbenchData,
  ResumeMatchResult,
  ResumeRewriteResult,
} from "../../../type"

// Import static assets
import defaultUserAvatar from '../../../assets/user.svg';
import defaultRobotAvatar from '../../../assets/robot.svg';

// 使用与ChatMessage接口中定义的eventInfo类型一致的接口
interface EventInfo {
  event_type: string
  show: boolean
  status: string
  message: string
}

interface EventStatus {
  id: string
  event_type: string
  message: string
  status: 'START' | 'END' | 'ERROR'
  timestamp: number
  loading: boolean
  success: boolean
  error: boolean
}

const searchInput = ref("")
const sendQuestion = ref(true)
const historyChatStore = useHistoryChatStore()
const userStore = useUserStore()
const scrollbar = ref<InstanceType<typeof ElScrollbar>>()
const route = useRoute()
const router = useRouter()
const abortCtrl = ref<AbortController | null>(null)
const isCancelled = ref(false)
// 标记是否有正在进行的事件
const hasActiveEvents = ref(false)
// 保存上传文件的URL和文件名
const fileUrl = ref("")
const fileName = ref("")
const jobWorkbench = ref<JobWorkbenchData | null>(null)
const jobWorkbenchLoading = ref(false)
const feishuMcpServer = ref<MCPServer | null>(null)

// 事件状态管理
const eventStatusMap = ref<Map<string, EventStatus>>(new Map())
const eventDisplayOrder = ref<string[]>([])

// Get user avatar from store or use default
const userAvatar = computed(() => userStore.userInfo?.avatar || defaultUserAvatar)
// Get AI avatar from store or use default
const aiAvatar = computed(() => historyChatStore.logo || defaultRobotAvatar)
const isJobAssistantDialog = computed(() => {
  return isJobAssistantAgentName(historyChatStore.name || "")
})
const inputPlaceholder = computed(() => {
  if (isJobAssistantDialog.value) {
    return "粘贴岗位 JD、简历内容或项目经历，我会帮你分析和改写..."
  }
  return "请输入您的问题..."
})
const uploadHeaders = computed(() => {
  const token = localStorage.getItem('token') || ''
  return token
    ? {
        Authorization: `Bearer ${token}`,
      }
    : {}
})

const getFeishuConfigValue = (key: string) => {
  const config = feishuMcpServer.value?.config
  if (!Array.isArray(config)) {
    return ''
  }

  return config.find((item: any) => item?.key === key)?.value || ''
}

const feishuAppConfigReady = computed(() => {
  const appId = getFeishuConfigValue('app_id')
  const appSecret = getFeishuConfigValue('app_secret')
  return Boolean(appId && appSecret)
})

const feishuUserTokenReady = computed(() => {
  return Boolean(getFeishuConfigValue('user_access_token'))
})

const feishuSyncReady = computed(() => {
  return feishuAppConfigReady.value && feishuUserTokenReady.value
})

const feishuStatusLabel = computed(() => {
  if (!feishuMcpServer.value) {
    return '飞书能力异常'
  }
  if (feishuSyncReady.value) {
    return '飞书同步已就绪'
  }
  if (feishuAppConfigReady.value) {
    return '飞书应用已连接'
  }
  return '飞书能力待配置'
})

const feishuStatusText = computed(() => {
  if (!feishuMcpServer.value) {
    return '当前未发现飞书 MCP 服务，请先确认系统 MCP 初始化是否成功。'
  }
  if (!feishuAppConfigReady.value) {
    return '使用飞书文档和飞书日历前，请先在 MCP 页面填写飞书 APP_ID / APP_SECRET。'
  }
  if (!feishuUserTokenReady.value) {
    return '已配置 APP_ID / APP_SECRET，但尚未配置 USER_ACCESS_TOKEN。飞书文档可能还能以应用身份执行，飞书日历/日程能力则必须使用用户身份；请到 MCP 页面补充 USER_ACCESS_TOKEN。'
  }
  return '已配置应用身份和用户身份，飞书文档与飞书日历会尽量同步到当前用户的个人空间。'
})

// 计算显示的事件列表
const displayEventList = computed(() => {
  return eventDisplayOrder.value.map(id => eventStatusMap.value.get(id)).filter(Boolean) as EventStatus[]
})

// 检查是否有活跃事件
const checkActiveEvents = (chatItem: any) => {
  const hasActiveExecution = Array.isArray(chatItem.executionRecords)
    && chatItem.executionRecords.some((record: any) => record.status === 'START')
  const hasActiveEventInfo = Array.isArray(chatItem.eventInfo)
    && chatItem.eventInfo.some((event: EventInfo) => event.status === 'START')

  return hasActiveExecution || hasActiveEventInfo
}

const handleUploadSuccess = (response: any, file: any, fileList: any) => {
  ElMessage.success(`文件 ${file.name} 上传成功!`)
  console.log(response)
  // 保存上传成功返回的文件URL和文件名
  if (response && response.data) {
    fileUrl.value = response.data
    fileName.value = file.name
  }
}

const handleUploadError = (error: any, file: any, fileList: any) => {
  ElMessage.error(`文件 ${file.name} 上传失败.`)
  console.error(error)
}

// 取消上传的文件
const cancelUploadedFile = () => {
  fileUrl.value = ""
  fileName.value = ""
  ElMessage.info('已取消选择的文件')
}

// 判断是否为图片文件以便展示缩略图
const isImageFile = (name: string) => {
  return /\.(png|jpe?g|gif|webp|bmp|svg)$/i.test(name)
}


// Function to scroll to the bottom of the chat
function scrollBottom() {
  nextTick(() => {
    scrollbar.value?.wrapRef?.scrollTo(0, scrollbar.value?.wrapRef.scrollHeight)
  })
}

// 清空事件状态
const clearEventStatus = () => {
  eventStatusMap.value.clear()
  eventDisplayOrder.value = []
}

// 处理事件状态更新
const handleEventStatus = (parsedData: any) => {
  const { data } = parsedData
  
  // 确保事件有title字段，如果没有则使用event_type或默认值
  const eventId = data.title || data.event_type || "event"
  const { status, message } = data
  
  // 获取最后一条AI消息
  const lastChat = historyChatStore.chatArr[historyChatStore.chatArr.length - 1]
  
  // 初始化eventInfo数组（如果不存在）
  if (!lastChat.eventInfo) {
    lastChat.eventInfo = []
  }
  
  // 查找是否已有相同事件类型的事件
  const existingEventIndex = lastChat.eventInfo.findIndex(
    (event) => event.event_type === eventId
  )
  
  if (status === 'START') {
    // 如果是新事件，添加到事件列表
    if (existingEventIndex === -1) {
      lastChat.eventInfo.push({
        event_type: eventId,
        message: message || "处理中...",
        status: status,
        show: false // 默认折叠
      })
    } else {
      // 更新已有事件
      lastChat.eventInfo[existingEventIndex].status = status
      lastChat.eventInfo[existingEventIndex].message = message || "处理中..."
    }
    // 设置有活跃事件
    hasActiveEvents.value = true
  } else if (status === 'END' || status === 'ERROR') {
    // 更新已有事件状态
    if (existingEventIndex !== -1) {
      lastChat.eventInfo[existingEventIndex].status = status
      if (message) {
        lastChat.eventInfo[existingEventIndex].message = message
      }
    } else {
      // 如果没有找到对应的事件，创建一个新事件
      lastChat.eventInfo.push({
        event_type: eventId,
        message: message || (status === 'END' ? "已完成" : "处理出错"),
        status: status,
        show: false // 默认折叠
      })
    }
    
    // 检查是否还有其他活跃事件
    hasActiveEvents.value = checkActiveEvents(lastChat)
  }
  
  scrollBottom()
}

const handleStructuredToolEvent = (parsedData: any) => {
  const toolOutput = parseToolOutputFromEvent(parsedData)
  if (!toolOutput) {
    return false
  }

  const lastChat = historyChatStore.chatArr[historyChatStore.chatArr.length - 1]
  if (!lastChat) {
    return true
  }

  if (!lastChat.toolOutputs) {
    lastChat.toolOutputs = []
  }

  lastChat.toolOutputs = appendToolOutputCard(lastChat.toolOutputs, toolOutput)

  scrollBottom()
  return true
}

const handleExecutionTraceEvent = (parsedData: any) => {
  const executionRecord = parseExecutionRecordFromEvent(parsedData)
  if (!executionRecord) {
    return false
  }

  const lastChat = historyChatStore.chatArr[historyChatStore.chatArr.length - 1]
  if (!lastChat) {
    return true
  }

  lastChat.executionRecords = upsertExecutionRecord(
    lastChat.executionRecords || [],
    executionRecord,
  )
  hasActiveEvents.value = checkActiveEvents(lastChat)
  scrollBottom()
  return true
}

const handleInvalidDialog = (message = '当前会话不存在或已失效，请重新选择或创建会话') => {
  historyChatStore.resetDialogState()
  sendQuestion.value = true
  abortCtrl.value = null
  hasActiveEvents.value = false
  fileUrl.value = ""
  fileName.value = ""
  ElMessage.error(message)
  router.push({ path: '/conversation' })
}

const refreshJobWorkbench = async () => {
  if (!isJobAssistantDialog.value) {
    jobWorkbench.value = null
    return
  }

  try {
    jobWorkbenchLoading.value = true
    const response = await getJobHuntWorkbenchAPI()
    if (response.data.status_code === 200) {
      jobWorkbench.value = response.data.data
      return
    }
    ElMessage.error(response.data.status_message || '获取求职工作台失败')
  } catch (error) {
    console.error('获取求职工作台失败:', error)
  } finally {
    jobWorkbenchLoading.value = false
  }
}

const refreshFeishuMcpStatus = async () => {
  if (!isJobAssistantDialog.value) {
    feishuMcpServer.value = null
    return
  }

  try {
    const response = await getMCPServersAPI()
    if (response.data.status_code === 200 && Array.isArray(response.data.data)) {
      feishuMcpServer.value = response.data.data.find(server => server.server_name === '飞书') || null
    }
  } catch (error) {
    console.error('获取飞书 MCP 状态失败:', error)
  }
}

const openFeishuConfigPage = () => {
  router.push({ path: '/mcp-server' })
}

const ensureFeishuMcpReady = (featureName = '飞书功能', options?: { requireUserToken?: boolean }) => {
  if (!feishuMcpServer.value) {
    ElMessage.error('未检测到飞书 MCP 服务，请先重启后端并确认系统 MCP 已初始化')
    return false
  }

  if (!feishuAppConfigReady.value) {
    ElMessage.warning(`${featureName}需要先在 MCP 页面配置飞书 APP_ID / APP_SECRET`)
    return false
  }

  if (!feishuUserTokenReady.value) {
    if (options?.requireUserToken) {
      ElMessage.warning(`${featureName}必须先在 MCP 页面配置 USER_ACCESS_TOKEN。当前飞书日历相关能力需要以用户身份调用，只有 APP_ID / APP_SECRET 不够。`)
      return false
    }

    ElMessage.warning(`${featureName}会继续执行，但当前只配置了应用身份。飞书 API 可能成功，结果不一定出现在你的个人云文档；如需个人空间可见，请补充 USER_ACCESS_TOKEN。`)
  }

  return true
}

const formatFeishuDateTime = (value: Date) => {
  const year = value.getFullYear()
  const month = `${value.getMonth() + 1}`.padStart(2, '0')
  const day = `${value.getDate()}`.padStart(2, '0')
  const hours = `${value.getHours()}`.padStart(2, '0')
  const minutes = `${value.getMinutes()}`.padStart(2, '0')
  return `${year}-${month}-${day} ${hours}:${minutes}`
}

const buildDefaultInterviewWindow = () => {
  const start = new Date()
  start.setDate(start.getDate() + 1)
  start.setHours(19, 0, 0, 0)

  const end = new Date(start.getTime() + 60 * 60 * 1000)
  return {
    start: formatFeishuDateTime(start),
    end: formatFeishuDateTime(end),
  }
}

const saveResumeVersionWithMcp = (result: ResumeRewriteResult) => {
  const rewritten = result.rewritten_resume.join('\n')
  useQuickPrompt(
    `请调用求职工作台 MCP，把下面这版简历改写结果保存为一个新的简历版本。标题控制在20字内，目标岗位是${result.target_role}。\n\n版本说明：${result.overall_strategy}\n\n简历内容：\n${rewritten}`,
    true,
  )
}

const syncResumeVersionToFeishuDoc = (result: ResumeRewriteResult) => {
  if (!ensureFeishuMcpReady('飞书文档同步')) {
    return
  }

  const rewritten = result.rewritten_resume.join('\n')
  useQuickPrompt(
    `请调用 feishu_workspace（飞书 MCP），把下面这版简历改写结果整理并同步为一篇飞书文档。文档标题控制在20字内，优先写入目标岗位、版本说明和正文；如果需要请先创建文档，再返回文档标题、document_id 和可访问链接。\n\n目标岗位：${result.target_role}\n\n版本说明：${result.overall_strategy}\n\n正文内容：\n${rewritten}`,
    true,
  )
}

const recordJobApplicationWithMcp = (result: ResumeMatchResult) => {
  useQuickPrompt(
    `请调用求职工作台 MCP，帮我记录一条岗位投递信息。岗位名称是${result.target_role}；公司名称如果未知先写“待补充”；当前状态记为待投递；匹配摘要是：${result.overall_summary}`,
    true,
  )
}

const createInterviewPlanWithMcp = (result: InterviewFollowupResult) => {
  const focusPoints = result.deep_dive_points.join('；')
  const prepActions = result.question_answer_pairs
    .slice(0, 4)
    .map((item, index) => `${index + 1}. ${item.question} -> ${item.answer_outline}`)
    .join('\n')

  useQuickPrompt(
    `请调用求职工作台 MCP，基于下面内容生成一份面试准备计划。目标岗位是${result.target_role}。\n\n总结：${result.overall_summary}\n\n建议深挖：${focusPoints}\n\n准备动作：\n${prepActions}`,
    true,
  )
}

const saveFollowupNotesWithMcp = (result: InterviewFollowupResult) => {
  const qaNotes = result.question_answer_pairs
    .map((item, index) => `Q${index + 1}：${item.question}\n回答框架：${item.answer_outline}`)
    .join('\n\n')

  useQuickPrompt(
    `请调用求职工作台 MCP，把下面这组面试追问内容保存成追问笔记，标题控制在20字内，目标岗位是${result.target_role}。\n\n总结：${result.overall_summary}\n\n追问笔记：\n${qaNotes}`,
    true,
  )
}

const scheduleInterviewWithFeishuCalendar = (result: InterviewFollowupResult) => {
  if (!ensureFeishuMcpReady('飞书日历日程', { requireUserToken: true })) {
    return
  }

  const focusPoints = result.deep_dive_points.join('；')
  const qaNotes = result.question_answer_pairs
    .slice(0, 4)
    .map((item, index) => `Q${index + 1}：${item.question}\n回答框架：${item.answer_outline}`)
    .join('\n\n')
  const window = buildDefaultInterviewWindow()

  useQuickPrompt(
    `请调用 feishu_workspace（飞书 MCP），帮我创建一个飞书面试准备日程。如果没有合适的日历，可先创建“求职面试”日历。日程标题控制在20字内，时区使用 Asia/Shanghai，并在描述中写入准备重点和回答框架摘要。创建完成后返回 calendar_id、event_id 和时间信息。\n\n目标岗位：${result.target_role}\n\n建议时间：${window.start} 到 ${window.end}\n\n准备重点：${focusPoints}\n\n追问摘要：\n${qaNotes}`,
    true,
  )
}

const loadDialogHistory = async (dialogId: string, initialMessage?: string) => {
  historyChatStore.dialogId = dialogId
  const result = await historyChatStore.HistoryChat(dialogId)
  if (!result?.ok) {
    if (result?.notFound) {
      handleInvalidDialog()
    }
    return
  }

  await refreshJobWorkbench()
  await refreshFeishuMcpStatus()

  scrollBottom()

  if (initialMessage && typeof initialMessage === 'string') {
    searchInput.value = initialMessage
    nextTick(() => {
      personQuestion()
    })
  }
}

// Function to handle sending a message
const personQuestion = async () => {
  if (!historyChatStore.dialogId) {
    ElMessage.error('未获取到会话 ID，请先选择或创建会话')
    return
  }
  if (searchInput.value.trim() && sendQuestion.value) {
    sendQuestion.value = false
    isCancelled.value = false
    hasActiveEvents.value = false
    const currentInput = searchInput.value
    searchInput.value = ""

    historyChatStore.chatArr.push({
      personMessage: { content: currentInput },
      aiMessage: { content: "" }, // 设置初始空内容，后续会被chunks累加
      toolOutputs: [],
      executionRecords: [],
      eventInfo: [] // 初始化事件信息数组
    })
    scrollBottom()

    const data: Chat = {
      dialogId: historyChatStore.dialogId,
      userInput: currentInput,
    }
    
    // 如果有上传的文件URL，添加到请求中
    if (fileUrl.value) {
      data.fileUrl = fileUrl.value
    }

    try {
      abortCtrl.value = sendMessage(
        data,
        (msg: any) => {
          if (isCancelled.value) {
            historyChatStore.chatArr[historyChatStore.chatArr.length - 1].aiMessage.content = '已取消本次对话！'
            return
          }
          try {
            const parsedData = JSON.parse(msg.data)
            // 移除这些可能含有敏感信息的日志
            // console.log("---------------------------")
            // console.log(parsedData.data)
            
            if (parsedData.data.tools && Array.isArray(parsedData.data.tools)) {
              // data.value.tools = parsedData.data.tools // This line was removed from the original file
            }
            // 只有当不是response_chunk类型时，才设置整个content
            if (parsedData.type !== 'response_chunk') {
              historyChatStore.chatArr[historyChatStore.chatArr.length - 1].aiMessage.content = parsedData.data.content || ''
            }
            if (parsedData.data.session_id) {
              // sessionId.value = parsedData.data.session_id // This line was removed from the original file
              // sessionStore().updateSessionId(sessionId.value) // This line was removed from the original file
            }
            // 处理不同类型的消息
            if (parsedData.type === 'response_chunk') {
              // 累加chunk内容而不是替换
              const lastMessage = historyChatStore.chatArr[historyChatStore.chatArr.length - 1]
              if (!lastMessage.aiMessage.content) {
                lastMessage.aiMessage.content = parsedData.data.chunk
              } else {
                lastMessage.aiMessage.content += parsedData.data.chunk
              }
              scrollBottom()
              // console.log('【Chunk接收】当前累加内容:', lastMessage.aiMessage.content) // 调试用
            } else if (parsedData.type === 'event') {
              if (handleExecutionTraceEvent(parsedData)) {
                return
              }
              if (handleStructuredToolEvent(parsedData)) {
                return
              }
              // 处理事件消息
              handleEventStatus(parsedData)
            } else if (parsedData.type === 'knowledge') {
              historyChatStore.chatArr.push({
                personMessage: { content: '' },
                aiMessage: { content: '[知识库检索结果]\n' + (parsedData.data.message || ''), type: 'knowledge' },
                toolOutputs: [],
                executionRecords: [],
                eventInfo: []
              })
              scrollBottom()
            } else if (parsedData.type === 'error') {
              historyChatStore.chatArr.push({
                personMessage: { content: '' },
                aiMessage: { content: '[错误]\n' + (parsedData.data.message || ''), type: 'error' },
                toolOutputs: [],
                executionRecords: [],
                eventInfo: []
              })
              scrollBottom()
            } else if (parsedData.type === 'heartbeat') {
              // 心跳包可忽略
            } else {
              // 其他类型作为普通消息展示
              historyChatStore.chatArr.push({
                personMessage: { content: '' },
                aiMessage: { content: '[系统消息]\n' + JSON.stringify(parsedData.data), type: 'system' },
                toolOutputs: [],
                executionRecords: [],
                eventInfo: []
              })
              scrollBottom()
            }
          } catch (error) {
            console.error('解析消息失败:', error)
          }
        },
        () => {
          const lastMessage = historyChatStore.chatArr[historyChatStore.chatArr.length - 1]
          if (lastMessage) {
            hydrateToolOutputCardsFromMessage(lastMessage)
          }
          sendQuestion.value = true
          abortCtrl.value = null
          hasActiveEvents.value = false
          // 清空文件URL和文件名
          fileUrl.value = ""
          fileName.value = ""
          void refreshJobWorkbench()
        },
        (error: any) => {
          const errorMessage = error?.message || '发送消息失败，请重试'
          const status = error?.status

          if (status === 404 || errorMessage.includes('当前会话不存在') || errorMessage.includes('当前会话绑定的智能体不存在')) {
            handleInvalidDialog(errorMessage)
            return
          }

          ElMessage.error(errorMessage)
          sendQuestion.value = true
          abortCtrl.value = null
          hasActiveEvents.value = false
          fileUrl.value = ""
          fileName.value = ""
        }
      )
    } catch (error) {
      ElMessage.error('发送消息失败，请重试')
      sendQuestion.value = true
      abortCtrl.value = null
      hasActiveEvents.value = false
      // 清空文件URL和文件名
      fileUrl.value = ""
      fileName.value = ""
    }
  }
}

const stopGeneration = () => {
  if (abortCtrl.value) {
    // console.log('[stopGeneration] 用户点击暂停, abort 请求')
    isCancelled.value = true
    abortCtrl.value.abort()
    const lastMessage = historyChatStore.chatArr[historyChatStore.chatArr.length - 1]
    if (lastMessage) {
      //lastMessage.aiMessage.content = '已取消本次AI生成！'
      sendQuestion.value = true
      abortCtrl.value = null
      hasActiveEvents.value = false
      ElMessage.info('已取消本次AI生成！')
    }
  }
}

// 切换事件信息的展开/折叠状态
const toggleEventInfo = (event: EventInfo) => {
  event.show = !event.show
}

const useQuickPrompt = (prompt: string, autoSend = false) => {
  if (!sendQuestion.value) {
    ElMessage.warning("当前正在生成回答，请稍后再试")
    return
  }

  searchInput.value = prompt
  if (autoSend) {
    nextTick(() => {
      personQuestion()
    })
  }
}

const useJobAssistantQuickPrompt = (
  item: { prompt: string; requiresFeishu?: boolean; requiresFeishuUserToken?: boolean },
  autoSend = false,
) => {
  if (item.requiresFeishu && !ensureFeishuMcpReady('飞书文档/日历功能', { requireUserToken: item.requiresFeishuUserToken })) {
    return
  }

  useQuickPrompt(item.prompt, autoSend)
}

// Load history on mount
onMounted(() => {
  const dialog_id = route.query.dialog_id
  const message = route.query.message
  
  if (dialog_id) {
    void loadDialogHistory(dialog_id as string, typeof message === 'string' ? message : undefined)
  } else if (message && typeof message === 'string') {
    // 新会话，直接发送首页的搜索消息
    searchInput.value = message
    nextTick(() => {
      personQuestion()
    })
  }
})

// Watch for route changes to load new chat history
watch(
  () => route.query.dialog_id,
  (newVal, oldVal) => {
    if (newVal && newVal !== oldVal) {
      const message = route.query.message
      void loadDialogHistory(newVal as string, typeof message === 'string' ? message : undefined)
    }
  }
)

watch(
  () => isJobAssistantDialog.value,
  (enabled) => {
    if (enabled) {
      void refreshJobWorkbench()
      void refreshFeishuMcpStatus()
      return
    }
    jobWorkbench.value = null
    feishuMcpServer.value = null
  },
  { immediate: true }
)

// Watch for new messages to scroll down
watch(
  () => historyChatStore.chatArr,
  (newVal) => {
    // console.log('【消息更新】历史消息数组更新:', JSON.stringify(newVal))
    scrollBottom()
  },
  { deep: true }
)
</script>

<template>
  <div class="chat-container">
    <div class="chat-conversation">
      <el-scrollbar ref="scrollbar">
        <div
          v-if="isJobAssistantDialog && historyChatStore.chatArr.length === 0"
          class="job-assistant-hero"
        >
          <div class="hero-head">
            <span class="hero-badge">{{ JOB_ASSISTANT_NAME }}</span>
            <h2>把岗位分析、简历改写和面试准备放进一个会话里完成</h2>
            <p>
              建议先贴岗位 JD 和你的项目经历，再继续追问简历表达、面试追问和回答框架。
            </p>
          </div>

          <div class="hero-highlight-list">
            <div
              v-for="item in JOB_ASSISTANT_HIGHLIGHTS"
              :key="item"
              class="hero-highlight-item"
            >
              <span class="highlight-marker"></span>
              <span>{{ item }}</span>
            </div>
          </div>

          <div class="integration-note" :class="{ ready: feishuAppConfigReady }">
            <span class="integration-note-label">
              {{ feishuStatusLabel }}
            </span>
            <span class="integration-note-text">{{ feishuStatusText }}</span>
            <button
              v-if="!feishuSyncReady"
              type="button"
              class="integration-note-btn"
              @click="openFeishuConfigPage"
            >
              去配置
            </button>
          </div>

          <div class="hero-prompt-grid">
            <button
              v-for="item in JOB_ASSISTANT_QUICK_PROMPTS"
              :key="item.label"
              class="hero-prompt-card"
              @click="useJobAssistantQuickPrompt(item, true)"
            >
              <span class="prompt-card-title">{{ item.label }}</span>
              <span class="prompt-card-description">{{ item.description }}</span>
              <span class="prompt-card-action">直接发起</span>
            </button>
          </div>
        </div>

        <JobWorkbenchPanel
          v-if="isJobAssistantDialog"
          :data="jobWorkbench"
          :loading="jobWorkbenchLoading"
          @refresh="refreshJobWorkbench"
        />

        <!-- 聊天消息区 -->
        <div v-for="(item, index) in historyChatStore.chatArr" :key="index" class="message-group">
          <!-- User Message -->
          <div v-if="item.personMessage.content" class="user-message">
            <div class="message-content">
              <span>{{ item.personMessage.content }}</span>
            </div>
            <img :src="userAvatar" alt="User Avatar" class="avatar" />
          </div>
          
          <!-- AI Message -->
          <div
            v-if="item.aiMessage.content || item.toolOutputs?.length || item.executionRecords?.length || (!sendQuestion && index === historyChatStore.chatArr.length - 1)"
            class="ai-message"
            :class="[
              item.aiMessage.type ? 'ai-message-' + item.aiMessage.type : '',
              item.toolOutputs?.length || item.executionRecords?.length ? 'has-tool-output' : ''
            ]"
          >
            <img :src="aiAvatar" alt="AI Avatar" class="avatar" />
            <div class="message-content">
              <ExecutionTraceList
                v-if="item.executionRecords?.length"
                :records="item.executionRecords"
              />
              <!-- 事件进度信息，每个事件一行，可折叠 -->
              <div v-if="item.eventInfo && item.eventInfo.length" class="event-info-list">
                <div v-for="(event, evIdx) in item.eventInfo" :key="evIdx" class="event-info-row" :class="event.status">
                  <div class="event-info-header" @click="toggleEventInfo(event)">
                    <el-icon v-if="event.status === 'START'" class="rotating"><Loading /></el-icon>
                    <el-icon v-else-if="event.status === 'END'" class="success-icon"><Check /></el-icon>
                    <el-icon v-else-if="event.status === 'ERROR'" class="error-icon"><Close /></el-icon>
                    <span class="event-info-title">{{ event.event_type }}</span>
                    <span class="event-info-status">
                      {{ event.status === 'START' ? '进行中' : event.status === 'END' ? '已完成' : '失败' }}
                    </span>
                    <span class="event-info-toggle">{{ event.show ? '收起' : '展开' }}</span>
                  </div>
                  <div v-if="event.show" class="event-info-message">
                    {{ event.message }}
                  </div>
                </div>
              </div>
              
              <!-- Loading Indicator - 只在没有活跃事件时显示 -->
              <div v-if="!item.aiMessage.content && !sendQuestion && index === historyChatStore.chatArr.length - 1 && !hasActiveEvents" class="loading-spinner">
                  <el-icon class="is-loading" :size="20"><Loading /></el-icon>
              </div>
              <div v-if="item.toolOutputs?.length" class="tool-output-list">
                <template v-for="(toolOutput, toolIdx) in item.toolOutputs" :key="`${index}-tool-${toolIdx}`">
                  <ResumeMatchCard
                    v-if="toolOutput.type === 'resume_match'"
                    :result="toolOutput.payload"
                    @record-application="recordJobApplicationWithMcp"
                  />
                  <ResumeRewriteCard
                    v-else-if="toolOutput.type === 'resume_rewrite'"
                    :result="toolOutput.payload"
                    @save-version="saveResumeVersionWithMcp"
                    @sync-feishu-doc="syncResumeVersionToFeishuDoc"
                  />
                  <InterviewFollowupCard
                    v-else-if="toolOutput.type === 'interview_followup'"
                    :result="toolOutput.payload"
                    @create-plan="createInterviewPlanWithMcp"
                    @save-notes="saveFollowupNotesWithMcp"
                    @create-calendar="scheduleInterviewWithFeishuCalendar"
                  />
                </template>
              </div>
              <div
                v-if="item.aiMessage.content"
                class="text-response"
                :class="{ 'after-tool-output': item.toolOutputs?.length || item.executionRecords?.length }"
              >
                <div v-if="item.aiMessage.type === 'knowledge'" style="color: #409eff;">
                  <MdPreview :editorId="'ai-knowledge-' + index" :modelValue="item.aiMessage.content" />
                </div>
                <div v-else-if="item.aiMessage.type === 'event'" style="color: #67c23a;">
                  <MdPreview :editorId="'ai-event-' + index" :modelValue="item.aiMessage.content" />
                </div>
                <div v-else-if="item.aiMessage.type === 'error'" style="color: #f56c6c;">
                  <MdPreview :editorId="'ai-error-' + index" :modelValue="item.aiMessage.content" />
                </div>
                <div v-else-if="item.aiMessage.type === 'system'" style="color: #e6a23c;">
                  <MdPreview :editorId="'ai-system-' + index" :modelValue="item.aiMessage.content" />
                </div>
                <MdPreview v-else :editorId="'ai-' + index" :modelValue="item.aiMessage.content" />
              </div>
            </div>
          </div>
        </div>
      </el-scrollbar>
    </div>

    <div class="input-area">
      <el-upload
        action="/api/v1/upload"
        :headers="uploadHeaders"
        :on-success="handleUploadSuccess"
        :on-error="handleUploadError"
        :show-file-list="false"
        :disabled="!!fileUrl"
      >
        <el-button circle class="action-btn" :class="{ 'file-uploaded': fileUrl }">
          <el-icon><UploadFilled /></el-icon>
        </el-button>
      </el-upload>
      <div class="input-wrapper">
        <div v-if="isJobAssistantDialog" class="quick-input-bar">
          <span class="quick-input-label">快捷输入</span>
          <button
            v-for="item in JOB_ASSISTANT_QUICK_PROMPTS"
            :key="item.label"
            class="quick-input-chip"
            @click="useJobAssistantQuickPrompt(item)"
          >
            {{ item.shortLabel }}
          </button>
        </div>
        <div v-if="isJobAssistantDialog && !feishuSyncReady" class="quick-integration-tip">
          <span>{{ feishuStatusText }}</span>
          <button type="button" class="quick-integration-btn" @click="openFeishuConfigPage">
            去配置
          </button>
        </div>
        <!-- 已上传文件显示 -->
        <div v-if="fileUrl" class="uploaded-file-tag">
          <span class="file-avatar" aria-hidden="true">
            <img v-if="isImageFile(fileName)" :src="fileUrl" alt="" />
            <svg v-else width="16" height="16" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
              <path d="M21.44 11.05l-7.07 7.07a5 5 0 01-7.07-7.07l7.07-7.07a3 3 0 114.24 4.24l-7.07 7.07a1 1 0 01-1.41-1.41l6.36-6.36" stroke="#409eff" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
            </svg>
          </span>
          <a class="file-name" :href="fileUrl" target="_blank" rel="noopener" :title="fileName">{{ fileName }}</a>
          <el-button size="small" type="danger" text @click="cancelUploadedFile" class="cancel-btn" title="移除">
            <el-icon><Close /></el-icon>
          </el-button>
        </div>
        <el-input
          v-model="searchInput"
          type="textarea"
          :autosize="{ minRows: 1, maxRows: 4 }"
          :placeholder="inputPlaceholder"
          @keydown.enter.exact.prevent="personQuestion"
          class="message-input"
        />
      </div>
      <el-button
        @click="sendQuestion ? personQuestion() : stopGeneration()"
        type="primary"
        circle
        class="send-btn"
        :class="{ 'pause-mode': !sendQuestion }"
        :disabled="sendQuestion ? !searchInput.trim() : false"
      >
        <el-icon v-if="sendQuestion"><Promotion /></el-icon>
        <el-icon v-else><VideoPause /></el-icon>
      </el-button>
    </div>
  </div>
</template>

<style lang="scss" scoped>
.chat-container {
  display: flex;
  flex-direction: column;
  height: 100%;
  background-color: #f7f8fa;
}

.chat-conversation {
  flex: 1;
  padding: 20px;
  overflow-y: hidden;

  .job-assistant-hero {
    margin-bottom: 22px;
    padding: 24px;
    border-radius: 24px;
    background:
      radial-gradient(circle at top right, rgba(255, 232, 188, 0.38), transparent 32%),
      linear-gradient(160deg, #fff9ee 0%, #f6faff 56%, #edf5ff 100%);
    border: 1px solid rgba(215, 226, 240, 0.95);
    box-shadow: 0 18px 36px rgba(73, 109, 161, 0.08);
  }

  .hero-head {
    h2 {
      margin: 14px 0 10px;
      font-size: 28px;
      line-height: 1.2;
      color: #17345f;
    }

    p {
      margin: 0;
      max-width: 760px;
      font-size: 15px;
      line-height: 1.7;
      color: #556377;
    }
  }

  .hero-badge {
    display: inline-flex;
    padding: 6px 12px;
    border-radius: 999px;
    background: #eaf2ff;
    color: #1858ab;
    font-size: 12px;
    font-weight: 700;
    letter-spacing: 0.05em;
    text-transform: uppercase;
  }

  .hero-highlight-list {
    display: grid;
    gap: 10px;
    margin-top: 20px;
  }

  .integration-note {
    display: flex;
    align-items: center;
    gap: 12px;
    flex-wrap: wrap;
    margin-top: 18px;
    padding: 14px 16px;
    border-radius: 18px;
    border: 1px solid #f2dfb4;
    background: rgba(255, 248, 230, 0.78);

    &.ready {
      border-color: #cde7dc;
      background: rgba(238, 250, 244, 0.82);
    }
  }

  .integration-note-label {
    display: inline-flex;
    padding: 6px 10px;
    border-radius: 999px;
    background: #fff0c9;
    color: #9a6317;
    font-size: 12px;
    font-weight: 700;
  }

  .integration-note.ready .integration-note-label {
    background: #e7f7f1;
    color: #11785c;
  }

  .integration-note-text {
    flex: 1;
    min-width: 220px;
    font-size: 13px;
    line-height: 1.7;
    color: #5b6777;
  }

  .integration-note-btn {
    border: 0;
    padding: 8px 12px;
    border-radius: 12px;
    background: #17345f;
    color: white;
    font-size: 12px;
    font-weight: 700;
    cursor: pointer;
  }

  .hero-highlight-item {
    display: flex;
    align-items: center;
    gap: 10px;
    font-size: 14px;
    color: #30445f;
  }

  .highlight-marker {
    width: 9px;
    height: 9px;
    border-radius: 50%;
    background: linear-gradient(135deg, #1f6fd6 0%, #d9a441 100%);
    box-shadow: 0 0 0 4px rgba(31, 111, 214, 0.1);
  }

  .hero-prompt-grid {
    display: grid;
    grid-template-columns: repeat(3, minmax(0, 1fr));
    gap: 14px;
    margin-top: 22px;
  }

  .hero-prompt-card {
    display: flex;
    flex-direction: column;
    align-items: flex-start;
    gap: 10px;
    padding: 18px;
    border-radius: 18px;
    border: 1px solid #d9e3f0;
    background: rgba(255, 255, 255, 0.8);
    cursor: pointer;
    text-align: left;
    transition: transform 0.2s ease, box-shadow 0.2s ease, border-color 0.2s ease;

    &:hover {
      transform: translateY(-2px);
      border-color: #8db5eb;
      box-shadow: 0 14px 28px rgba(74, 126, 191, 0.12);
    }
  }

  .prompt-card-title {
    font-size: 16px;
    font-weight: 700;
    color: #17345f;
  }

  .prompt-card-description {
    font-size: 13px;
    line-height: 1.6;
    color: #56657c;
  }

  .prompt-card-action {
    font-size: 12px;
    font-weight: 700;
    color: #1b65ca;
  }
  
  .message-group {
    margin-bottom: 20px;
  }

  .ai-message {
    display: flex;
    align-items: flex-start;
    justify-content: flex-start;

    &.has-tool-output {
      .message-content {
        max-width: min(960px, calc(100% - 70px));
        background: transparent;
        box-shadow: none;
        padding: 0;
      }
    }

    .avatar {
      width: 40px;
      height: 40px;
      border-radius: 50%;
      margin-right: 15px;
      flex-shrink: 0;
      border: 1px solid #eee;
    }

    .message-content {
      background-color: #ffffff;
      border-radius: 18px;
      padding: 12px 18px;
      max-width: 70%;
      color: #333;
      box-shadow: 0 2px 8px rgba(0,0,0,0.05);
      word-break: break-word;
    }
  }

  .tool-output-list {
    display: grid;
    gap: 12px;
    margin-bottom: 12px;
  }

  .text-response {
    background-color: #ffffff;
    border-radius: 18px;
    padding: 12px 18px;
    box-shadow: 0 2px 8px rgba(0,0,0,0.05);

    &.after-tool-output {
      margin-top: 10px;
    }
  }

  .user-message {
    display: flex;
    justify-content: flex-end;
    align-items: flex-start;

    .avatar {
      width: 40px;
      height: 40px;
      border-radius: 50%;
      margin-left: 12px;
      flex-shrink: 0;
      border: 1px solid #eee;
    }

    .message-content {
      display: flex;
      align-items: center;
      background: linear-gradient(135deg, #6e8efb, #a777e3);
      color: white;
      border-radius: 18px;
      padding: 12px 18px;
      max-width: 70%;
      box-shadow: 0 2px 8px rgba(0,0,0,0.1);
    }
  }
}

/* 事件进度信息样式 */
.event-info-list {
  margin-bottom: 12px;
}

.event-info-row {
  margin-bottom: 8px;
  border-radius: 8px;
  padding: 8px 12px;
  background: #f8fafc;
  cursor: pointer;
  transition: background 0.3s ease;
  display: flex;
  flex-direction: column;
  
  &.START { 
    border-left: 4px solid #409eff; 
    background: #f0f7ff;
  }
  
  &.END { 
    border-left: 4px solid #67c23a; 
    background: #f0fff4;
  }
  
  &.ERROR { 
    border-left: 4px solid #f56c6c; 
    background: #fff0f0;
  }
  
  &:hover {
    transform: translateX(2px);
  }
}

.event-info-header { 
  display: flex; 
  align-items: center; 
}

.event-info-title { 
  margin-left: 8px; 
  font-weight: 600;
  color: #333;
}

.event-info-status {
  margin-left: 8px;
  font-size: 12px;
  padding: 2px 6px;
  border-radius: 10px;
  background: #eee;
  
  .START & {
    background: #e6f1ff;
    color: #409eff;
  }
  
  .END & {
    background: #e7f9eb;
    color: #67c23a;
  }
  
  .ERROR & {
    background: #ffeded;
    color: #f56c6c;
  }
}

.event-info-toggle { 
  margin-left: auto; 
  color: #aaa; 
  font-size: 12px;
  
  &:hover {
    color: #666;
  }
}

.event-info-message { 
  margin-top: 8px; 
  color: #333;
  padding: 8px;
  background: rgba(255, 255, 255, 0.7);
  border-radius: 4px;
  font-size: 14px;
  line-height: 1.5;
}

.rotating { 
  animation: spin 1.2s linear infinite;
  color: #409eff;
}

.success-icon {
  color: #67c23a;
}

.error-icon {
  color: #f56c6c;
}

@keyframes spin { 
  from { transform: rotate(0deg); } 
  to { transform: rotate(360deg); } 
}

.loading-spinner {
  display: flex;
  justify-content: center;
  align-items: center;
  min-height: 28px;
  color: #6e8efb;
}

.input-area {
  display: flex;
  align-items: flex-end;
  padding: 15px 20px;
  border-top: 1px solid #e0e0e0;
  background-color: #ffffff;
  box-shadow: 0 -2px 10px rgba(0,0,0,0.05);

  .action-btn {
    margin-right: 10px;
    background-color: #f0f2f5;
    border: none;
    width: 48px;
    height: 48px;
    font-size: 24px;
    transition: all 0.3s ease;
    &:hover {
      background-color: #e6e8eb;
    }
    &.file-uploaded {
      background-color: #67c23a;
      color: white;
      &:hover {
        background-color: #5daf34;
      }
    }
    &:disabled {
      opacity: 0.6;
      cursor: not-allowed;
    }
  }

  .input-wrapper {
    flex-grow: 1;
    position: relative;
  }

  .quick-input-bar {
    display: flex;
    align-items: center;
    gap: 8px;
    flex-wrap: wrap;
    margin-bottom: 10px;
  }

  .quick-input-label {
    font-size: 12px;
    font-weight: 700;
    color: #6b7280;
  }

  .quick-input-chip {
    height: 28px;
    padding: 0 12px;
    border-radius: 999px;
    border: 1px solid #d5e3f5;
    background: #f7fbff;
    color: #27528a;
    font-size: 12px;
    font-weight: 600;
    cursor: pointer;
    transition: background 0.2s ease, border-color 0.2s ease, color 0.2s ease;

    &:hover {
      background: #ecf4ff;
      border-color: #8db5eb;
      color: #174985;
    }
  }

  .quick-integration-tip {
    display: flex;
    align-items: center;
    gap: 10px;
    flex-wrap: wrap;
    margin-bottom: 10px;
    padding: 10px 12px;
    border-radius: 14px;
    background: #fff8e8;
    border: 1px solid #f1dfb5;
    color: #7a5b27;
    font-size: 12px;
    line-height: 1.6;
  }

  .quick-integration-btn {
    border: 0;
    padding: 6px 10px;
    border-radius: 10px;
    background: #17345f;
    color: white;
    font-size: 12px;
    font-weight: 700;
    cursor: pointer;
  }

  .uploaded-file-tag {
    position: relative;
    top: auto;
    left: 0;
    display: flex;
    align-items: center;
    gap: 8px;
    width: fit-content;
    margin-bottom: 8px;
    padding: 6px 10px;
    background: linear-gradient(135deg, #f5fbff 0%, #ecf5ff 100%);
    border: 1px solid #b3d8ff;
    border-radius: 16px;
    font-size: 12px;
    z-index: 10;
    box-shadow: 0 2px 4px rgba(0,0,0,0.1);

    .file-avatar {
      width: 22px;
      height: 22px;
      border-radius: 6px;
      overflow: hidden;
      background: rgba(64, 158, 255, 0.1);
      display: flex;
      align-items: center;
      justify-content: center;
      flex-shrink: 0;
      border: 1px solid rgba(64, 158, 255, 0.2);
      img {
        width: 100%;
        height: 100%;
        object-fit: cover;
        display: block;
      }
    }

    .file-name {
      color: #1f6fd6;
      text-decoration: none;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
      max-width: 180px;
      font-weight: 500;
    }

    .cancel-btn {
      padding: 0;
      width: 20px;
      height: 20px;
      min-height: 20px;
      font-size: 12px;
      margin-left: 4px;
      
      &:hover {
        background-color: rgba(245, 108, 108, 0.1);
      }
      :deep(.el-icon) {
        font-size: 16px;
      }
    }
  }

  .message-input {
    width: 100%;
    :deep(.el-textarea__inner) {
      border-radius: 20px;
      background-color: #f0f2f5;
      box-shadow: none;
      border: 1px solid transparent;
      padding: 12px 18px;
      &:focus {
        border-color: #6e8efb;
      }
    }
  }

  .send-btn {
    margin-left: 10px;
    background-color: #6e8efb;
    border: none;
    width: 48px;
    height: 48px;
    font-size: 24px;
    &:hover {
      background-color: #5a78e6;
    }
    &.pause-mode {
      background-color: #f56c6c;
      &:hover {
        background-color: #dd6161;
      }
    }
  }
}


// Override MdPreview background
:deep(.md-editor-preview-wrapper) {
    background-color: transparent !important;
}

:deep(.el-scrollbar__view) {
  padding: 10px;
}

@media (max-width: 1024px) {
  .chat-conversation {
    .hero-prompt-grid {
      grid-template-columns: 1fr;
    }
  }
}

@media (max-width: 768px) {
  .chat-conversation {
    padding: 14px;

    .job-assistant-hero {
      padding: 18px;
    }

    .hero-head h2 {
      font-size: 24px;
    }

    .ai-message .message-content,
    .user-message .message-content {
      max-width: 84%;
    }
  }

  .input-area {
    padding: 12px 14px;
  }
}
</style>
