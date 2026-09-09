/**
 * Typed API client — Phase 11.
 *
 * Wraps the auth-aware axios instance from ``@/api/workflow`` in React Query
 * hooks and Zod-validated schemas. The runtime validators double as TS type
 * sources (``z.infer<typeof X>``), so the wire format is described in exactly
 * one place.
 *
 * Why this exists:
 *
 * * All components now share one canonical type per resource — no more drifting
 *   ``any`` shapes.
 * * React Query gives us caching, request deduplication, automatic refetch on
 *   focus, and optimistic updates for free.
 * * Zod runtime validation catches backend schema drift (a field gets renamed,
 *   a number becomes a string, etc.) and surfaces it as a typed parse error
 *   rather than a silent UI bug.
 *
 * This module deliberately does NOT re-implement the axios interceptor or the
 * login/refresh dance — it imports the existing ``apiClient`` and token getter
 * so auth behaviour stays in one place.
 */
import {
  useQuery,
  useMutation,
  useQueryClient,
  type UseQueryOptions,
} from "@tanstack/react-query";
import { z } from "zod";

import { apiClient, setAccessToken } from "@/api/workflow";

// ---------------------------------------------------------------------------
// Zod schemas — single source of truth for wire format
// ---------------------------------------------------------------------------
const uuidSchema = z.string().uuid();

export const addressSchema = z.object({
  id: uuidSchema.optional(),
  flat: z.string().nullable().optional(),
  building: z.string().nullable().optional(),
  village_town: z.string().nullable().optional(),
  block: z.string().nullable().optional(),
  road_street: z.string().nullable().optional(),
  city: z.string().nullable().optional(),
  pin: z.string().nullable().optional(),
  state: z.string().nullable().optional(),
  district: z.string().nullable().optional(),
});
export type Address = z.infer<typeof addressSchema>;

export const applicationUnitSchema = addressSchema.extend({
  id: uuidSchema.optional(),
  unit_name: z.string(),
  application_id: uuidSchema.optional(),
});
export type ApplicationUnit = z.infer<typeof applicationUnitSchema>;

export const clientSchema = z.object({
  id: uuidSchema,
  business_name: z.string(),
  applicant_name: z.string(),
  mobile_number: z.string(),
  email: z.string().nullable().optional(),
  pan_number: z.string(),
  gender: z.string().nullable().optional(),
  social_category: z.string().nullable().optional(),
  divyang_status: z.boolean().nullable().optional(),
  branch_id: uuidSchema.optional(),
  created_at: z.string().optional(),
  updated_at: z.string().optional(),
  application_count: z.number().optional(),
  active_count: z.number().optional(),
});
export type Client = z.infer<typeof clientSchema>;

export const documentSchema = z.object({
  id: uuidSchema,
  application_id: uuidSchema,
  type: z.string(),
  file_name: z.string(),
  mime_type: z.string(),
  size_bytes: z.number(),
  ocr_status: z.string(),
  created_at: z.string(),
});
export type DocumentRecord = z.infer<typeof documentSchema>;

export const userListSchema = z.object({
  id: uuidSchema,
  name: z.string(),
  email: z.string(),
  role: z.string(),
  branch_id: uuidSchema.nullable().optional(),
  status: z.string(),
  created_at: z.string(),
  updated_at: z.string(),
  last_active: z.string().nullable().optional(),
});
export type UserListItem = z.infer<typeof userListSchema>;

export const reportsOverviewSchema = z.object({
  generated_at: z.string(),
  total_applications: z.number(),
  completed_applications: z.number(),
  pending_applications: z.number(),
  exceptions: z.number(),
  success_rate: z.number(),
  average_processing_seconds: z.number().nullable().optional(),
  completions_by_day: z.array(
    z.object({ key: z.string(), label: z.string(), count: z.number() }),
  ),
  status_distribution: z.array(
    z.object({ status: z.string(), count: z.number() }),
  ),
  top_nic_codes: z.array(
    z.object({ code: z.string(), description: z.string(), count: z.number() }),
  ),
});
export type ReportsOverview = z.infer<typeof reportsOverviewSchema>;

