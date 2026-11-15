export type SeverityLevel = 'CRITICAL' | 'HIGH' | 'MEDIUM' | 'LOW' | 'INFO';
export type MergeDecision = 'APPROVE' | 'REQUEST_CHANGES' | 'PENDING';
export type ReviewStatus = 'PENDING' | 'RUNNING' | 'COMPLETED' | 'FAILED';

export interface Finding {
  id: string;
  agent: string;
  file: string;
  line?: number;
  severity: SeverityLevel;
  category: string;
  title: string;
  description: string;
  recommendation: string;
  evidence?: string;
  created_at?: string;
}

export interface AgentExecution {
  id: string;
  agent_name: string;
  status: string;
  findings_count: number;
  started_at?: string;
  completed_at?: string;
  error_message?: string;
  tools_invoked: string[];
  duration_seconds?: number;
}

export interface SuggestedPatch {
  id: string;
  finding_title: string;
  before_code: string;
  after_code: string;
  explanation: string;
  expected_result: string;
  is_valid: boolean;
}

export interface ReviewSummary {
  id: string;
  repo_name?: string;
  language: string;
  status: ReviewStatus;
  merge_decision: MergeDecision;
  total_findings: number;
  critical_count: number;
  high_count: number;
  medium_count: number;
  low_count: number;
  info_count: number;
  created_at: string;
  completed_at?: string;
}

export interface ReviewDetail extends ReviewSummary {
  decision_reason?: string;
  findings: Finding[];
  agent_executions: AgentExecution[];
  patches: SuggestedPatch[];
}

export interface CreateReviewRequest {
  diff_text: string;
  repo_name?: string;
  language: string;
  submission_type: string;
}
