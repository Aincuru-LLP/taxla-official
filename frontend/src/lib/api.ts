import { apiClient, setAccessToken } from "@/api/workflow";

export interface DashboardSummary {
  total_applications: number;
  pending_requirements: number;
  pending_payment: number;
  ready_for_automation: number;
  automation_running: number;
  waiting_for_otp: number;
  completed: number;
}

export interface NeedsAttentionItem {
  id: string;
  application_number: string;
  customer_name: string;
  customer_phone?: string;
  status: string;
  processing_mode: string;
  assigned_employee_name?: string;
  created_at: string;
  updated_at: string;
  action_required: string;
}

export interface ApplicationItem {
  id: string;
  application_number: string;
  business_name?: string;
  applicant_name?: string;
  mobile_number?: string;
  status: string;
  workflow_type?: string;
  assigned_employee_name?: string;
  created_at: string;
  updated_at: string;
  completion_percentage?: number;
}

export interface CustomerItem {
  id: string;
  business_name: string;
  applicant_name: string;
  mobile_number: string;
  email?: string;
  applications_count: number;
  active_applications_count: number;
  created_at: string;
  updated_at: string;
}

export interface CustomerDetail extends CustomerItem {
  pan_number?: string;
  social_category?: string;
  gender?: string;
  whatsapp_status: string;
  applications: Array<{
    id: string;
    application_number: string;
    service: string;
    status: string;
    processing_mode: string;
    created_at: string;
    updated_at: string;
  }>;
}

// ---------------- DASHBOARD ----------------
export async function fetchDashboardSummary(): Promise<DashboardSummary> {
  const res = await apiClient.get<DashboardSummary>("/dashboard/summary");
  return res.data;
}

export async function fetchNeedsAttention(limit = 15): Promise<NeedsAttentionItem[]> {
  const res = await apiClient.get<NeedsAttentionItem[]>(`/dashboard/needs-attention?limit=${limit}`);
  return res.data;
}

// ---------------- APPLICATIONS ----------------
export async function fetchApplications(params?: {
  search?: string;
  status?: string;
  skip?: number;
  limit?: number;
}): Promise<{ items: ApplicationItem[]; total: number }> {
  const query = new URLSearchParams();
  if (params?.search) query.set("search", params.search);
  if (params?.status) query.set("status", params.status);
  if (params?.skip !== undefined) query.set("skip", String(params.skip));
  if (params?.limit !== undefined) query.set("limit", String(params.limit));

  const res = await apiClient.get<any>(`/applications?${query.toString()}`);
  const data = res.data;
  if (Array.isArray(data)) {
    return { items: data, total: data.length };
  }
  return { items: data.items || [], total: data.total || 0 };
}

export async function fetchApplicationDetail(id: string): Promise<any> {
  const res = await apiClient.get(`/applications/${id}`);
  return res.data;
}

export async function createApplication(payload: {
  business_name: string;
  applicant_name: string;
  mobile_number: string;
  email?: string;
  pan_number: string;
  aadhaar_number: string;
}): Promise<any> {
  const res = await apiClient.post("/applications", payload);
  return res.data;
}

export async function patchApplication(id: string, payload: any): Promise<any> {
  const res = await apiClient.patch(`/applications/${id}`, payload);
  return res.data;
}

// ---------------- REQUIREMENTS ----------------
export async function fetchRequirements(id: string): Promise<any> {
  const res = await apiClient.get(`/applications/${id}/requirements`);
  return res.data;
}

export async function updateRequirements(id: string, payload: any): Promise<any> {
  const res = await apiClient.patch(`/applications/${id}/requirements`, payload);
  return res.data;
}

export async function requestMissingInfo(id: string, missingFields: string[], customMessage?: string): Promise<any> {
  const res = await apiClient.post(`/applications/${id}/request-info`, {
    missing_fields: missingFields,
    custom_message: customMessage,
  });
  return res.data;
}

// ---------------- PAYMENTS ----------------
export async function fetchPayments(id: string): Promise<any> {
  const res = await apiClient.get(`/applications/${id}/payments`);
  return res.data;
}

export async function markPaymentReceived(id: string, payload?: {
  amount?: number;
  currency?: string;
  payment_method?: string;
  reference?: string;
}): Promise<any> {
  const res = await apiClient.post(`/applications/${id}/payments`, {
    amount: payload?.amount ?? 1500.0,
    currency: payload?.currency ?? "INR",
    payment_method: payload?.payment_method ?? "UPI / Bank Transfer",
    reference: payload?.reference ?? "MANUAL-CONFIRMED",
  });
  return res.data;
}

// ---------------- AUTOMATION ----------------
export async function fetchAutomationStatus(id: string): Promise<any> {
  const res = await apiClient.get(`/applications/${id}/automation`);
  return res.data;
}

export async function startAutomation(id: string): Promise<any> {
  const res = await apiClient.post(`/applications/${id}/automation/start`);
  return res.data;
}