export const workflowStageCountSchema = z.object({
  key: z.string(),
  label: z.string(),
  description: z.string(),
  count: z.number(),
});
export type WorkflowStageCount = z.infer<typeof workflowStageCountSchema>;

export const workflowsSummarySchema = z.object({
  stages: z.array(workflowStageCountSchema),
  total_in_flight: z.number(),
});
export type WorkflowsSummary = z.infer<typeof workflowsSummarySchema>;

export const applicationSchema = z.object({
  id: uuidSchema,
  application_number: z.string(),
  workflow_type: z.string(),
  status: z.string(),
  client_id: uuidSchema,
  branch_id: uuidSchema,
  enterprise_type: z.string().nullable().optional(),
  bank_name: z.string().nullable().optional(),
  bank_account_number: z.string().nullable().optional(),
  bank_ifsc: z.string().nullable().optional(),
  major_activity: z.string().nullable().optional(),
  net_investment: z.number().nullable().optional(),
  total_turnover: z.number().nullable().optional(),
  created_at: z.string(),
  updated_at: z.string(),
  client: clientSchema.nullable().optional(),
  official_address: addressSchema.nullable().optional(),
  units: z.array(applicationUnitSchema).optional(),
  workflow: z.object({
    id: z.string(),
    current_node: z.string().optional(),
    status: z.string().optional(),
  }).nullable().optional(),
});
export type Application = z.infer<typeof applicationSchema>;

export const auditLogSchema = z.object({
  id: uuidSchema,
  actor_id: uuidSchema.nullable().optional(),
  application_id: uuidSchema.nullable().optional(),
  action: z.string(),
  ip_address: z.string().nullable().optional(),
  user_agent: z.string().nullable().optional(),
  metadata_json: z.record(z.unknown()).optional(),
  created_at: z.string(),
});
export type AuditLog = z.infer<typeof auditLogSchema>;

export const workflowEventSchema = z.object({
  id: uuidSchema,
  application_id: uuidSchema,
  workflow_id: uuidSchema,
  node_key: z.string(),
  event_type: z.string(),
  status: z.string(),
  payload_json: z.record(z.unknown()).nullable().optional(),
  error_code: z.string().nullable().optional(),
  created_at: z.string(),
});
export type WorkflowEvent = z.infer<typeof workflowEventSchema>;

export const nicSuggestionSchema = z.object({
  id: uuidSchema.optional(),
  nic_2digit: z.string(),
  nic_4digit: z.string(),
  nic_5digit: z.string(),
  description: z.string(),
  confidence: z.number(),
  rationale: z.string().nullable().optional(),
});
export type NicSuggestion = z.infer<typeof nicSuggestionSchema>;

// ---------------------------------------------------------------------------
// Query keys — central registry avoids stringly-typed cache misses
// ---------------------------------------------------------------------------
export const queryKeys = {
  applications: ["applications"] as const,
  application: (id: string) => ["applications", id] as const,
  auditLog: (id: string) => ["applications", id, "audit"] as const,
  workflowEvents: (id: string) =>
    ["applications", id, "workflow-events"] as const,
  nicSuggestions: (id: string) => ["applications", id, "nic"] as const,
  clients: ["clients"] as const,
  users: ["users"] as const,
  documents: ["documents"] as const,
  reportsOverview: ["reports", "overview"] as const,
  workflowsSummary: ["workflows", "summary"] as const,
};

// ---------------------------------------------------------------------------
// Fetcher — parses through Zod, surfaces validation errors as throws
// ---------------------------------------------------------------------------
async function fetchJson<T>(schema: z.ZodType<T>, path: string): Promise<T> {
  const res = await apiClient.get(path);
  const parsed = schema.safeParse(res.data);
  if (!parsed.success) {
    // Don't swallow — caller can branch on ZodError for field-level messages.
    throw parsed.error;
  }
  return parsed.data;
}

