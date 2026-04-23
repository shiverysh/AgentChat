import type { ExecutionRecord, ExecutionRecordKind } from "../type"

type ExecutionEventPayload = {
  event_type?: string
  call_id?: string
  call_kind?: string
  call_name?: string
  raw_name?: string
  parent_name?: string
  call_scope?: string
  status?: string
  message?: string
  title?: string
}

function normalizeExecutionKind(value: unknown): ExecutionRecordKind | null {
  if (
    value === 'tool' ||
    value === 'mcp' ||
    value === 'skill' ||
    value === 'mcp_tool' ||
    value === 'skill_tool'
  ) {
    return value
  }
  return null
}

function normalizeStatus(value: unknown): 'START' | 'END' | 'ERROR' {
  if (value === 'START' || value === 'END' || value === 'ERROR') {
    return value
  }
  return 'END'
}

function parseLegacyExecution(title: string, payload: ExecutionEventPayload): ExecutionRecord | null {
  const directToolMatch = title.match(/^执行可用工具:\s*(.+)$/)
  if (directToolMatch) {
    const name = directToolMatch[1].trim()
    return {
      id: `legacy-tool:${name}`,
      kind: 'tool',
      name,
      rawName: name,
      status: normalizeStatus(payload.status),
      message: payload.message || '',
      scope: 'agent',
    }
  }

  const typedToolMatch = title.match(/^执行可用(MCP|Skill|工具):\s*(.+)$/)
  if (typedToolMatch) {
    const rawKind = typedToolMatch[1]
    const name = typedToolMatch[2].trim()
    const kindMap: Record<string, ExecutionRecordKind> = {
      MCP: 'mcp',
      Skill: 'skill',
      工具: 'tool',
    }
    return {
      id: `legacy-${rawKind}:${name}`,
      kind: kindMap[rawKind] || 'tool',
      name,
      rawName: name,
      status: normalizeStatus(payload.status),
      message: payload.message || '',
      scope: 'agent',
    }
  }

  const mcpToolMatch = title.match(/^Sub-Agent\s*-\s*(.+)执行可用工具:\s*(.+)$/)
  if (mcpToolMatch) {
    const parentName = mcpToolMatch[1].trim()
    const name = mcpToolMatch[2].trim()
    return {
      id: `legacy-mcp-tool:${parentName}:${name}`,
      kind: 'mcp_tool',
      name,
      rawName: name,
      parentName,
      status: normalizeStatus(payload.status),
      message: payload.message || '',
      scope: 'mcp_agent',
    }
  }

  const skillToolMatch = title.match(/^Skill-Agent\s*-\s*(.+)执行可用工具:\s*(.+)$/)
  if (skillToolMatch) {
    const parentName = skillToolMatch[1].trim()
    const name = skillToolMatch[2].trim()
    return {
      id: `legacy-skill-tool:${parentName}:${name}`,
      kind: 'skill_tool',
      name,
      rawName: name,
      parentName,
      status: normalizeStatus(payload.status),
      message: payload.message || '',
      scope: 'skill_agent',
    }
  }

  return null
}

export function parseExecutionRecordFromEvent(event: any): ExecutionRecord | null {
  const payload: ExecutionEventPayload = event?.data ?? event
  if (!payload || typeof payload !== 'object') {
    return null
  }

  if (payload.event_type === 'agent_execution') {
    const kind = normalizeExecutionKind(payload.call_kind)
    if (!kind || !payload.call_name || !payload.raw_name) {
      return null
    }

    return {
      id: payload.call_id || `${kind}:${payload.parent_name || 'root'}:${payload.raw_name}`,
      kind,
      name: payload.call_name,
      rawName: payload.raw_name,
      parentName: payload.parent_name,
      scope: payload.call_scope,
      status: normalizeStatus(payload.status),
      message: payload.message || '',
    }
  }

  if (typeof payload.title === 'string' && payload.title.trim()) {
    return parseLegacyExecution(payload.title.trim(), payload)
  }

  return null
}

export function upsertExecutionRecord(
  records: ExecutionRecord[],
  nextRecord: ExecutionRecord,
): ExecutionRecord[] {
  const existingIndex = records.findIndex(record => record.id === nextRecord.id)
  if (existingIndex === -1) {
    return [...records, nextRecord]
  }

  const mergedRecords = [...records]
  mergedRecords[existingIndex] = {
    ...mergedRecords[existingIndex],
    ...nextRecord,
    message: nextRecord.message || mergedRecords[existingIndex].message,
  }
  return mergedRecords
}
