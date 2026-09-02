export interface TelemetryEvent {
  id: string;
  timestamp: string;
  service: string;
  environment: string;
  severity: "DEBUG" | "INFO" | "WARN" | "ERROR" | "CRITICAL";
  event_type: string;
  message: string;
  metadata: Record<string, unknown>;
  trace_id: string | null;
  raw_source: string;
}

export interface ServiceInfo {
  name: string;
  kind: string;
  description: string;
  dependencies: string[];
  dependents: string[];
  error_rate: number | null;
}

export interface TopologyData {
  nodes: { id: string; name: string; kind: string; description: string }[];
  edges: { source: string; target: string; type: string; critical: boolean }[];
}

export interface Anomaly {
  service: string;
  metric: string;
  timestamp: string;
  value: number;
  baseline: number;
  z_score: number;
  method: string;
  explanation: string;
}

export interface Incident {
  id: string;
  title: string;
  status: string;
  severity: string;
  confidence: number;
  category: string;
  started_at: string;
  detected_at: string;
  resolved_at: string | null;
  affected_services: string[];
  signals: Record<string, unknown>[];
  root_cause: string | null;
  root_cause_confidence: number;
  scenario_id: string | null;
}

export interface TimelineEntry {
  timestamp: string;
  kind: string;
  label: string;
}

export interface EvidenceItem {
  id: string;
  kind: string;
  description: string;
  source_ref: string;
  observed_at: string | null;
}

export interface Hypothesis {
  id: string;
  statement: string;
  confidence: number;
  evidence_for: string[];
  evidence_against: string[];
  rank: number;
  verdict: string;
}

export interface InvestigationResult {
  run_id: string;
  incident_id: string;
  status: string;
  hypotheses: {
    statement: string;
    confidence: number;
    evidence_for: string[];
    evidence_against: string[];
    temporal_consistent?: boolean;
  }[];
  root_cause: string | null;
  root_cause_confidence: number;
  recommended_action: { action: string; target_service?: string; reason?: string } | null;
  summary: string;
  stop_reason: string;
  input_tokens: number;
  output_tokens: number;
  llm_request_count: number;
  tool_calls: { seq: number; tool: string; status: string; duration_ms: number }[];
  demo_mode: boolean;
}

export interface Remediation {
  id: string;
  incident_id: string;
  action: string;
  target_service: string;
  reason: string;
  expected_effect: string;
  risk: string;
  status: string;
  approval_state: string;
  initiated_by: string;
  approved_by: string | null;
  executed_at: string | null;
  result: string;
}

export interface Verification {
  id: string;
  incident_id: string;
  remediation_id: string | null;
  outcome: "recovered" | "partial" | "not_recovered" | "unknown";
  checked_metrics: Record<string, unknown>[];
  evidence: string[];
  checked_at: string;
}

export interface Postmortem {
  id: string;
  incident_id: string;
  title: string;
  content_markdown: string;
  generated_by: string;
  created_at: string;
}

export interface AgentRun {
  id: string;
  incident_id: string;
  status: string;
  provider: string;
  model: string;
  started_at: string;
  finished_at: string | null;
  summary: string;
  input_tokens: number;
  output_tokens: number;
  llm_request_count: number;
  stop_reason: string;
}

export interface ToolCallEntry {
  seq: number;
  tool: string;
  args: Record<string, unknown>;
  status: string;
  duration_ms: number;
  result_summary: string;
  error: string;
  created_at: string;
}

export interface EvaluationScenario {
  scenario_id: string;
  incident_id: string;
  known_root_cause: string;
  predicted_root_cause: string | null;
  root_cause_correct: boolean;
  affected_services_correct: boolean;
  remediation_correct: boolean | null;
  recovery_verified: boolean;
  evidence_count: number;
  tool_calls: number;
  failed_tool_calls: number;
  investigation_duration_ms: number;
  score: number;
}

export interface EvaluationReport {
  scenarios: EvaluationScenario[];
  aggregate: {
    root_cause_accuracy: number;
    affected_service_accuracy: number;
    remediation_accuracy: number;
    recovery_verification_rate: number;
    average_score: number;
    n_scenarios: number;
  };
}

export interface OverviewData {
  synthetic: boolean;
  environment: string;
  llm_enabled: boolean;
  active_incidents: Incident[];
  active_incident_count: number;
  affected_services: string[];
  service_count: number;
  gateway: { error_rate: number | null; p95_latency_ms: number | null; request_rate: number | null };
  recent_deployments: { timestamp: string; service: string; version: string }[];
  anomaly_count: number;
  anomalies: Anomaly[];
  latest_telemetry_time: string | null;
}

export interface Deployment {
  id: string;
  timestamp: string;
  service: string;
  version: string;
  commit: string;
  actor: string;
  notes: string;
}

export interface MetricSeries {
  service: string;
  metric: string;
  series: { timestamp: string; value: number }[];
  anomalies: Anomaly[];
}

export interface SettingsInfo {
  llm_provider: string;
  llm_model: string;
  llm_enabled: boolean;
  remediation_mode: string;
  demo_mode: boolean;
  agent_max_tool_calls: number;
}
