import type {
  ChatMessage,
  InterviewFollowupResult,
  InterviewQuestionAnswerPair,
  ResumeMatchResult,
  ResumeRewriteResult,
  ToolOutputCard,
} from "../type"

interface JsonCandidate {
  raw: string
  normalized: string
}

interface ExtractedToolOutput {
  card: ToolOutputCard
  rawSegment: string
}

function normalizeJsonCandidate(value: string): string {
  return value
    .trim()
    .replace(/^```json\s*/i, '')
    .replace(/^```\s*/i, '')
    .replace(/\s*```$/i, '')
    .trim()
}

function tryParseJsonCandidate(candidate: JsonCandidate): unknown {
  try {
    return JSON.parse(candidate.normalized)
  } catch {
    return null
  }
}

function collectFencedJsonCandidates(content: string): JsonCandidate[] {
  const candidates: JsonCandidate[] = []
  const fenceRegex = /```(?:json)?\s*([\s\S]*?)```/gi

  for (const match of content.matchAll(fenceRegex)) {
    const raw = match[0]
    const inner = match[1]
    if (!raw || !inner) {
      continue
    }

    candidates.push({
      raw,
      normalized: normalizeJsonCandidate(inner),
    })
  }

  return candidates
}

function collectBalancedObjectCandidates(content: string): JsonCandidate[] {
  const candidates: JsonCandidate[] = []
  let depth = 0
  let start = -1
  let inString = false
  let escaped = false

  for (let index = 0; index < content.length; index += 1) {
    const char = content[index]

    if (escaped) {
      escaped = false
      continue
    }

    if (char === '\\' && inString) {
      escaped = true
      continue
    }

    if (char === '"') {
      inString = !inString
      continue
    }

    if (inString) {
      continue
    }

    if (char === '{') {
      if (depth === 0) {
        start = index
      }
      depth += 1
      continue
    }

    if (char === '}') {
      if (depth === 0) {
        continue
      }

      depth -= 1
      if (depth === 0 && start >= 0) {
        const raw = content.slice(start, index + 1)
        candidates.push({
          raw,
          normalized: normalizeJsonCandidate(raw),
        })
        start = -1
      }
    }
  }

  return candidates
}

function collectJsonCandidates(content: string): JsonCandidate[] {
  const trimmed = content.trim()
  if (!trimmed) {
    return []
  }

  const candidates: JsonCandidate[] = [
    {
      raw: content,
      normalized: normalizeJsonCandidate(content),
    },
    ...collectFencedJsonCandidates(content),
    ...collectBalancedObjectCandidates(content),
  ]

  const uniqueCandidates = new Map<string, JsonCandidate>()
  candidates.forEach((candidate) => {
    const raw = candidate.raw
    const normalized = candidate.normalized.trim()
    if (!raw.trim() || !normalized) {
      return
    }

    const key = `${raw.trim()}__${normalized}`
    if (!uniqueCandidates.has(key)) {
      uniqueCandidates.set(key, {
        raw,
        normalized,
      })
    }
  })

  return Array.from(uniqueCandidates.values())
}

function tryParseJsonLike(value: unknown): unknown {
  if (typeof value !== 'string') {
    return value
  }

  for (const candidate of collectJsonCandidates(value)) {
    const parsed = tryParseJsonCandidate(candidate)
    if (parsed !== null) {
      return parsed
    }
  }

  return value
}

function isParsedJsonPayload(value: unknown): boolean {
  return typeof value === 'object' && value !== null
}

function isStringArray(value: unknown): value is string[] {
  return Array.isArray(value) && value.every(item => typeof item === 'string')
}

function isInterviewQuestionAnswerPair(value: unknown): value is InterviewQuestionAnswerPair {
  if (!value || typeof value !== 'object') {
    return false
  }

  const candidate = value as InterviewQuestionAnswerPair
  return (
    typeof candidate.dimension === 'string' &&
    typeof candidate.question === 'string' &&
    typeof candidate.answer_outline === 'string' &&
    typeof candidate.why_it_matters === 'string'
  )
}

export function isResumeMatchResult(value: unknown): value is ResumeMatchResult {
  if (!value || typeof value !== 'object') {
    return false
  }

  const candidate = value as ResumeMatchResult
  return (
    typeof candidate.target_role === 'string' &&
    typeof candidate.overall_summary === 'string' &&
    typeof candidate.match_score === 'number' &&
    isStringArray(candidate.matched_strengths) &&
    isStringArray(candidate.missing_requirements) &&
    isStringArray(candidate.revision_suggestions) &&
    isStringArray(candidate.interview_focus)
  )
}

export function isResumeRewriteResult(value: unknown): value is ResumeRewriteResult {
  if (!value || typeof value !== 'object') {
    return false
  }

  const candidate = value as ResumeRewriteResult
  return (
    typeof candidate.target_role === 'string' &&
    typeof candidate.overall_strategy === 'string' &&
    isStringArray(candidate.detected_issues) &&
    isStringArray(candidate.rewritten_resume) &&
    isStringArray(candidate.supplement_suggestions) &&
    isStringArray(candidate.highlight_keywords)
  )
}

export function isInterviewFollowupResult(value: unknown): value is InterviewFollowupResult {
  if (!value || typeof value !== 'object') {
    return false
  }

  const candidate = value as InterviewFollowupResult
  return (
    typeof candidate.target_role === 'string' &&
    typeof candidate.overall_summary === 'string' &&
    Array.isArray(candidate.question_answer_pairs) &&
    candidate.question_answer_pairs.every(item => isInterviewQuestionAnswerPair(item)) &&
    isStringArray(candidate.deep_dive_points) &&
    isStringArray(candidate.risk_points)
  )
}

export function parseToolOutputFromEvent(event: any): ToolOutputCard | null {
  const data = event?.data ?? event
  if (!data || typeof data !== 'object') {
    return null
  }

  const structuredData = tryParseJsonLike(data.structured_data)
  if (data.event_type === 'resume_match_result' && isResumeMatchResult(structuredData)) {
    return {
      type: 'resume_match',
      payload: structuredData,
    }
  }

  if (data.event_type === 'resume_rewrite_result' && isResumeRewriteResult(structuredData)) {
    return {
      type: 'resume_rewrite',
      payload: structuredData,
    }
  }

  if (data.event_type === 'interview_followup_result' && isInterviewFollowupResult(structuredData)) {
    return {
      type: 'interview_followup',
      payload: structuredData,
    }
  }

  return null
}

export function parseToolOutputFromContent(content: string): ToolOutputCard | null {
  return extractToolOutputFromContent(content)?.card || null
}

export function getToolOutputCardKey(card: ToolOutputCard): string {
  return `${card.type}:${JSON.stringify(card.payload)}`
}

export function appendToolOutputCard(cards: ToolOutputCard[], nextCard: ToolOutputCard): ToolOutputCard[] {
  const nextKey = getToolOutputCardKey(nextCard)
  if (cards.some(card => getToolOutputCardKey(card) === nextKey)) {
    return cards
  }

  return [...cards, nextCard]
}

export function hydrateToolOutputCardsFromMessage(message: ChatMessage): ChatMessage {
  const content = message.aiMessage?.content || ''
  if (!content.trim()) {
    return message
  }

  const parsedContent = tryParseJsonLike(content)
  const extractedToolOutput = extractToolOutputFromContent(content)
  if (!extractedToolOutput) {
    if ((message.toolOutputs?.length || 0) > 0 && isParsedJsonPayload(parsedContent)) {
      message.aiMessage.content = ''
    }
    return message
  }

  message.toolOutputs = appendToolOutputCard(message.toolOutputs || [], extractedToolOutput.card)
  message.aiMessage.content = cleanupResidualContent(content, extractedToolOutput.rawSegment)
  return message
}

function extractToolOutputFromContent(content: string): ExtractedToolOutput | null {
  for (const candidate of collectJsonCandidates(content)) {
    const parsed = tryParseJsonCandidate(candidate)
    if (!parsed || typeof parsed !== 'object') {
      continue
    }

    if (isResumeMatchResult(parsed)) {
      return {
        card: {
          type: 'resume_match',
          payload: parsed,
        },
        rawSegment: candidate.raw,
      }
    }

    if (isResumeRewriteResult(parsed)) {
      return {
        card: {
          type: 'resume_rewrite',
          payload: parsed,
        },
        rawSegment: candidate.raw,
      }
    }

    if (isInterviewFollowupResult(parsed)) {
      return {
        card: {
          type: 'interview_followup',
          payload: parsed,
        },
        rawSegment: candidate.raw,
      }
    }
  }

  return null
}

function cleanupResidualContent(content: string, rawSegment: string): string {
  const residual = content.replace(rawSegment, '')
  const lines = residual
    .split('\n')
    .map(line => line.trim())
    .filter(Boolean)
    .filter(line => !isLowSignalResidualLine(line))

  return lines.join('\n').trim()
}

function isLowSignalResidualLine(line: string): boolean {
  return /^(总结如下|结果如下|分析如下|输出如下|返回如下|以下是结果|以下为结果|如下|总结|结果|分析|输出)[：:]?$/i.test(line)
}
