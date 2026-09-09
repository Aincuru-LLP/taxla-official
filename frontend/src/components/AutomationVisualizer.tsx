"use client";

import React, { useState } from "react";
import {
  useApplicationExecution,
  usePauseExecution,
  useResumeExecution,
  useCancelExecution,
  useResolveCheckpoint,
  NodeExecution,
  CheckpointItem,
} from "@/lib/api-client";
import {
  Play,
  Pause,
  RotateCw,
  XCircle,
  CheckCircle2,
  AlertTriangle,
  Clock,
  Cpu,
  FileText,
  ShieldAlert,
  Terminal,
  Camera,
  ExternalLink,
  ChevronRight,
  Sparkles,
  Layers,
  ArrowRight,
  KeyRound,
  Eye,
} from "lucide-react";

interface AutomationVisualizerProps {
  applicationId: string;
  applicationNumber?: string;
  businessName?: string;
}

export function AutomationVisualizer({
  applicationId,
  applicationNumber,
  businessName,
}: AutomationVisualizerProps) {
  const { data: execution, isLoading, isError, refetch } = useApplicationExecution(applicationId);
  const pauseMutation = usePauseExecution();
  const resumeMutation = useResumeExecution();
  const cancelMutation = useCancelExecution();
  const resolveMutation = useResolveCheckpoint();

  const [selectedNode, setSelectedNode] = useState<NodeExecution | null>(null);
  const [otpInput, setOtpInput] = useState("");
  const [reviewNotes, setReviewNotes] = useState("");
  const [showScreenshotModal, setShowScreenshotModal] = useState(false);

  if (isLoading) {
    return (
      <div className="flex flex-col items-center justify-center p-16 space-y-4">
        <div className="w-12 h-12 border-4 border-indigo-500 border-t-transparent rounded-full animate-spin" />
        <p className="text-sm font-medium text-slate-400">Loading live automation execution graph...</p>
      </div>
    );
  }

  if (isError || !execution) {
    return (
      <div className="bg-slate-900 border border-slate-800 rounded-xl p-8 text-center space-y-4">
        <AlertTriangle className="w-10 h-10 text-amber-400 mx-auto" />
        <h3 className="text-lg font-semibold text-white">Execution Graph Unavailable</h3>
        <p className="text-sm text-slate-400 max-w-md mx-auto">
          No active automation execution found for this case. Upload a requirement document to start autonomous processing.
        </p>
        <button
          onClick={() => refetch()}
          className="inline-flex items-center px-4 py-2 bg-indigo-600 hover:bg-indigo-500 text-white rounded-lg text-sm font-medium transition"
        >
          <RotateCw className="w-4 h-4 mr-2" /> Retry Connection
        </button>
      </div>
    );
  }

  const activeCheckpoint = execution.checkpoints?.find((c) => c.status === "PENDING");

  const getNodeStatus = (node: NodeExecution) => {
    return node.status;
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case "SUCCESS":
        return "bg-emerald-500/10 border-emerald-500/30 text-emerald-400";
      case "RUNNING":
        return "bg-blue-500/10 border-blue-500/40 text-blue-400 ring-2 ring-blue-500/20 animate-pulse";
      case "HUMAN_REQUIRED":
        return "bg-purple-500/20 border-purple-500/50 text-purple-300 ring-2 ring-purple-500/30";
      case "FAILED":
        return "bg-rose-500/10 border-rose-500/30 text-rose-400";
      case "PAUSED":
        return "bg-amber-500/10 border-amber-500/30 text-amber-400";
      case "SKIPPED":
        return "bg-slate-800/40 border-slate-700/40 text-slate-500";
      default:
        return "bg-slate-900/60 border-slate-800 text-slate-400";
    }
  };

  const getStatusBadge = (status: string) => {
    switch (status) {
      case "SUCCESS":
        return (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-semibold bg-emerald-500/20 text-emerald-300">
            <CheckCircle2 className="w-3 h-3" /> Done
          </span>
        );
      case "RUNNING":
        return (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-semibold bg-blue-500/20 text-blue-300 animate-pulse">
            <RotateCw className="w-3 h-3 animate-spin" /> Running
          </span>
        );
      case "HUMAN_REQUIRED":
        return (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-semibold bg-purple-500/20 text-purple-300">
            <KeyRound className="w-3 h-3" /> Checkpoint
          </span>
        );
      case "FAILED":
        return (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-semibold bg-rose-500/20 text-rose-300">
            <XCircle className="w-3 h-3" /> Failed
          </span>
        );
      case "PAUSED":
        return (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-semibold bg-amber-500/20 text-amber-300">
            <Pause className="w-3 h-3" /> Paused
          </span>
        );
      case "SKIPPED":
        return (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-semibold bg-slate-800 text-slate-400">
            Skipped
          </span>
        );
      default:
        return (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-semibold bg-slate-800 text-slate-400">
            <Clock className="w-3 h-3" /> Waiting
          </span>
        );
    }
  };

  const handleResolveCheckpoint = (resolutionData: Record<string, any>) => {
    if (!activeCheckpoint) return;
    resolveMutation.mutate(
      {
        checkpointId: activeCheckpoint.id,
        resolutionData,
      },
      {
        onSuccess: () => {
          setOtpInput("");
          setReviewNotes("");
          refetch();
        },
      }
    );
  };

  // Group nodes into 3 pipeline stages
  const stage1Nodes = execution.nodes.filter((n) =>
    ["doc_received", "classification", "parsing", "ocr", "ai_extraction"].includes(n.node_id)
  );
  const stage2Nodes = execution.nodes.filter((n) =>
    ["req_matching", "validation", "nic", "human_review", "udyam_prep"].includes(n.node_id)
  );
  const stage3Nodes = execution.nodes.filter((n) =>
    ["portal_automation", "human_checkpoint", "final_review", "submission", "certificate", "completed"].includes(n.node_id)
  );

  return (
    <div className="space-y-6">
      {/* Control & Status Bar */}
      <div className="bg-slate-900 border border-slate-800 rounded-xl p-5 shadow-xl flex flex-wrap items-center justify-between gap-4">
        <div className="flex items-center gap-4">
          <div className="p-3 bg-indigo-600/10 border border-indigo-500/20 rounded-xl">
            <Cpu className="w-6 h-6 text-indigo-400" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h2 className="text-lg font-bold text-white tracking-wide">
                Autonomous Execution Visualizer
              </h2>
              <span
                className={`px-2.5 py-0.5 rounded-full text-xs font-bold uppercase tracking-wider ${
                  execution.status === "RUNNING"
                    ? "bg-blue-500/20 text-blue-400 border border-blue-500/30 animate-pulse"
                    : execution.status === "COMPLETED"
                    ? "bg-emerald-500/20 text-emerald-400 border border-emerald-500/30"
                    : execution.status === "HUMAN_REQUIRED"
                    ? "bg-purple-500/20 text-purple-300 border border-purple-500/40"
                    : "bg-slate-800 text-slate-300"
                }`}
              >
                {execution.status}
              </span>
            </div>
            <p className="text-xs text-slate-400 mt-0.5">
              Case: <span className="text-slate-200 font-semibold">{applicationNumber || applicationId.slice(0, 8)}</span> •{" "}
              {businessName || "MSME Enterprise"} • Version: {execution.workflow_version}
            </p>
          </div>
        </div>

        {/* Execution Actions */}
        <div className="flex items-center gap-2">
          {execution.status === "PAUSED" && (
            <button
              onClick={() => resumeMutation.mutate({ executionId: execution.execution_id })}
              disabled={resumeMutation.isPending}
              className="inline-flex items-center px-3.5 py-2 bg-emerald-600 hover:bg-emerald-500 text-white rounded-lg text-xs font-semibold transition shadow-lg shadow-emerald-900/20"
            >
              <Play className="w-3.5 h-3.5 mr-1.5" /> Resume
            </button>
          )}
          {execution.status === "RUNNING" && (
            <button
              onClick={() => pauseMutation.mutate({ executionId: execution.execution_id })}
              disabled={pauseMutation.isPending}
              className="inline-flex items-center px-3.5 py-2 bg-amber-600 hover:bg-amber-500 text-white rounded-lg text-xs font-semibold transition shadow-lg shadow-amber-900/20"
            >
              <Pause className="w-3.5 h-3.5 mr-1.5" /> Pause
            </button>
          )}
          {["RUNNING", "PAUSED", "HUMAN_REQUIRED"].includes(execution.status) && (
            <button
              onClick={() => cancelMutation.mutate({ executionId: execution.execution_id })}
              disabled={cancelMutation.isPending}
              className="inline-flex items-center px-3.5 py-2 bg-slate-800 hover:bg-rose-900/40 text-slate-300 hover:text-rose-300 border border-slate-700 hover:border-rose-700/50 rounded-lg text-xs font-semibold transition"
            >
              <XCircle className="w-3.5 h-3.5 mr-1.5" /> Abort
            </button>
          )}
          <button
            onClick={() => refetch()}
            className="p-2 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded-lg text-xs font-medium transition border border-slate-700"
            title="Refresh Graph State"
          >
            <RotateCw className="w-4 h-4" />
          </button>
        </div>
      </div>

      {/* Human Checkpoint Urgent Banner */}
      {activeCheckpoint && (
        <div className="bg-gradient-to-r from-purple-950/80 via-indigo-950/60 to-purple-950/80 border-2 border-purple-500/50 rounded-xl p-6 shadow-2xl shadow-purple-950/50 animate-fade-in space-y-4">
          <div className="flex items-start justify-between gap-4">
            <div className="flex items-center gap-3">
              <div className="p-3 bg-purple-500/20 border border-purple-400/30 rounded-xl animate-bounce">
                <KeyRound className="w-6 h-6 text-purple-300" />
              </div>
              <div>
                <span className="text-xs uppercase font-bold tracking-widest text-purple-400">
                  Human Checkpoint Triggered
                </span>
                <h3 className="text-lg font-bold text-white">{activeCheckpoint.title}</h3>
              </div>
            </div>
            <span className="px-3 py-1 bg-purple-500/20 text-purple-300 text-xs font-semibold rounded-full border border-purple-500/30">
              Awaiting Operator Action
            </span>
          </div>

          <p className="text-sm text-purple-200/90 leading-relaxed">
            {activeCheckpoint.prompt_message}
          </p>

          {activeCheckpoint.checkpoint_type === "OTP" && (
            <div className="flex flex-wrap items-center gap-3 pt-2">
              <input
                type="text"
                maxLength={6}
                value={otpInput}
                onChange={(e) => setOtpInput(e.target.value.replace(/\D/g, ""))}
                placeholder="Enter 6-digit OTP"
                className="px-4 py-2.5 bg-slate-900/90 border-2 border-purple-500/40 focus:border-purple-400 text-white rounded-lg text-base tracking-widest font-mono text-center w-48 outline-none shadow-inner"
              />
              <button
                onClick={() => handleResolveCheckpoint({ otp_code: otpInput })}
                disabled={otpInput.length < 6 || resolveMutation.isPending}
                className="px-5 py-2.5 bg-purple-600 hover:bg-purple-500 disabled:opacity-50 disabled:cursor-not-allowed text-white font-bold rounded-lg text-sm transition shadow-lg shadow-purple-900/40"
              >
                {resolveMutation.isPending ? "Verifying..." : "Submit OTP & Continue"}
              </button>
            </div>
          )}

          {activeCheckpoint.checkpoint_type !== "OTP" && (
            <div className="space-y-3 pt-2">
              <input
                type="text"
                value={reviewNotes}
                onChange={(e) => setReviewNotes(e.target.value)}
                placeholder="Review notes / approval remarks (optional)"
                className="w-full px-4 py-2.5 bg-slate-900/90 border border-purple-500/30 focus:border-purple-400 text-white rounded-lg text-sm outline-none"
              />
              <button
                onClick={() => handleResolveCheckpoint({ approved: true, remarks: reviewNotes })}
                disabled={resolveMutation.isPending}
                className="px-5 py-2.5 bg-purple-600 hover:bg-purple-500 text-white font-bold rounded-lg text-sm transition shadow-lg shadow-purple-900/40"
              >
                {resolveMutation.isPending ? "Submitting..." : "Approve & Resume Pipeline"}
              </button>
            </div>
          )}
        </div>
      )}

      {/* 3-Column Execution Graph Canvas */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Stage 1: Intelligence & Ingestion */}
        <div className="bg-slate-900/70 border border-slate-800 rounded-xl p-5 space-y-4">
          <div className="flex items-center justify-between border-b border-slate-800 pb-3">
            <div className="flex items-center gap-2">
              <FileText className="w-4 h-4 text-indigo-400" />
              <h3 className="text-xs font-bold uppercase tracking-wider text-slate-300">
                1. Intelligence & Ingestion
              </h3>
            </div>
            <span className="text-xs text-slate-500 font-mono">5 nodes</span>
          </div>

          <div className="space-y-3">
            {stage1Nodes.map((node) => (
              <div
                key={node.node_id}
                onClick={() => setSelectedNode(node)}
                className={`p-3.5 rounded-lg border transition cursor-pointer hover:scale-[1.01] ${getStatusColor(
                  node.status
                )}`}
              >
                <div className="flex items-center justify-between">
                  <span className="text-sm font-bold">{node.node_label}</span>
                  {getStatusBadge(node.status)}
                </div>
                <div className="flex items-center justify-between text-xs text-slate-400 mt-2">
                  <span className="font-mono">{node.node_type}</span>
                  {node.duration_seconds ? (
                    <span className="font-mono">{node.duration_seconds}s</span>
                  ) : null}
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Stage 2: Validation & Business Rules */}
        <div className="bg-slate-900/70 border border-slate-800 rounded-xl p-5 space-y-4">
          <div className="flex items-center justify-between border-b border-slate-800 pb-3">
            <div className="flex items-center gap-2">
              <Sparkles className="w-4 h-4 text-violet-400" />
              <h3 className="text-xs font-bold uppercase tracking-wider text-slate-300">
                2. Validation & Business Rules
              </h3>
            </div>
            <span className="text-xs text-slate-500 font-mono">5 nodes</span>
          </div>

          <div className="space-y-3">
            {stage2Nodes.map((node) => (
              <div
                key={node.node_id}
                onClick={() => setSelectedNode(node)}
                className={`p-3.5 rounded-lg border transition cursor-pointer hover:scale-[1.01] ${getStatusColor(
                  node.status
                )}`}
              >
                <div className="flex items-center justify-between">
                  <span className="text-sm font-bold">{node.node_label}</span>
                  {getStatusBadge(node.status)}
                </div>
                <div className="flex items-center justify-between text-xs text-slate-400 mt-2">
                  <span className="font-mono">{node.node_type}</span>
                  {node.duration_seconds ? (
                    <span className="font-mono">{node.duration_seconds}s</span>
                  ) : null}
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Stage 3: Portal Automation & Issue */}
        <div className="bg-slate-900/70 border border-slate-800 rounded-xl p-5 space-y-4">
          <div className="flex items-center justify-between border-b border-slate-800 pb-3">
            <div className="flex items-center gap-2">
              <Layers className="w-4 h-4 text-emerald-400" />
              <h3 className="text-xs font-bold uppercase tracking-wider text-slate-300">
                3. Portal Automation & Issue
              </h3>
            </div>
            <span className="text-xs text-slate-500 font-mono">6 nodes</span>
          </div>

          <div className="space-y-3">
            {stage3Nodes.map((node) => (
              <div
                key={node.node_id}
                onClick={() => setSelectedNode(node)}
                className={`p-3.5 rounded-lg border transition cursor-pointer hover:scale-[1.01] ${getStatusColor(
                  node.status
                )}`}
              >
                <div className="flex items-center justify-between">
                  <span className="text-sm font-bold">{node.node_label}</span>
                  {getStatusBadge(node.status)}
                </div>
                <div className="flex items-center justify-between text-xs text-slate-400 mt-2">
                  <span className="font-mono">{node.node_type}</span>
                  {node.duration_seconds ? (
                    <span className="font-mono">{node.duration_seconds}s</span>
                  ) : null}
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Live Playwright Browser Preview Box */}
      {execution.live_screenshot_url && (
        <div className="bg-slate-900 border border-slate-800 rounded-xl p-5 space-y-3 shadow-xl">
          <div className="flex items-center justify-between border-b border-slate-800 pb-3">
            <div className="flex items-center gap-2">
              <Camera className="w-4 h-4 text-blue-400" />
              <h4 className="text-sm font-bold text-white">Live Portal Browser View</h4>
              <span className="px-2 py-0.5 bg-blue-500/20 text-blue-300 text-xs font-semibold rounded-full animate-pulse">
                Active Telemetry
              </span>
            </div>
            <button
              onClick={() => setShowScreenshotModal(true)}
              className="text-xs text-indigo-400 hover:text-indigo-300 font-medium inline-flex items-center gap-1"
            >
              <Eye className="w-3.5 h-3.5" /> Enlarge View
            </button>
          </div>
          <div className="relative rounded-lg overflow-hidden border border-slate-800 bg-slate-950 max-h-80 flex items-center justify-center">
            <img
              src={execution.live_screenshot_url}
              alt="Live Portal Stream"
              className="w-full object-cover max-h-80"
            />
          </div>
        </div>
      )}

      {/* Slide-out Node Detail Drawer */}
      {selectedNode && (
        <div className="fixed inset-0 z-50 bg-black/60 backdrop-blur-sm flex justify-end">
          <div className="w-full max-w-xl bg-slate-900 border-l border-slate-800 h-full p-6 overflow-y-auto space-y-6 shadow-2xl animate-in slide-in-from-right">
            <div className="flex items-start justify-between border-b border-slate-800 pb-4">
              <div>
                <span className="text-xs uppercase font-bold text-indigo-400 tracking-wider font-mono">
                  {selectedNode.node_type} NODE
                </span>
                <h3 className="text-xl font-bold text-white mt-0.5">{selectedNode.node_label}</h3>
                <p className="text-xs text-slate-400 font-mono mt-1">ID: {selectedNode.node_id}</p>
              </div>
              <button
                onClick={() => setSelectedNode(null)}
                className="p-1.5 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded-lg transition"
              >
                <XCircle className="w-5 h-5" />
              </button>
            </div>

            {/* Metrics */}
            <div className="grid grid-cols-2 gap-3">
              <div className="bg-slate-950 p-3.5 rounded-lg border border-slate-800/80">
                <span className="text-xs text-slate-400">Status</span>
                <div className="mt-1">{getStatusBadge(selectedNode.status)}</div>
              </div>
              <div className="bg-slate-950 p-3.5 rounded-lg border border-slate-800/80">
                <span className="text-xs text-slate-400">Duration</span>
                <p className="text-sm font-bold text-white font-mono mt-1">
                  {selectedNode.duration_seconds ? `${selectedNode.duration_seconds}s` : "In Progress"}
                </p>
              </div>
              <div className="bg-slate-950 p-3.5 rounded-lg border border-slate-800/80">
                <span className="text-xs text-slate-400">Worker</span>
                <p className="text-sm font-medium text-slate-200 font-mono mt-1">
                  {selectedNode.worker_id || "System"}
                </p>
              </div>
              <div className="bg-slate-950 p-3.5 rounded-lg border border-slate-800/80">
                <span className="text-xs text-slate-400">Attempt</span>
                <p className="text-sm font-bold text-white font-mono mt-1">
                  {selectedNode.attempt} / {selectedNode.max_attempts}
                </p>
              </div>
            </div>

            {/* Error message */}
            {selectedNode.error_message && (
              <div className="bg-rose-950/40 border border-rose-800/50 p-4 rounded-lg space-y-1">
                <span className="text-xs font-bold uppercase text-rose-400">Error Diagnostics</span>
                <p className="text-sm text-rose-200">{selectedNode.error_message}</p>
              </div>
            )}

            {/* Outputs */}
            {selectedNode.output_summary && (
              <div className="space-y-2">
                <span className="text-xs font-bold uppercase tracking-wider text-slate-400">
                  Node Output Summary
                </span>
                <pre className="bg-slate-950 border border-slate-800 p-3.5 rounded-lg text-xs font-mono text-emerald-400 overflow-x-auto">
                  {JSON.stringify(selectedNode.output_summary, null, 2)}
                </pre>
              </div>
            )}

            {/* Logs */}
            <div className="space-y-2">
              <div className="flex items-center gap-2 text-xs font-bold uppercase tracking-wider text-slate-400">
                <Terminal className="w-3.5 h-3.5" />
                <span>Execution Logs</span>
              </div>
              <pre className="bg-slate-950 border border-slate-800 p-3.5 rounded-lg text-xs font-mono text-slate-300 whitespace-pre-wrap leading-relaxed max-h-60 overflow-y-auto">
                {selectedNode.logs_text || "No detailed logs recorded."}
              </pre>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