export async function submitOtp(id: string, otp: string): Promise<any> {
  const res = await apiClient.post(`/applications/${id}/automation/otp`, { otp });
  return res.data;
}

export async function continueAutomation(id: string): Promise<any> {
  const res = await apiClient.post(`/applications/${id}/automation/continue`);
  return res.data;
}

export async function cancelAutomation(id: string): Promise<any> {
  const res = await apiClient.post(`/applications/${id}/automation/cancel`);
  return res.data;
}

export async function processManually(id: string, payload: {
  udyam_registration_number: string;
  certificate_file_name?: string;
  notes?: string;
}): Promise<any> {
  const res = await apiClient.post(`/applications/${id}/manual-process`, payload);
  return res.data;
}

// ---------------- CERTIFICATES ----------------
export async function fetchCertificate(id: string): Promise<any> {
  const res = await apiClient.get(`/applications/${id}/certificate`);
  return res.data;
}

export async function sendCertificateWhatsApp(id: string): Promise<any> {
  const res = await apiClient.post(`/applications/${id}/certificate/send`);
  return res.data;
}

// ---------------- CUSTOMERS ----------------
export async function fetchCustomers(params?: {
  search?: string;
  skip?: number;
  limit?: number;
}): Promise<{ items: CustomerItem[]; total: number }> {
  const query = new URLSearchParams();
  if (params?.search) query.set("search", params.search);
  if (params?.skip !== undefined) query.set("skip", String(params.skip));
  if (params?.limit !== undefined) query.set("limit", String(params.limit));

  const res = await apiClient.get<any>(`/customers?${query.toString()}`);
  return res.data;
}

export async function fetchCustomerDetail(id: string): Promise<CustomerDetail> {
  const res = await apiClient.get<CustomerDetail>(`/customers/${id}`);
  return res.data;
}

export async function createCustomer(payload: {
  business_name: string;
  applicant_name: string;
  mobile_number: string;
  email?: string;
  pan_number?: string;
}): Promise<CustomerDetail> {
  const res = await apiClient.post<CustomerDetail>("/customers", payload);
  return res.data;
}

// ---------------- DOCUMENTS ----------------
export async function fetchApplicationDocuments(id: string): Promise<any[]> {
  const res = await apiClient.get(`/applications/${id}/documents`);
  return res.data;
}

export async function uploadApplicationDocument(id: string, file: File, docType: string): Promise<any> {
  const formData = new FormData();
  formData.append("file", file);
  formData.append("document_type", docType);
  const res = await apiClient.post(`/applications/${id}/documents`, formData, {
    headers: { "Content-Type": "multipart/form-data" },
  });
  return res.data;
}

export async function verifyDocument(docId: string, verified: boolean): Promise<any> {
  const res = await apiClient.post(`/documents/${docId}/verify`, { verified });
  return res.data;
}

// ---------------- WHATSAPP ----------------
export async function fetchConversations(limit = 25): Promise<any[]> {
  const res = await apiClient.get(`/whatsapp/conversations?limit=${limit}`);
  return res.data;
}

export async function fetchApplicationMessages(id: string): Promise<any[]> {
  const res = await apiClient.get(`/applications/${id}/messages`);
  return res.data;
}

export async function sendApplicationMessage(id: string, text: string): Promise<any> {
  const res = await apiClient.post(`/applications/${id}/message`, { message_text: text });
  return res.data;
}

// ---------------- ACTIVITY ----------------
export async function fetchApplicationActivity(id: string): Promise<any[]> {
  const res = await apiClient.get(`/applications/${id}/activity`);
  return res.data;
}

// ---------------- SETTINGS & USERS ----------------
export async function fetchSettings(): Promise<any> {
  const res = await apiClient.get("/settings");
  return res.data;
}

export async function fetchWhatsAppSettings(): Promise<any> {
  const res = await apiClient.get("/settings/whatsapp");
  return res.data;
}

export async function fetchUsers(): Promise<any[]> {
  const res = await apiClient.get("/users");
  return res.data;
}

export async function createUser(payload: any): Promise<any> {
  const res = await apiClient.post("/users", payload);
  return res.data;
}

export async function patchUser(userId: string, payload: any): Promise<any> {
  const res = await apiClient.patch(`/users/${userId}`, payload);
  return res.data;
}

// ---------------- CUSTOMER PUBLIC FORM ----------------
export async function fetchPublicForm(code: string, token: string): Promise<any> {
  const res = await apiClient.get(`/forms/${code}/${token}`);
  return res.data;
}

export async function savePublicFormDraft(code: string, token: string, data: any): Promise<any> {
  const res = await apiClient.patch(`/forms/${code}/${token}`, data);
  return res.data;
}

export async function submitPublicForm(code: string, token: string, data: any): Promise<any> {
  const res = await apiClient.post(`/forms/${code}/${token}/submit`, data);
  return res.data;
}
