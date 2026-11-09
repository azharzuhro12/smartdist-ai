"use client";

import React, { useState, useRef, useEffect } from "react";
import {
  Bot,
  User,
  Send,
  Sparkles,
  BookOpen,
  Database,
  LineChart,
  Boxes,
  AlertTriangle,
  FileText,
  RotateCcw,
} from "lucide-react";
import { api, ChatResult } from "@/lib/api";

interface Message {
  id: string;
  sender: "user" | "assistant";
  text: string;
  intent?: string;
  toolUsed?: string;
  provenance?: string;
  citations?: string[];
  data?: any;
  timestamp: string;
}

const SUGGESTED_PROMPTS = [
  "What is our policy on safety stock and reorder point?",
  "Forecast demand for product 13 branch 44 for next 7 days",
  "What are the top 5 selling products by volume?",
  "Evaluate inventory replenishment for product 13 branch 44",
  "Show me recent critical sales anomalies",
  "What are the purchase order approval thresholds?",
];

export default function AssistantPage() {
  const [messages, setMessages] = useState<Message[]>([
    {
      id: "initial",
      sender: "assistant",
      text: "Hello! I am your SmartDist AI Business Assistant. I can help you query sales analytics with Safe SQL, generate demand forecasts with LightGBM, optimize inventory replenishment with mathematical safety stock models, and look up company SOPs and procurement policies. How can I assist you today?",
      intent: "SYSTEM",
      toolUsed: "assistant_orchestrator",
      provenance: "ENTERPRISE_SYSTEM",
      timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
    },
  ]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, loading]);

  const handleSend = async (queryText?: string) => {
    const textToSend = queryText || input;
    if (!textToSend.trim() || loading) return;

    const userMsg: Message = {
      id: `user_${Date.now()}`,
      sender: "user",
      text: textToSend,
      timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
    };

    setMessages((prev) => [...prev, userMsg]);
    if (!queryText) setInput("");
    setLoading(true);

    try {
      const res: ChatResult = await api.chatAssistant(textToSend);
      const assistantMsg: Message = {
        id: `assistant_${Date.now()}`,
        sender: "assistant",
        text: res.answer,
        intent: res.intent,
        toolUsed: res.tool_used,
        provenance: res.provenance,
        citations: res.citations,
        data: res.data,
        timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
      };
      setMessages((prev) => [...prev, assistantMsg]);
    } catch (err: any) {
      const errorMsg: Message = {
        id: `assistant_err_${Date.now()}`,
        sender: "assistant",
        text: `Error processing request: ${err.message || "Failed to contact AI assistant."}`,
        intent: "ERROR",
        provenance: "ERROR",
        timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
      };
      setMessages((prev) => [...prev, errorMsg]);
    } finally {
      setLoading(false);
    }
  };

  const handleWorkflowClick = async (workflowName: string, params: Record<string, any> = {}) => {
    setLoading(true);
    const userMsg: Message = {
      id: `user_${Date.now()}`,
      sender: "user",
      text: `Run workflow: ${workflowName}`,
      timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
    };
    setMessages((prev) => [...prev, userMsg]);

    try {
      const res = await api.executeWorkflow(workflowName, params);
      const assistantMsg: Message = {
        id: `assistant_${Date.now()}`,
        sender: "assistant",
        text: res.report,
        intent: "WORKFLOW",
        toolUsed: `workflow_${workflowName}`,
        provenance: res.provenance,
        citations: res.citations || [],
        data: res.data || res.sections,
        timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
      };
      setMessages((prev) => [...prev, assistantMsg]);
    } catch (err: any) {
      const errorMsg: Message = {
        id: `assistant_wf_err_${Date.now()}`,
        sender: "assistant",
        text: `Workflow execution error: ${err.message || "Failed to execute workflow."}`,
        intent: "ERROR",
        provenance: "ERROR",
        timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
      };
      setMessages((prev) => [...prev, errorMsg]);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex h-[calc(100vh-8rem)] flex-col rounded-2xl border border-slate-200 bg-white shadow-sm overflow-hidden">
      {/* Top Assistant Header & Workflows */}
      <div className="flex flex-wrap items-center justify-between border-b border-slate-200 bg-slate-50/75 px-6 py-3.5 gap-2">
        <div className="flex items-center gap-2.5">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-sky-600 text-white shadow-sm">
            <Bot className="h-4 w-4" />
          </div>
          <div>
            <h2 className="text-sm font-bold text-slate-900">
              SmartDist AI Copilot
            </h2>
            <p className="text-[11px] text-slate-500">
              Safe Text-to-SQL • RAG SOP Citations • ML Forecasts • Inventory Decision Engine
            </p>
          </div>
        </div>

        {/* Workflow shortcuts */}
        <div className="flex flex-wrap items-center gap-2">
          <button
            onClick={() => handleWorkflowClick("executive_briefing")}
            disabled={loading}
            className="flex items-center gap-1.5 rounded-lg border border-slate-200 bg-white px-2.5 py-1 text-xs font-semibold text-slate-700 shadow-sm hover:bg-slate-50 disabled:opacity-50 transition"
          >
            <Sparkles className="h-3 w-3 text-sky-600" /> Executive Briefing
          </button>
          <button
            onClick={() => handleWorkflowClick("replenishment_explanation", { product_id: 13, branch_id: 44 })}
            disabled={loading}
            className="flex items-center gap-1.5 rounded-lg border border-slate-200 bg-white px-2.5 py-1 text-xs font-semibold text-slate-700 shadow-sm hover:bg-slate-50 disabled:opacity-50 transition"
          >
            <Boxes className="h-3 w-3 text-emerald-600" /> Replenish SOP Check
          </button>
          <button
            onClick={() => handleWorkflowClick("anomaly_root_cause")}
            disabled={loading}
            className="flex items-center gap-1.5 rounded-lg border border-slate-200 bg-white px-2.5 py-1 text-xs font-semibold text-slate-700 shadow-sm hover:bg-slate-50 disabled:opacity-50 transition"
          >
            <AlertTriangle className="h-3 w-3 text-amber-600" /> Anomaly Root Cause
          </button>
        </div>
      </div>

      {/* Messages Stream */}
      <div className="flex-1 overflow-y-auto p-6 space-y-6">
        {messages.map((msg) => (
          <div
            key={msg.id}
            className={`flex gap-3 max-w-3xl ${
              msg.sender === "user" ? "ml-auto flex-row-reverse" : "mr-auto"
            }`}
          >
            <div
              className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-full ${
                msg.sender === "user"
                  ? "bg-slate-800 text-white"
                  : "bg-sky-600 text-white shadow-sm"
              }`}
            >
              {msg.sender === "user" ? <User className="h-4 w-4" /> : <Bot className="h-4 w-4" />}
            </div>

            <div className="space-y-1.5">
              {/* Meta tags for assistant */}
              {msg.sender === "assistant" && msg.intent && (
                <div className="flex flex-wrap items-center gap-2 text-[10px]">
                  <span className="rounded bg-sky-100 px-2 py-0.5 font-bold text-sky-800">
                    {msg.intent}
                  </span>
                  {msg.toolUsed && (
                    <span className="rounded bg-slate-100 px-2 py-0.5 font-medium text-slate-600">
                      Tool: {msg.toolUsed}
                    </span>
                  )}
                  {msg.provenance && (
                    <span className="rounded border border-slate-200 bg-white px-1.5 py-0.5 text-slate-500">
                      {msg.provenance}
                    </span>
                  )}
                  <span className="text-slate-400">{msg.timestamp}</span>
                </div>
              )}

              {/* Message Content */}
              <div
                className={`rounded-2xl px-4 py-3 text-sm leading-relaxed shadow-sm ${
                  msg.sender === "user"
                    ? "bg-slate-900 text-white"
                    : "border border-slate-200 bg-white text-slate-800 whitespace-pre-line"
                }`}
              >
                {msg.text}

                {/* Citations block if any */}
                {msg.citations && msg.citations.length > 0 && (
                  <div className="mt-3 border-t border-slate-100 pt-2 text-xs text-slate-500">
                    <span className="font-bold text-slate-700 flex items-center gap-1">
                      <BookOpen className="h-3 w-3 text-sky-600" /> Grounded SOP Citations:
                    </span>
                    <ul className="mt-1 list-disc pl-4 space-y-0.5 text-[11px] text-sky-800">
                      {msg.citations.map((c, i) => (
                        <li key={i}>{c}</li>
                      ))}
                    </ul>
                  </div>
                )}
              </div>
            </div>
          </div>
        ))}

        {loading && (
          <div className="flex gap-3 max-w-3xl mr-auto items-center">
            <div className="flex h-8 w-8 items-center justify-center rounded-full bg-sky-600 text-white">
              <Bot className="h-4 w-4 animate-spin" />
            </div>
            <div className="rounded-2xl border border-slate-200 bg-white px-4 py-3 text-xs text-slate-500">
              Orchestrating tools, evaluating safety policies, and querying PostgreSQL...
            </div>
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      {/* Suggested Prompts Toolbar */}
      <div className="border-t border-slate-100 bg-slate-50/50 px-4 py-2">
        <div className="flex items-center gap-2 overflow-x-auto no-scrollbar py-1">
          <span className="text-[11px] font-semibold text-slate-400 uppercase shrink-0">
            Suggested:
          </span>
          {SUGGESTED_PROMPTS.map((p, idx) => (
            <button
              key={idx}
              onClick={() => handleSend(p)}
              className="shrink-0 rounded-full border border-slate-200 bg-white px-3 py-1 text-xs text-slate-600 hover:border-sky-300 hover:bg-sky-50 hover:text-sky-700 transition"
            >
              {p}
            </button>
          ))}
        </div>
      </div>

      {/* Input Box */}
      <form
        onSubmit={(e) => {
          e.preventDefault();
          handleSend();
        }}
        className="flex items-center gap-2 border-t border-slate-200 bg-white p-4"
      >
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Ask anything about sales trends, SOPs, LightGBM forecasts, or inventory reorders..."
          className="flex-1 rounded-xl border border-slate-300 px-4 py-2.5 text-sm text-slate-800 placeholder-slate-400 focus:border-sky-500 focus:outline-none"
        />
        <button
          type="submit"
          disabled={!input.trim() || loading}
          className="flex h-10 w-10 items-center justify-center rounded-xl bg-sky-600 text-white shadow-sm hover:bg-sky-700 disabled:opacity-50 transition"
        >
          <Send className="h-4 w-4" />
        </button>
      </form>
    </div>
  );
}

