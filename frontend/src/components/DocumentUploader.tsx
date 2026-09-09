'use client';
import React, { useState, useRef } from 'react';
import {
  UploadCloud,
  FileText,
  CheckCircle2,
  AlertCircle,
  Eye,
  RefreshCw,
  Sparkles,
  Layers,
  ArrowRight,
} from 'lucide-react';
import { useApplicationDocuments, useUploadDocument } from '@/lib/api-client';
import { DocumentViewerModal } from './DocumentViewerModal';

interface DocumentUploaderProps {
  applicationId: string;
}

const DOC_TYPES = [
  { id: 'PAN_CARD', name: 'PAN Card', desc: 'Proprietor or Company PAN' },
  { id: 'AADHAAR_CARD', name: 'Aadhaar Card', desc: 'Applicant UIDAI Aadhaar' },
  { id: 'BANK_PROOF', name: 'Bank Statement / Cheque', desc: 'Account & IFSC proof' },
  { id: 'GENERAL_DOCUMENT', name: 'Other Supporting Document', desc: 'Incorporation deed, electricity bill, etc.' },
];

export const DocumentUploader: React.FC<DocumentUploaderProps> = ({ applicationId }) => {
  const { data: documents, isLoading, refetch } = useApplicationDocuments(applicationId);
  const uploadMutation = useUploadDocument();

  const [selectedType, setSelectedType] = useState('PAN_CARD');
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [isDragging, setIsDragging] = useState(false);
  const [activePreviewDoc, setActivePreviewDoc] = useState<any>(null);
  const [uploadStatus, setUploadStatus] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleFileDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      setSelectedFile(e.dataTransfer.files[0]);
    }
  };

  const handleUpload = async () => {
    if (!selectedFile) return;
    setUploadStatus('Uploading document and queueing OCR pipeline...');

    try {
      await uploadMutation.mutateAsync({
        applicationId,
        file: selectedFile,
        documentType: selectedType,
      });

      setSelectedFile(null);
      setUploadStatus('Document uploaded! OCR & Ollama extraction started.');
      await refetch();
      setTimeout(() => setUploadStatus(null), 4000);
    } catch (err: any) {
      setUploadStatus('Upload failed: ' + (err?.response?.data?.detail || err.message));
    }
  };

  return (
    <div className="space-y-6">
      {/* Upload Zone & Form */}
      <div className="glass-panel p-6 rounded-2xl border border-slate-800 bg-slate-950/80 shadow-xl space-y-4">
        <div className="flex items-center justify-between">
          <div>
            <h3 className="text-sm font-bold text-white flex items-center gap-2">
              <span>Intelligent Document Ingestion</span>
              <span className="text-xs px-2 py-0.5 rounded-full bg-indigo-500/10 text-indigo-400 border border-indigo-500/20">
                Tesseract + Ollama Qwen
              </span>
            </h3>
            <p className="text-[11px] text-slate-400">
              Upload scanned images or PDFs for instant OCR and automatic requirement satisfaction
            </p>
          </div>

          <button
            onClick={() => refetch()}
            className="p-2 rounded-lg bg-slate-900 hover:bg-slate-800 text-slate-300 transition-colors text-xs flex items-center gap-1.5"
          >
            <RefreshCw className="w-3.5 h-3.5" />
            <span>Refresh</span>
          </button>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {/* Document Type Selector */}
          <div>
            <label className="block text-xs font-semibold text-slate-300 uppercase tracking-wider mb-2">
              1. Document Type
            </label>
            <div className="space-y-2">
              {DOC_TYPES.map((dt) => (
                <div
                  key={dt.id}
                  onClick={() => setSelectedType(dt.id)}
                  className={`p-2.5 rounded-xl border cursor-pointer transition-all flex items-center justify-between ${
                    selectedType === dt.id
                      ? 'bg-indigo-600/15 border-indigo-500 text-white'
                      : 'bg-slate-900/50 border-slate-800 text-slate-300 hover:border-slate-700'
                  }`}
                >
                  <div>
                    <div className="text-xs font-bold">{dt.name}</div>
                    <div className="text-[10px] text-slate-400">{dt.desc}</div>
                  </div>
                  <div className={`w-3.5 h-3.5 rounded-full border flex items-center justify-center ${
                    selectedType === dt.id ? 'border-indigo-400 bg-indigo-500' : 'border-slate-700'
                  }`}>
                    {selectedType === dt.id && <div className="w-1 h-1 rounded-full bg-white" />}
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Drag & Drop Area */}
          <div className="md:col-span-2 flex flex-col">
            <label className="block text-xs font-semibold text-slate-300 uppercase tracking-wider mb-2">
              2. Select or Drop File
            </label>
            <div
              onDragOver={(e) => {
                e.preventDefault();
                setIsDragging(true);
              }}
              onDragLeave={() => setIsDragging(false)}
              onDrop={handleFileDrop}
              onClick={() => fileInputRef.current?.click()}
              className={`flex-1 border-2 border-dashed rounded-2xl p-6 flex flex-col items-center justify-center cursor-pointer transition-all ${
                isDragging
                  ? 'border-indigo-500 bg-indigo-500/10'
                  : 'border-slate-800 bg-slate-900/30 hover:border-slate-700 hover:bg-slate-900/50'
              }`}
            >
              <input
                ref={fileInputRef}
                type="file"
                accept=".pdf,.png,.jpg,.jpeg,.webp"
                className="hidden"
                onChange={(e) => {
                  if (e.target.files && e.target.files[0]) {
                    setSelectedFile(e.target.files[0]);
                  }
                }}
              />

              <UploadCloud className={`w-10 h-10 mb-2 ${isDragging ? 'text-indigo-400' : 'text-slate-500'}`} />
              <div className="text-xs font-bold text-white">
                {selectedFile ? selectedFile.name : 'Click to browse or drag and drop document'}
              </div>
              <p className="text-[11px] text-slate-400 mt-1">
                Supports PDF, PNG, JPG up to 25MB
              </p>

              {selectedFile && (
                <div className="mt-3 flex items-center gap-2">
                  <button
                    type="button"
                    onClick={(e) => {
                      e.stopPropagation();
                      handleUpload();
                    }}
                    disabled={uploadMutation.isPending}
                    className="gradient-button px-4 py-2 rounded-xl text-white text-xs font-semibold flex items-center gap-1.5 shadow-lg shadow-indigo-500/20"
                  >
                    {uploadMutation.isPending ? <RefreshCw className="w-3.5 h-3.5 animate-spin" /> : <Sparkles className="w-3.5 h-3.5" />}
                    <span>Upload & Process with AI</span>
                  </button>
                </div>
              )}
            </div>

            {uploadStatus && (
              <div className="mt-2 text-xs text-indigo-300 bg-indigo-950/40 p-2.5 rounded-xl border border-indigo-500/30 flex items-center gap-2">
                <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
                <span>{uploadStatus}</span>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Uploaded Documents List */}
      <div className="glass-panel p-6 rounded-2xl border border-slate-800 bg-slate-950/80 shadow-xl space-y-4">
        <h3 className="text-sm font-bold text-white flex items-center justify-between">
          <span>Uploaded Documents ({documents?.length || 0})</span>
        </h3>

        {isLoading ? (
          <div className="text-center py-8 text-xs text-slate-500">Loading documents...</div>
        ) : documents && documents.length > 0 ? (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
            {documents.map((doc: any) => (
              <div
                key={doc.id}
                className="p-4 rounded-xl bg-slate-900/60 border border-slate-800 hover:border-slate-700 transition-all flex flex-col justify-between space-y-3"
              >
                <div className="flex items-start justify-between">
                  <div className="flex items-center space-x-2.5">
                    <div className="w-9 h-9 rounded-lg bg-indigo-500/10 border border-indigo-500/20 flex items-center justify-center text-indigo-400">
                      <FileText className="w-5 h-5" />
                    </div>
                    <div>
                      <div className="text-xs font-bold text-white line-clamp-1">{doc.file_name}</div>
                      <div className="text-[10px] text-slate-400">{doc.type}</div>
                    </div>
                  </div>

                  <span className={`text-[10px] px-2 py-0.5 rounded-full font-bold ${
                    doc.ocr_status === 'COMPLETED'
                      ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20'
                      : 'bg-amber-500/10 text-amber-400 border border-amber-500/20'
                  }`}>
                    {doc.ocr_status}
                  </span>
                </div>

                <div className="pt-2 border-t border-slate-800/80 flex items-center justify-between">
                  <span className="text-[11px] text-slate-400">
                    {(doc.size_bytes / 1024).toFixed(1)} KB
                  </span>

                  <button
                    onClick={() => setActivePreviewDoc(doc)}
                    className="px-2.5 py-1 rounded-lg bg-slate-800 hover:bg-slate-700 text-xs text-indigo-300 font-semibold flex items-center gap-1 transition-colors"
                  >
                    <Eye className="w-3.5 h-3.5" />
                    <span>View & Provenance</span>
                  </button>
                </div>
              </div>
            ))}
          </div>
        ) : (
          <div className="text-center py-10 text-xs text-slate-500 border border-dashed border-slate-800 rounded-xl">
            No documents uploaded yet. Upload Aadhaar, PAN, or Bank Statement above.
          </div>
        )}
      </div>

      {/* Document Viewer Modal */}
      {activePreviewDoc && (
        <DocumentViewerModal
          isOpen={Boolean(activePreviewDoc)}
          onClose={() => setActivePreviewDoc(null)}
          document={activePreviewDoc}
        />
      )}
    </div>
  );
};