// ---------------------------------------------------------------------------
// Application hooks
// ---------------------------------------------------------------------------
export function useApplications(
  options?: Omit<UseQueryOptions<Application[]>, "queryKey" | "queryFn">,
) {
  return useQuery({
    queryKey: queryKeys.applications,
    queryFn: () => fetchJson(z.array(applicationSchema), "/applications"),
    ...options,
  });
}

export function useApplication(
  id: string | null | undefined,
  options?: Omit<UseQueryOptions<Application>, "queryKey" | "queryFn">,
) {
  return useQuery({
    queryKey: queryKeys.application(id ?? "__none__"),
    queryFn: () => fetchJson(applicationSchema, `/applications/${id}`),
    enabled: Boolean(id),
    ...options,
  });
}

export function useApplicationAuditLog(
  id: string | null | undefined,
  options?: Omit<UseQueryOptions<AuditLog[]>, "queryKey" | "queryFn">,
) {
  return useQuery({
    queryKey: queryKeys.auditLog(id ?? "__none__"),
    queryFn: () =>
      fetchJson(z.array(auditLogSchema), `/applications/${id}/audit`),
    enabled: Boolean(id),
    ...options,
  });
}

export function useApplicationWorkflowEvents(
  id: string | null | undefined,
  options?: Omit<UseQueryOptions<WorkflowEvent[]>, "queryKey" | "queryFn">,
) {
  return useQuery({
    queryKey: queryKeys.workflowEvents(id ?? "__none__"),
    queryFn: () =>
      fetchJson(
        z.array(workflowEventSchema),
        `/applications/${id}/workflow-events`,
      ),
    enabled: Boolean(id),
    ...options,
  });
}

// ---------------------------------------------------------------------------
// Mutations
// ---------------------------------------------------------------------------
export function useSearchNIC(applicationId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (businessDescription: string) => {
      const res = await apiClient.post(
        `/applications/${applicationId}/nic/search`,
        {
          business_description: businessDescription,
          location_text: "India",
        },
      );
      return z.array(nicSuggestionSchema).parse(res.data);
    },
    onSuccess: (data) => {
      qc.setQueryData(queryKeys.nicSuggestions(applicationId), data);
    },
  });
}

export function useApproveNIC(applicationId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (input: {
      nic_suggestion_id?: string;
      override_code_5digit?: string;
    }) => {
      const res = await apiClient.post(
        `/applications/${applicationId}/nic/approve`,
        input,
      );
      return res.data;
    },
    onSuccess: () => {
      // Status change → refetch the application + workflow events so the
      // stepper / audit timeline update without manual cache wiring.
      qc.invalidateQueries({ queryKey: queryKeys.application(applicationId) });
      qc.invalidateQueries({
        queryKey: queryKeys.workflowEvents(applicationId),
      });
    },
  });
}

export function useSubmitOTP(applicationId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (input: { otp_type: string; code: string }) => {
      const res = await apiClient.post(
        `/applications/${applicationId}/otp`,
        input,
      );
      return res.data;
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: queryKeys.application(applicationId) });
    },
  });
}

// ---------------------------------------------------------------------------
// Auth mutations — thin wrappers around the imperative helpers in
// ``@/api/workflow`` so components can compose with React Query patterns.
// ---------------------------------------------------------------------------
export function useLogin() {
  return useMutation({
    mutationFn: async (input: { username: string; password: string }) => {
      const res = await apiClient.post("/auth/login", input);
      const { access_token, user } = res.data as {
        access_token: string;
        user: unknown;
      };
      setAccessToken(access_token);
      return { user, accessToken: access_token };
    },
  });
}

// ---------------------------------------------------------------------------
// Phase 14 — directory endpoints that replaced the frontend's MOCK_*
// arrays. All four pages (clients, users, documents, reports) now read
// from real backend data; the workflows page reads /workflows/summary.
// ---------------------------------------------------------------------------

export function useClients(
  options?: Omit<UseQueryOptions<Client[]>, "queryKey" | "queryFn">,
) {
  return useQuery({
    queryKey: queryKeys.clients,
    queryFn: () => fetchJson(z.array(clientSchema), "/clients"),
    ...options,
  });
}

