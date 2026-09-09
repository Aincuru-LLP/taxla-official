# 49 — Automation Visualizer Specification

## 1. Visual Architecture

The visualizer reflects backend authoritative execution truth (`workflow_executions`, `workflow_node_executions`, `human_checkpoints`) and is rendered at:
`/applications/:applicationId/automation`

## 2. 16 Canonical Execution Nodes

```
[doc_received] -> [classification] -> [parsing] -> [ocr] -> [ai_extraction]
                                                                  |
[udyam_prep]   <- [human_review]   <- [nic]     <- [validation] <- [req_matching]
      |
[portal_automation] -> [human_checkpoint] -> [final_review] -> [submission] -> [certificate] -> [completed]
```

## 3. Node State Badge Specifications

- **`WAITING`**: Slate outline (`border-slate-700 text-slate-500 bg-slate-900/40`)
- **`QUEUED`**: Indigo glow with small clock (`border-indigo-500/40 text-indigo-400 bg-indigo-950/40`)
- **`RUNNING`**: Blue glowing border with animated ping radar badge (`border-blue-500 text-blue-300 bg-blue-950/60 ring-2 ring-blue-500/30`)
- **`SUCCESS`**: Emerald solid with checkmark icon (`border-emerald-500/60 text-emerald-300 bg-emerald-950/40`)
- **`FAILED`**: Rose outline with alert icon (`border-rose-500 text-rose-300 bg-rose-950/50 ring-2 ring-rose-500/20`)
- **`PAUSED`**: Amber outline with pause bars (`border-amber-500/50 text-amber-300 bg-amber-950/40`)
- **`HUMAN_REQUIRED`**: High-priority amber pulse badge with hand/shield icon (`border-amber-400 text-amber-200 bg-amber-950/80 animate-pulse ring-4 ring-amber-500/40`)
- **`SKIPPED`**: Muted slate (`border-slate-800 text-slate-600 bg-slate-950/30`)
- **`CANCELLED`**: Muted red (`border-red-800 text-red-400 bg-red-950/20`)

## 4. Interactive Components
- **Slide-out Node Drawer**: Displays Node ID, Label, Duration, Worker ID, Input/Output Summary JSON, and Logs text.
- **Human Checkpoint Banner**: Interactive OTP input / Review action banner that resolves challenges via `POST /api/v1/checkpoints/{id}/resolve`.
- **Live Screenshot Preview**: Auto-refreshing portal screen capture stream.
