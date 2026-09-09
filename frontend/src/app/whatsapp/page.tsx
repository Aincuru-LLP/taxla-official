"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import {
  MessageSquare,
  Search,
  Send,
  Building,
  User,
  ExternalLink,
  CheckCheck,
  Clock,
  Phone,
  ArrowUpRight,
  ShieldCheck,
} from "lucide-react";

import { fetchConversations, fetchApplicationMessages, sendApplicationMessage } from "@/lib/api";

export default function WhatsAppWorkspacePage() {
  const [conversations, setConversations] = useState<any[]>([]);
  const [selectedConv, setSelectedConv] = useState<any | null>(null);
  const [messages, setMessages] = useState<any[]>([]);
  const [loadingConv, setLoadingConv] = useState(true);
  const [loadingMsgs, setLoadingMsgs] = useState(false);
  const [search, setSearch] = useState("");
  const [inputText, setInputText] = useState("");
  const [sending, setSending] = useState(false);

  useEffect(() => {
    fetchConversations(30)
      .then((data) => {
        setConversations(data || []);
        if (data && data.length > 0) {
          setSelectedConv(data[0]);
        }
      })
      .catch((err) => console.error("Failed to load WhatsApp conversations:", err))
      .finally(() => setLoadingConv(false));
  }, []);

  useEffect(() => {
    if (!selectedConv?.application_id) {
      setMessages([]);
      return;
    }
    setLoadingMsgs(true);
    fetchApplicationMessages(selectedConv.application_id)
      .then((msgs) => setMessages(msgs || []))
      .catch((err) => console.error("Failed to load messages:", err))
      .finally(() => setLoadingMsgs(false));
  }, [selectedConv]);

  async function handleSend(e: React.FormEvent) {
    e.preventDefault();
    if (!inputText.trim() || !selectedConv?.application_id) return;
    const textToSend = inputText.trim();
    setInputText("");
    setSending(true);
    try {
      await sendApplicationMessage(selectedConv.application_id, textToSend);
      // Reload message thread
      const updated = await fetchApplicationMessages(selectedConv.application_id);
      setMessages(updated || []);
    } catch (err) {
      console.error("Failed to send message:", err);
    } finally {
      setSending(false);
    }
  }

  const filteredConv = conversations.filter((c) =>
    c.customer_name?.toLowerCase().includes(search.toLowerCase()) ||
    c.phone_number?.includes(search) ||
    c.application_number?.toLowerCase().includes(search.toLowerCase())
  );

  return (
    <div className="h-[calc(100vh-64px)] max-w-7xl mx-auto p-6 flex flex-col">
      {/* Page Title */}
      <div className="pb-4 mb-4 border-b border-slate-200 flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-slate-900 tracking-tight">
            WhatsApp Communication Workspace
          </h1>
          <p className="text-xs text-slate-500">
            Realtime two-way WhatsApp messaging linked to Customer profiles and Application IDs.
          </p>
        </div>

        <div className="flex items-center gap-1.5 px-3 py-1 bg-emerald-50 text-emerald-800 border border-emerald-200 rounded-full text-xs font-semibold">
          <ShieldCheck className="w-3.5 h-3.5 text-emerald-600" />
          <span>Cloud API Active</span>
        </div>
      </div>

      {/* 2-Pane Split Layout */}
      <div className="flex-1 bg-white border border-slate-200 rounded-xl shadow-xs overflow-hidden flex flex-col md:flex-row">
        {/* Left Pane: Conversation Threads */}
        <div className="w-full md:w-80 border-r border-slate-200 flex flex-col bg-slate-50/50">
          <div className="p-3 border-b border-slate-200">
            <div className="relative">
              <Search className="w-4 h-4 text-slate-400 absolute left-3 top-2.5" />
              <input
                type="text"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder="Search conversations…"
                className="w-full pl-9 pr-3 py-1.5 text-xs bg-white border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-600"
              />
            </div>
          </div>

          <div className="flex-1 overflow-y-auto divide-y divide-slate-100">
            {loadingConv ? (
              <div className="p-8 text-center text-xs text-slate-400">Loading threads…</div>
            ) : filteredConv.length === 0 ? (
              <div className="p-8 text-center text-xs text-slate-400">No conversations found</div>
            ) : (
              filteredConv.map((conv) => {
                const isSelected = selectedConv?.id === conv.id;

                return (
                  <button
                    key={conv.id}
                    onClick={() => setSelectedConv(conv)}
                    className={`w-full text-left p-3.5 transition-colors flex flex-col gap-1 ${
                      isSelected ? "bg-indigo-50/80 border-l-4 border-indigo-600" : "hover:bg-slate-100/60"
                    }`}
                  >
                    <div className="flex items-center justify-between">
                      <span className="text-xs font-bold text-slate-900 truncate max-w-[170px]">
                        {conv.customer_name}
                      </span>
                      <span className="text-[10px] text-slate-400">
                        {conv.last_message_at ? new Date(conv.last_message_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : ""}
                      </span>
                    </div>

                    <div className="text-[11px] text-slate-500 truncate">
                      {conv.last_message}
                    </div>

                    {conv.application_number && (
                      <div className="mt-1 flex items-center gap-1">
                        <span className="px-1.5 py-0.5 rounded text-[10px] font-bold bg-slate-200 text-slate-700">
                          {conv.application_number}
                        </span>
                      </div>
                    )}
                  </button>
                );
              })
            )}
          </div>
        </div>

        {/* Right Pane: Active Message Thread */}
        <div className="flex-1 flex flex-col bg-white">
          {selectedConv ? (
            <>
              {/* Thread Header */}
              <div className="p-4 border-b border-slate-200 flex items-center justify-between bg-slate-50/60">
                <div>
                  <div className="flex items-center gap-2">
                    <h2 className="text-sm font-bold text-slate-900">{selectedConv.customer_name}</h2>
                    <span className="text-xs text-slate-500 font-medium">({selectedConv.phone_number})</span>
                  </div>

                  {selectedConv.application_id && (
                    <div className="flex items-center gap-2 text-xs text-slate-500 mt-0.5">
                      <span>Linked Application:</span>
                      <Link
                        href={`/applications/${selectedConv.application_id}/overview`}
                        className="font-semibold text-indigo-600 hover:underline flex items-center gap-0.5"
                      >
                        <span>{selectedConv.application_number}</span>
                        <ArrowUpRight className="w-3 h-3" />
                      </Link>
                    </div>
                  )}
                </div>

                <div className="flex items-center gap-2">
                  <Link
                    href={`/customers/${selectedConv.customer_id}`}
                    className="px-2.5 py-1 bg-white border border-slate-200 hover:bg-slate-50 rounded-lg text-xs font-semibold text-slate-700 transition-colors shadow-2xs"
                  >
                    Customer Profile
                  </Link>
                </div>
              </div>

              {/* Message Feed */}
              <div className="flex-1 p-5 overflow-y-auto space-y-3 bg-slate-50/30">
                {loadingMsgs ? (
                  <div className="p-12 text-center text-xs text-slate-400">Loading conversation history…</div>
                ) : messages.length === 0 ? (
                  <div className="p-12 text-center text-xs text-slate-400">
                    No messages recorded for this application yet.
                  </div>
                ) : (
                  messages.map((m) => {
                    const isOutbound = m.direction === "OUTBOUND";

                    return (
                      <div
                        key={m.id}
                        className={`flex flex-col ${isOutbound ? "items-end" : "items-start"}`}
                      >
                        <div
                          className={`max-w-md rounded-2xl px-4 py-2.5 text-xs shadow-2xs ${
                            isOutbound
                              ? "bg-indigo-600 text-white rounded-br-xs"
                              : "bg-white border border-slate-200 text-slate-900 rounded-bl-xs"
                          }`}
                        >
                          <div className="leading-relaxed whitespace-pre-wrap">{m.text}</div>
                          <div
                            className={`flex items-center justify-end gap-1 mt-1 text-[10px] ${
                              isOutbound ? "text-indigo-200" : "text-slate-400"
                            }`}
                          >
                            <span>
                              {m.timestamp ? new Date(m.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : ""}
                            </span>
                            {isOutbound && <CheckCheck className="w-3 h-3 text-indigo-200" />}
                          </div>
                        </div>
                      </div>
                    );
                  })
                )}
              </div>

              {/* Message Composer */}
              <form onSubmit={handleSend} className="p-3 border-t border-slate-200 bg-white flex items-center gap-2">
                <input
                  type="text"
                  value={inputText}
                  onChange={(e) => setInputText(e.target.value)}
                  placeholder="Type an official WhatsApp reply…"
                  className="flex-1 px-3 py-2 text-xs border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-600 text-slate-900"
                />
                <button
                  type="submit"
                  disabled={sending || !inputText.trim()}
                  className="px-4 py-2 bg-indigo-600 hover:bg-indigo-700 disabled:opacity-50 text-white rounded-lg text-xs font-semibold shadow-xs flex items-center gap-1.5 transition-colors"
                >
                  <Send className="w-3.5 h-3.5" />
                  <span>{sending ? "Sending…" : "Send"}</span>
                </button>
              </form>
            </>
          ) : (
            <div className="flex-1 flex flex-col items-center justify-center p-8 text-slate-400 text-xs">
              <MessageSquare className="w-8 h-8 text-slate-300 mb-2" />
              <span>Select a conversation to view WhatsApp timeline.</span>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