export function useUsers(
  options?: Omit<UseQueryOptions<UserListItem[]>, "queryKey" | "queryFn">,
) {
  return useQuery({
    queryKey: queryKeys.users,
    queryFn: () => fetchJson(z.array(userListSchema), "/users"),
    ...options,
  });
}

export function useDocuments(
  options?: Omit<UseQueryOptions<DocumentRecord[]>, "queryKey" | "queryFn">,
) {
  return useQuery({
    queryKey: queryKeys.documents,
    queryFn: () => fetchJson(z.array(documentSchema), "/documents"),
    ...options,
  });
}

export function useReportsOverview(
  options?: Omit<UseQueryOptions<ReportsOverview>, "queryKey" | "queryFn">,
) {
  return useQuery({
    queryKey: queryKeys.reportsOverview,
    queryFn: () => fetchJson(reportsOverviewSchema, "/reports/overview"),
    staleTime: 30_000,
    refetchInterval: 60_000,
    ...options,
  });
}

export function useWorkflowsSummary(
  options?: Omit<UseQueryOptions<WorkflowsSummary>, "queryKey" | "queryFn">,
) {
  return useQuery({
    queryKey: queryKeys.workflowsSummary,
    queryFn: () => fetchJson(workflowsSummarySchema, "/workflows/summary"),
    refetchInterval: 30_000,
    ...options,
  });
}

// ---------------------------------------------------------------------------
// Phase 15 — Requirements, AI Intake, and Requirement Document Generation
// ---------------------------------------------------------------------------

export const requirementItemSchema = z.object({
  id: z.string(),
  requirement_key: z.string(),
  display_label: z.string(),
  category: z.string(),
  is_required: z.boolean(),
  is_completed: z.boolean(),
  source: z.string().nullable().optional(),
  value: z.string().nullable().optional(),
  validation_status: z.string(),
  validation_error: z.string().nullable().optional(),
  sort_order: z.number(),
});
export type RequirementItem = z.infer<typeof requirementItemSchema>;

export const requirementsListSchema = z.object({
  application_id: z.string(),
  completion_percentage: z.number(),
  requirements: z.array(requirementItemSchema),
});
export type RequirementsList = z.infer<typeof requirementsListSchema>;

export const intakeQuestionSchema = z.object({
  all_completed: z.boolean(),
  completion_percentage: z.number().optional(),
  message: z.string().optional(),
  requirement_key: z.string().optional(),
  field: z.string().optional(),
  question: z.string().optional(),
  type: z.string().optional(),
  options: z.array(z.string()).optional(),
  placeholder: z.string().optional(),
  category: z.string().optional(),
  current_index: z.number().optional(),
  total_questions: z.number().optional(),
  progress_percentage: z.number().optional(),
});
export type IntakeQuestion = z.infer<typeof intakeQuestionSchema>;

export const generatedDocumentSchema = z.object({
  id: z.string(),
  application_id: z.string(),
  document_title: z.string(),
  format: z.string(),
  file_size_bytes: z.number(),
  status: z.string(),
  created_at: z.string().nullable().optional(),
  download_url: z.string(),
});
export type GeneratedDocumentItem = z.infer<typeof generatedDocumentSchema>;

export function useApplicationRequirements(applicationId?: string) {
  return useQuery({
    queryKey: ["application-requirements", applicationId],
    queryFn: () => fetchJson(requirementsListSchema, `/applications/${applicationId}/requirements`),
    enabled: Boolean(applicationId),
  });
}

export function useNextIntakeQuestion(applicationId?: string) {
  return useQuery({
    queryKey: ["intake-next-question", applicationId],
    queryFn: () => fetchJson(intakeQuestionSchema, `/applications/${applicationId}/intake/next-question`),
    enabled: Boolean(applicationId),
  });
}

export function useRequirementDocuments(applicationId?: string) {
  return useQuery({
    queryKey: ["requirement-documents", applicationId],
    queryFn: () => fetchJson(z.array(generatedDocumentSchema), `/applications/${applicationId}/requirement-documents`),
    enabled: Boolean(applicationId),
  });
}

