"use client";

import React, { useEffect, useState, useCallback } from "react";
import {
  Filter,
  Eye,
  ArrowUpRight,
  ArrowDownRight,
  X,
} from "lucide-react";
import { api, AnomalyItem, AnomalyStatus } from "@/lib/api";
import { formatNumber } from "@/lib/utils";
import { useAuth } from "@/context/AuthContext";

export default function AnomalyExplorerPage() {
  const { user } = useAuth();
  const isViewer = user?.role === "VIEWER";
  const [anomalies, setAnomalies] = useState<AnomalyItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedSeverity, setSelectedSeverity] = useState<string>("");
  const [selectedStatus, setSelectedStatus] = useState<string>("");
  const [activeModal, setActiveModal] = useState<AnomalyItem | null>(null);
  const [patching, setPatching] = useState(false);
  const [resolutionNote, setResolutionNote] = useState("");

  const loadAnomalies = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const res = await api.getAnomalies(
        selectedStatus || undefined,
        selectedSeverity || undefined,
        50
      );
      if (res?.items) {
        setAnomalies(res.items);
      }
    } catch (err: any) {
      setError(err.message || "Failed to load anomalies.");
    } finally {
      setLoading(false);
    }
  }, [selectedStatus, selectedSeverity]);

  useEffect(() => {
    loadAnomalies();
  }, [loadAnomalies]);

  const handleUpdateStatus = async (newStatus: AnomalyStatus) => {
    if (!activeModal) return;
    try {
      setPatching(true);
      setError(null);
      const updated = await api.patchAnomalyStatus(activeModal.id, newStatus, resolutionNote);
      setActiveModal({
        ...activeModal,
        investigation_status: updated.investigation_status || newStatus,
        resolution_note: updated.resolution_note ?? resolutionNote,
      });
      await loadAnomalies();
    } catch (err: any) {
      setError(err.message || "Failed to update anomaly status.");
    } finally {
      setPatching(false);
    }
  };

  return (
    <div className="space-y-8">
      {/* Page Title */}
      <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h2 className="text-2xl font-bold tracking-tight text-slate-900">
            Sales Anomaly Detection & Triage Explorer
          </h2>
          <p className="text-sm text-slate-500">
            Ensemble anomaly detection combining Statistical Z-Score, Forecast Residuals, and ML Isolation Forest.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <span className="rounded bg-sky-50 px-3 py-1.5 text-xs font-bold text-sky-700">
            {anomalies.length} Records Loaded
          </span>
        </div>
      </div>

      {error && (
        <div className="rounded-lg border border-rose-200 bg-rose-50 p-4 text-xs font-medium text-rose-700">
          {error}
        </div>
      )}

      {/* Filter Toolbar */}
      <div className="flex flex-wrap items-center gap-4 rounded-xl border border-slate-200 bg-white p-4 shadow-sm text-xs">
        <div className="flex items-center gap-2">
          <Filter className="h-4 w-4 text-slate-500" />
          <span className="font-semibold text-slate-700">Severity:</span>
          {["", "CRITICAL", "HIGH", "MEDIUM", "LOW", "NORMAL"].map((sev) => (
            <button
              key={sev}
              onClick={() => setSelectedSeverity(sev)}
              className={`rounded-md px-2.5 py-1 font-medium transition ${
                selectedSeverity === sev
                  ? "bg-sky-600 text-white"
                  : "bg-slate-100 text-slate-600 hover:bg-slate-200"
              }`}
            >
              {sev || "All Severities"}
            </button>
          ))}
        </div>

        <div className="h-4 w-px bg-slate-200" />

        <div className="flex items-center gap-2">
          <span className="font-semibold text-slate-700">Status:</span>
          {["", "NEW", "INVESTIGATING", "CONFIRMED", "FALSE_POSITIVE", "RESOLVED"].map((st) => (
            <button
              key={st}
              onClick={() => setSelectedStatus(st)}
              className={`rounded-md px-2.5 py-1 font-medium transition ${
                selectedStatus === st
                  ? "bg-slate-800 text-white"
                  : "bg-slate-100 text-slate-600 hover:bg-slate-200"
              }`}
            >
              {st || "All Statuses"}
            </button>
          ))}
        </div>
      </div>

      {/* Anomalies Table */}
      <div className="rounded-xl border border-slate-200 bg-white shadow-sm overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead className="border-b border-slate-100 bg-slate-50/80 text-slate-600 uppercase tracking-wider font-semibold">
              <tr>
                <th className="py-3 px-4">Date</th>
                <th className="py-3 px-4">Product Family</th>
                <th className="py-3 px-4">Store Branch</th>
                <th className="py-3 px-4">Type</th>
                <th className="py-3 px-4">Observed</th>
                <th className="py-3 px-4">Expected</th>
                <th className="py-3 px-4">Deviation</th>
                <th className="py-3 px-4">Severity</th>
                <th className="py-3 px-4">Status</th>
                <th className="py-3 px-4">Triage</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 text-slate-700">
              {loading ? (
                <tr>
                  <td colSpan={10} className="py-8 text-center text-slate-400">
                    Scanning anomaly database...
                  </td>
                </tr>
              ) : anomalies.length === 0 ? (
                <tr>
                  <td colSpan={10} className="py-8 text-center text-slate-400">
                    No anomalies match the selected filters.
                  </td>
                </tr>
              ) : (
                anomalies.map((a) => (
                  <tr key={a.id} className="hover:bg-slate-50/80 transition-colors">
                    <td className="py-2.5 px-4 font-semibold text-slate-900">{a.anomaly_date}</td>
                    <td className="py-2.5 px-4 font-medium">{a.product_name || `Product #${a.product_id}`}</td>
                    <td className="py-2.5 px-4">{a.branch_name || `Branch #${a.branch_id}`}</td>
                    <td className="py-2.5 px-4">
                      <span
                        className={`inline-flex items-center gap-1 font-bold px-2 py-0.5 rounded text-[10px] ${
                          a.direction === "SPIKE"
                            ? "bg-amber-100 text-amber-800"
                            : "bg-blue-100 text-blue-800"
                        }`}
                      >
                        {a.direction === "SPIKE" ? (
                          <ArrowUpRight className="h-3 w-3" />
                        ) : (
                          <ArrowDownRight className="h-3 w-3" />
                        )}
                        {a.direction}
                      </span>
                    </td>
                    <td className="py-2.5 px-4 font-semibold text-slate-900">
                      {formatNumber(a.observed_quantity)}
                    </td>
                    <td className="py-2.5 px-4 text-slate-500">
                      {formatNumber(a.expected_quantity)}
                    </td>
                    <td className="py-2.5 px-4 font-medium">
                      {a.deviation > 0 ? `+${formatNumber(a.deviation)}` : formatNumber(a.deviation)}
                    </td>
                    <td className="py-2.5 px-4">
                      <span
                        className={`font-bold px-2 py-0.5 rounded text-[10px] ${
                          a.severity === "CRITICAL"
                            ? "bg-rose-100 text-rose-700"
                            : a.severity === "HIGH"
                            ? "bg-orange-100 text-orange-700"
                            : "bg-yellow-100 text-yellow-800"
                        }`}
                      >
                        {a.severity}
                      </span>
                    </td>
                    <td className="py-2.5 px-4 font-medium text-slate-600">
                      {a.investigation_status}
                    </td>
                    <td className="py-2.5 px-4">
                      <button
                        onClick={() => {
                          setActiveModal(a);
                          setResolutionNote(a.resolution_note || "");
                        }}
                        className="flex items-center gap-1 rounded bg-sky-50 px-2 py-1 text-[11px] font-semibold text-sky-700 hover:bg-sky-100 transition"
                      >
                        <Eye className="h-3 w-3" /> Review
                      </button>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Anomaly Detail & Triage Modal */}
      {activeModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/50 p-4 backdrop-blur-sm">
          <div className="w-full max-w-2xl rounded-2xl bg-white p-6 shadow-xl border border-slate-200">
            <div className="flex items-center justify-between border-b border-slate-100 pb-3">
              <div>
                <span className="text-xs font-bold uppercase tracking-wider text-sky-600">
                  Incident Review & Root Cause Triage
                </span>
                <h3 className="text-lg font-bold text-slate-900">
                  {activeModal.product_name} at {activeModal.branch_name}
                </h3>
              </div>
              <button
                onClick={() => setActiveModal(null)}
                className="rounded-lg p-1 text-slate-400 hover:bg-slate-100 hover:text-slate-600"
              >
                <X className="h-5 w-5" />
              </button>
            </div>

            <div className="mt-4 grid grid-cols-2 sm:grid-cols-4 gap-3 text-xs">
              <div className="rounded-lg bg-slate-50 p-2.5">
                <span className="text-slate-500 font-medium">Anomaly Date</span>
                <div className="text-sm font-bold text-slate-900">{activeModal.anomaly_date}</div>
              </div>
              <div className="rounded-lg bg-slate-50 p-2.5">
                <span className="text-slate-500 font-medium">Observed vs Expected</span>
                <div className="text-sm font-bold text-slate-900">
                  {formatNumber(activeModal.observed_quantity)} / {formatNumber(activeModal.expected_quantity)}
                </div>
              </div>
              <div className="rounded-lg bg-slate-50 p-2.5">
                <span className="text-slate-500 font-medium">Severity Score</span>
                <div className="text-sm font-bold text-rose-600">
                  {activeModal.anomaly_score.toFixed(3)} ({activeModal.severity})
                </div>
              </div>
              <div className="rounded-lg bg-slate-50 p-2.5">
                <span className="text-slate-500 font-medium">Current Status</span>
                <div className="text-sm font-bold text-sky-700">{activeModal.investigation_status}</div>
              </div>
            </div>

            <div className="mt-4 space-y-3 text-xs">
              <div className="rounded-lg border border-slate-100 bg-slate-50 p-3">
                <span className="font-bold text-slate-800">AI Root Cause Diagnosis:</span>
                <p className="mt-1 text-slate-600 leading-relaxed">{activeModal.explanation}</p>
              </div>

              {activeModal.recommended_actions && (
                <div className="rounded-lg border border-amber-100 bg-amber-50/60 p-3 text-amber-900">
                  <span className="font-bold">Recommended Protocol:</span>
                  <p className="mt-1 leading-relaxed">
                    {Array.isArray(activeModal.recommended_actions)
                      ? activeModal.recommended_actions.join(" • ")
                      : activeModal.recommended_actions}
                  </p>
                </div>
              )}

              {/* Resolution Note Input & Triage Status Buttons */}
              <div className="border-t border-slate-100 pt-3 space-y-3">
                <div>
                  <label className="block font-semibold text-slate-700 mb-1">
                    Resolution / Triage Note:
                  </label>
                  <input
                    type="text"
                    value={resolutionNote}
                    onChange={(e) => setResolutionNote(e.target.value)}
                    placeholder="Enter investigation findings or resolution note..."
                    className="w-full rounded-lg border border-slate-300 px-3 py-1.5 text-xs text-slate-800 focus:border-sky-500 focus:outline-none"
                  />
                </div>
                {isViewer ? (
                  <div className="rounded-lg bg-amber-50 p-2.5 text-xs text-amber-800 border border-amber-200">
                    <span className="font-semibold">Role Permission Notice:</span> You are logged in as a <strong>VIEWER</strong> (Read-Only). Updating investigation statuses requires an <strong>ANALYST</strong> or <strong>ADMIN</strong> account.
                  </div>
                ) : (
                  <div>
                    <label className="block font-semibold text-slate-700 mb-2">
                      Update Investigation Status:
                    </label>
                    <div className="flex flex-wrap gap-2">
                      {(["NEW", "INVESTIGATING", "CONFIRMED", "FALSE_POSITIVE", "RESOLVED"] as AnomalyStatus[]).map(
                        (status) => (
                          <button
                            key={status}
                            disabled={patching}
                            onClick={() => handleUpdateStatus(status)}
                            className={`rounded-lg px-3 py-1.5 font-bold transition ${
                              activeModal.investigation_status === status
                                ? "bg-sky-600 text-white shadow-sm"
                                : "bg-slate-100 text-slate-700 hover:bg-slate-200"
                            }`}
                          >
                            {status}
                          </button>
                        )
                      )}
                    </div>
                  </div>
                )}
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
