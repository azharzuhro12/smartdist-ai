"use client";

import React, { useEffect, useState } from "react";
import { api, OptimizationSummaryItem } from "@/lib/api";
import { formatNumber } from "@/lib/utils";

export default function InventoryDecisionPage() {
  const [items, setItems] = useState<OptimizationSummaryItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [serviceLevel, setServiceLevel] = useState<number>(0.95);
  const [selectedItem, setSelectedItem] = useState<OptimizationSummaryItem | null>(null);

  useEffect(() => {
    async function loadData() {
      try {
        setLoading(true);
        setError(null);
        const res = await api.getInventorySummary(1, 20, serviceLevel);
        if (res?.items) {
          setItems(res.items);
          if (res.items.length > 0) {
            setSelectedItem(res.items[0]);
          } else {
            setSelectedItem(null);
          }
        }
      } catch (err: any) {
        setError(err.message || "Failed to load inventory optimization summary.");
      } finally {
        setLoading(false);
      }
    }
    loadData();
  }, [serviceLevel]);

  return (
    <div className="space-y-8">
      {/* Page Header */}
      <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h2 className="text-2xl font-bold tracking-tight text-slate-900">
            Intelligent Inventory Decision Engine
          </h2>
          <p className="text-sm text-slate-500">
            Unified replenishment optimization: Empirical/Parametric Safety Stock, Reorder Point, EOQ, and Stockout Risk.
          </p>
        </div>
        <div className="flex items-center gap-2 rounded-lg border border-slate-200 bg-white p-1 text-xs font-semibold">
          <span className="px-2 text-slate-500">Cycle Service Level:</span>
          {[0.9, 0.95, 0.98].map((lvl) => (
            <button
              key={lvl}
              onClick={() => setServiceLevel(lvl)}
              className={`rounded-md px-2.5 py-1 transition ${
                serviceLevel === lvl
                  ? "bg-sky-600 text-white shadow-sm"
                  : "text-slate-600 hover:text-slate-900"
              }`}
            >
              {(lvl * 100).toFixed(0)}% CSL
            </button>
          ))}
        </div>
      </div>

      {error && (
        <div className="rounded-lg border border-rose-200 bg-rose-50 p-4 text-xs font-medium text-rose-700">
          {error}
        </div>
      )}

      {/* Selected Item Decision Card (Deep Dive) */}
      {selectedItem && (
        <div className="rounded-xl border border-sky-200 bg-white p-6 shadow-sm">
          <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between border-b border-slate-100 pb-4">
            <div>
              <span className="text-xs font-semibold uppercase text-sky-600">
                Active Decision Evaluation
              </span>
              <h3 className="text-lg font-bold text-slate-900">
                {selectedItem.product_name} at {selectedItem.branch_name}
              </h3>
            </div>
            <div className="flex items-center gap-2">
              <span
                className={`rounded-full px-3 py-1 text-xs font-bold ${
                  (selectedItem.recommended_order_quantity ?? 0) > 0
                    ? "bg-rose-100 text-rose-700"
                    : "bg-emerald-100 text-emerald-700"
                }`}
              >
                {selectedItem.decision || "NO_ACTION"}
              </span>
            </div>
          </div>

          <div className="mt-5 grid grid-cols-2 gap-4 sm:grid-cols-4 lg:grid-cols-5">
            <div className="rounded-lg bg-slate-50 p-3">
              <span className="text-[11px] font-semibold text-slate-500 uppercase">Available Stock</span>
              <div className="mt-1 text-xl font-bold text-slate-900">
                {selectedItem.available_stock !== undefined && selectedItem.available_stock !== null
                  ? `${formatNumber(selectedItem.available_stock)} units`
                  : "Unassigned"}
              </div>
            </div>

            <div className="rounded-lg bg-slate-50 p-3">
              <span className="text-[11px] font-semibold text-slate-500 uppercase">Safety Stock (SS)</span>
              <div className="mt-1 text-xl font-bold text-sky-600">
                {formatNumber(selectedItem.safety_stock, 1)} units
              </div>
              <span className="text-[10px] text-slate-400">
                Target CSL {(serviceLevel * 100).toFixed(0)}%
              </span>
            </div>

            <div className="rounded-lg bg-slate-50 p-3">
              <span className="text-[11px] font-semibold text-slate-500 uppercase">Reorder Point (ROP)</span>
              <div className="mt-1 text-xl font-bold text-amber-600">
                {formatNumber(selectedItem.reorder_point, 1)} units
              </div>
              <span className="text-[10px] text-slate-400">Demand + SS Buffer</span>
            </div>

            <div className="rounded-lg bg-slate-50 p-3">
              <span className="text-[11px] font-semibold text-slate-500 uppercase">Lead-Time Demand</span>
              <div className="mt-1 text-xl font-bold text-slate-900">
                {formatNumber(selectedItem.expected_lead_time_demand, 1)} units
              </div>
              <span className="text-[10px] text-slate-400">Expected Cycle Velocity</span>
            </div>

            <div className="rounded-lg bg-slate-50 p-3">
              <span className="text-[11px] font-semibold text-slate-500 uppercase">Recommended Order</span>
              <div className="mt-1 text-xl font-bold text-emerald-600">
                {formatNumber(selectedItem.recommended_order_quantity)} units
              </div>
              <span className="text-[10px] text-slate-400">
                Risk Tier: {selectedItem.risk_category || "EVALUATED"}
              </span>
            </div>
          </div>

          <div className="mt-4 rounded-lg bg-slate-50 p-3 text-xs text-slate-600">
            <span className="font-bold text-slate-800">Operational Decision Status: </span>
            {selectedItem.decision === "REORDER_REQUIRED"
              ? `Reorder triggered. Current available inventory is below the reorder point threshold (${formatNumber(selectedItem.reorder_point, 1)} units). Dispatch purchase order for ${formatNumber(selectedItem.recommended_order_quantity)} units.`
              : selectedItem.decision === "NO_ACTION"
              ? `Healthy inventory buffer. Available stock (${formatNumber(selectedItem.available_stock)} units) exceeds reorder point (${formatNumber(selectedItem.reorder_point, 1)} units). No order required.`
              : `Status: ${selectedItem.decision || "Evaluated"}. Stockout risk: ${selectedItem.risk_category || "Normal"}.`}
          </div>
        </div>
      )}

      {/* Inventory Optimization Table */}
      <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h3 className="text-base font-bold text-slate-900">
              Network Replenishment Decision Queue
            </h3>
            <p className="text-xs text-slate-500">
              Evaluated at {(serviceLevel * 100).toFixed(0)}% Cycle Service Level
            </p>
          </div>
          <span className="rounded bg-sky-50 px-2.5 py-1 text-xs font-semibold text-sky-700">
            {items.length} Products Monitored
          </span>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead className="border-b border-slate-100 bg-slate-50/75 text-slate-600 uppercase tracking-wider font-semibold">
              <tr>
                <th className="py-2.5 px-3">Product Family</th>
                <th className="py-2.5 px-3">Store Branch</th>
                <th className="py-2.5 px-3">Available Stock</th>
                <th className="py-2.5 px-3">Safety Stock</th>
                <th className="py-2.5 px-3">Reorder Point</th>
                <th className="py-2.5 px-3">Lead-Time Demand</th>
                <th className="py-2.5 px-3">Stockout Risk</th>
                <th className="py-2.5 px-3">Decision</th>
                <th className="py-2.5 px-3">Action</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 text-slate-700">
              {loading ? (
                <tr>
                  <td colSpan={9} className="py-8 text-center text-slate-400">
                    Evaluating network inventory optimization policies...
                  </td>
                </tr>
              ) : items.length === 0 ? (
                <tr>
                  <td colSpan={9} className="py-8 text-center text-slate-400">
                    No inventory items available for evaluation.
                  </td>
                </tr>
              ) : (
                items.map((it, idx) => {
                  const isSelected =
                    selectedItem?.product_id === it.product_id &&
                    selectedItem?.branch_id === it.branch_id;
                  const isReorder = (it.recommended_order_quantity ?? 0) > 0;
                  return (
                    <tr
                      key={idx}
                      onClick={() => setSelectedItem(it)}
                      className={`cursor-pointer transition-colors ${
                        isSelected ? "bg-sky-50/80" : "hover:bg-slate-50/80"
                      }`}
                    >
                      <td className="py-2.5 px-3 font-semibold text-slate-900">
                        {it.product_name}
                      </td>
                      <td className="py-2.5 px-3">{it.branch_name}</td>
                      <td className="py-2.5 px-3 font-medium text-slate-800">
                        {it.available_stock !== null && it.available_stock !== undefined
                          ? formatNumber(it.available_stock)
                          : "N/A"}
                      </td>
                      <td className="py-2.5 px-3 font-medium text-sky-700">
                        {formatNumber(it.safety_stock, 1)}
                      </td>
                      <td className="py-2.5 px-3 font-medium text-amber-700">
                        {formatNumber(it.reorder_point, 1)}
                      </td>
                      <td className="py-2.5 px-3">
                        {formatNumber(it.expected_lead_time_demand, 1)}
                      </td>
                      <td className="py-2.5 px-3">
                        <span className="font-semibold text-slate-700">
                          {it.risk_category || "EVALUATED"}
                        </span>
                      </td>
                      <td className="py-2.5 px-3">
                        <span
                          className={`font-bold px-2 py-0.5 rounded text-[10px] ${
                            isReorder
                              ? "bg-rose-100 text-rose-700"
                              : "bg-emerald-100 text-emerald-700"
                          }`}
                        >
                          {it.decision || "NO_ACTION"}
                        </span>
                      </td>
                      <td className="py-2.5 px-3">
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            setSelectedItem(it);
                          }}
                          className="text-[11px] font-semibold text-sky-600 hover:text-sky-800"
                        >
                          Inspect
                        </button>
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
