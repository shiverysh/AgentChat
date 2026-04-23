import { request } from "../utils/request"

export interface ApiResponse<T> {
  status_code: number
  status_message: string
  data: T
}

export interface EvalToolRuntime {
  average_elapsed_seconds: number
  max_elapsed_seconds: number
}

export interface EvalRuntimeSummary {
  average_elapsed_seconds: number
  max_elapsed_seconds: number
  tool_runtime: Record<string, EvalToolRuntime>
}

export interface EvalToolSummary {
  case_count: number
  passed_cases: number
  pass_rate: number
  average_score: number
  rule_average_score: number
  judge_average_score?: number | null
}

export interface EvalSummary {
  total_cases: number
  passed_cases: number
  pass_rate: number
  average_score: number
  rule_average_score: number
  judge_average_score?: number | null
  judge_enabled?: boolean
  runtime?: EvalRuntimeSummary
  tool_summary: Record<string, EvalToolSummary>
}

export interface EvalCaseResult {
  case_id: string
  tool: string
  overall_score: number
  rule_score: number
  judge_score?: number | null
  pass_threshold: number
  passed: boolean
  metric_scores: Record<string, number>
  judge_metric_scores?: Record<string, number>
  notes?: string[]
}

export interface EvalDashboardReport {
  generated_at: string
  run_label: string
  run_id: string
  config_path: string
  case_file: string
  judge_enabled: boolean
  judge_weight: number
  summary: EvalSummary
  cases: EvalCaseResult[]
  raw_results: Array<Record<string, any>>
}

export interface EvalReportSummary {
  report_name: string
  run_id: string
  run_label: string
  generated_at: string
  judge_enabled: boolean
  judge_weight?: number
  total_cases: number
  passed_cases: number
  pass_rate: number
  average_score: number
  rule_average_score: number
  judge_average_score?: number | null
  average_elapsed_seconds: number
}

export interface EvalCompareDelta {
  average_score_delta?: number
  rule_average_score_delta?: number
  judge_average_score_delta?: number
  pass_rate_delta?: number
  average_elapsed_seconds_delta?: number
  [key: string]: number | undefined
}

export interface EvalCompareReport {
  generated_at?: string
  current_label: string
  baseline_label: string
  overall_delta: EvalCompareDelta
  tool_deltas: Record<string, EvalCompareDelta>
}

export interface EvalCompareSummary {
  report_name: string
  generated_at: string
  current_label: string
  baseline_label: string
  overall_delta: EvalCompareDelta
  tool_deltas: Record<string, EvalCompareDelta>
}

export interface EvalDashboardOverview {
  latest_report: EvalDashboardReport | null
  latest_summary: EvalReportSummary | null
  history_reports: EvalReportSummary[]
  compare_reports: EvalCompareSummary[]
}

export interface EvalRunRequest {
  run_label: string
  tool: 'all' | 'resume_match' | 'resume_rewrite' | 'interview_followup'
  enable_judge: boolean
  judge_weight: number
  compare_latest: boolean
}

export interface EvalRunLog {
  time: string
  message: string
}

export interface EvalRunProgress {
  stage: string
  message: string
  total_cases: number
  completed_cases: number
  percent: number
  current_index: number
  current_case_id?: string | null
  current_tool?: string | null
  last_case_result?: {
    case_id: string
    tool: string
    overall_score: number
    passed: boolean
  } | null
}

export interface EvalRunResult {
  generated_at: string
  run_label: string
  run_id: string
  judge_enabled: boolean
  judge_weight: number
  summary: EvalSummary
  latest_report_name: string
  history_report_name: string
  comparison_report_name?: string | null
}

export interface EvalRunStatus {
  task_id: string | null
  status: 'idle' | 'queued' | 'running' | 'success' | 'error'
  created_at?: string | null
  started_at?: string | null
  finished_at?: string | null
  config?: {
    run_label: string
    tool: string
    enable_judge: boolean
    judge_weight: number
    compare_latest: boolean
  } | null
  progress?: EvalRunProgress | null
  logs: EvalRunLog[]
  result?: EvalRunResult | null
  error?: string | null
  is_active: boolean
}

export function getEvalDashboardOverviewAPI() {
  return request<ApiResponse<EvalDashboardOverview>>({
    url: '/api/v1/eval_dashboard/overview',
    method: 'GET',
  })
}

export function getEvalDashboardReportAPI(category: 'latest' | 'history' | 'compare', reportName?: string) {
  return request<ApiResponse<EvalDashboardReport | EvalCompareReport>>({
    url: '/api/v1/eval_dashboard/report',
    method: 'GET',
    params: {
      category,
      report_name: reportName,
    },
  })
}

export function startEvalDashboardRunAPI(payload: EvalRunRequest) {
  return request<ApiResponse<EvalRunStatus>>({
    url: '/api/v1/eval_dashboard/run',
    method: 'POST',
    data: payload,
  })
}

export function getEvalDashboardRunStatusAPI(taskId?: string) {
  return request<ApiResponse<EvalRunStatus>>({
    url: '/api/v1/eval_dashboard/run_status',
    method: 'GET',
    params: {
      task_id: taskId,
    },
  })
}