export function useTemplatePreview(applicationId?: string) {
  return useQuery({
    queryKey: ["template-preview", applicationId],
    queryFn: async () => {
      const res = await apiClient.get(`/applications/${applicationId}/template-preview`);
      return res.data;
    },
    enabled: Boolean(applicationId),
  });
}

export function useSubmitIntakeAnswer() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({ applicationId, fieldKey, answer }: { applicationId: string; fieldKey: string; answer: string }) => {
      const res = await apiClient.post(`/applications/${applicationId}/intake/answer`, {
        field_key: fieldKey,
        answer,
      });
      return res.data;
    },
    onSuccess: (_, vars) => {
      qc.invalidateQueries({ queryKey: ["intake-next-question", vars.applicationId] });
      qc.invalidateQueries({ queryKey: ["application-requirements", vars.applicationId] });
      qc.invalidateQueries({ queryKey: queryKeys.application(vars.applicationId) });
      qc.invalidateQueries({ queryKey: queryKeys.applications });
    },
  });
}

export function useGenerateRequirementDocuments() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({ applicationId, customTemplateData }: { applicationId: string; customTemplateData?: any }) => {
      const res = await apiClient.post(`/applications/${applicationId}/requirement-documents`, {
        custom_template_data: customTemplateData,
      });
      return res.data;
    },
    onSuccess: (_, vars) => {
      qc.invalidateQueries({ queryKey: ["requirement-documents", vars.applicationId] });
    },
  });
}

export function useReprocessDocument() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (documentId: string) => {
      const res = await apiClient.post(`/documents/${documentId}/reprocess`);
      return res.data;
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: queryKeys.documents });
    },
  });
}

export function useDocumentExtractedFields(documentId?: string) {
  return useQuery({
    queryKey: ["document-extracted-fields", documentId],
    queryFn: async () => {
      const res = await apiClient.get(`/documents/${documentId}/extracted-fields`);
      return res.data;
    },
    enabled: Boolean(documentId),
  });
}

export function useApplicationDocuments(applicationId?: string) {
  return useQuery({
    queryKey: ["application-documents", applicationId],
    queryFn: () => fetchJson(z.array(documentSchema), `/applications/${applicationId}/documents`),
    enabled: Boolean(applicationId),
  });
}

export function useUploadDocument() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({ applicationId, file, documentType }: { applicationId: string; file: File; documentType: string }) => {
      const formData = new FormData();
      formData.append("file", file);
      formData.append("document_type", documentType);
      const res = await apiClient.post(`/applications/${applicationId}/documents`, formData, {
        headers: { "Content-Type": "multipart/form-data" },
      });
      return res.data;
    },
    onSuccess: (_, vars) => {
      qc.invalidateQueries({ queryKey: ["application-documents", vars.applicationId] });
      qc.invalidateQueries({ queryKey: queryKeys.documents });
      qc.invalidateQueries({ queryKey: ["application-requirements", vars.applicationId] });
      qc.invalidateQueries({ queryKey: queryKeys.application(vars.applicationId) });
    },
  });
}

export function useExecuteWorkflowStep() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({ workflowId, payload }: { workflowId: string; payload?: Record<string, any> }) => {
      const res = await apiClient.post(`/workflow/${workflowId}/execute-step`, payload || {});
      return res.data;
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: queryKeys.applications });
    },
  });
}

export function useCreateApplication() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (payload: {
      branch_id: string;
      business_name: string;
      applicant_name: string;
      mobile_number: string;
      email?: string;
      pan_number: string;
      aadhaar_number: string;
      gender?: string;
      social_category?: string;
      divyang_status?: boolean;
      workflow_type?: string;
    }) => {
      const res = await apiClient.post("/applications", payload);
      return res.data;
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: queryKeys.applications });
    },
  });
}

// ---------------------------------------------------------------------------
// Autonomous Automation & Visualizer Hooks
// ---------------------------------------------------------------------------

export interface NodeExecution {
  id: string;
  execution_id: string;
  node_id: string;
  node_label: string;
  node_type: string;
  status: "WAITING" | "QUEUED" | "RUNNING" | "SUCCESS" | "FAILED" | "PAUSED" | "HUMAN_REQUIRED" | "SKIPPED" | "CANCELLED";
  attempt: number;
  max_attempts: number;
  worker_id?: string | null;
  input_summary?: Record<string, any> | null;
  output_summary?: Record<string, any> | null;
  error_message?: string | null;
  logs_text?: string | null;
  screenshot_path?: string | null;
  started_at?: string | null;
  completed_at?: string | null;
  duration_seconds?: number | null;
}

export interface CheckpointItem {
  id: string;
  execution_id: string;
  application_id: string;
  node_execution_id?: string | null;
  checkpoint_type: "OTP" | "CAPTCHA" | "DATA_REVIEW" | "NIC_APPROVAL" | "FINAL_APPROVAL" | "EXCEPTION";
  status: "PENDING" | "RESOLVED" | "EXPIRED" | "CANCELLED";
  title: string;
  prompt_message: string;
  context_data?: Record<string, any> | null;
  resolution_data?: Record<string, any> | null;
  created_at?: string | null;
  resolved_at?: string | null;
}

export interface ExecutionGraphData {
  execution_id: string;
  application_id: string;
  workflow_version: string;
  status: "RUNNING" | "PAUSED" | "HUMAN_REQUIRED" | "COMPLETED" | "FAILED" | "CANCELLED";
  current_node_id: string;
  started_at?: string | null;
  completed_at?: string | null;
  duration_seconds?: number | null;
  trigger_source: string;
  error_message?: string | null;
  nodes: NodeExecution[];
  checkpoints: CheckpointItem[];
  live_screenshot_url?: string | null;
}

export function useApplicationExecution(applicationId?: string) {
  return useQuery<ExecutionGraphData>({
    queryKey: ["application-execution", applicationId],
    queryFn: async () => {
      const res = await apiClient.get(`/applications/${applicationId}/automation/execution`);
      return res.data;
    },
    enabled: Boolean(applicationId),
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      return status === "RUNNING" ? 1500 : false;
    },
  });
}

export function usePauseExecution() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({ executionId, reason }: { executionId: string; reason?: string }) => {
      const res = await apiClient.post(`/executions/${executionId}/pause`, { reason });
      return res.data;
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["application-execution"] });
    },
  });
}

export function useResumeExecution() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({ executionId }: { executionId: string }) => {
      const res = await apiClient.post(`/executions/${executionId}/resume`);
      return res.data;
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["application-execution"] });
    },
  });
}

export function useCancelExecution() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({ executionId, reason }: { executionId: string; reason?: string }) => {
      const res = await apiClient.post(`/executions/${executionId}/cancel`, { reason });
      return res.data;
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["application-execution"] });
    },
  });
}

export function useResolveCheckpoint() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({ checkpointId, resolutionData }: { checkpointId: string; resolutionData: Record<string, any> }) => {
      const res = await apiClient.post(`/checkpoints/${checkpointId}/resolve`, {
        resolution_data: resolutionData,
      });
      return res.data;
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["application-execution"] });
      qc.invalidateQueries({ queryKey: queryKeys.applications });
    },
  });
}

export function useAutonomousUploadDocument() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({ file, applicationId }: { file: File; applicationId?: string }) => {
      const formData = new FormData();
      formData.append("file", file);
      if (applicationId) {
        formData.append("application_id", applicationId);
      }
      const res = await apiClient.post("/documents/autonomous-upload", formData, {
        headers: { "Content-Type": "multipart/form-data" },
      });
      return res.data;
    },
    onSuccess: (_, vars) => {
      qc.invalidateQueries({ queryKey: queryKeys.documents });
      qc.invalidateQueries({ queryKey: queryKeys.applications });
      if (vars.applicationId) {
        qc.invalidateQueries({ queryKey: ["application-execution", vars.applicationId] });
      }
    },
  });
}