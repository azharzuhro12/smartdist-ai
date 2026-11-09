"use client";

import React, { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { formatNumber, formatCurrency } from "@/lib/utils";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from "recharts";

export default function SalesAnalyticsPage() {
  const [metric, setMetric] = useState<"volume" | "revenue">("volume");
  const [topProducts, setTopProducts] = useState<any[]>([]);
  const [branches, setBranches] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function loadData() {
      try {
        setLoading(true);
        setError(null);
        const [prodRes, branchRes] = await Promise.all([
          api.getTopProducts(10, metric),
          api.getBranchPerformance(),
        ]);
        if (prodRes?.rows) setTopProducts(prodRes.rows);
        if (branchRes?.rows) setBranches(branchRes.rows);
      } catch (err: any) {
        setError(err.message || "Failed to load sales analytics data.");
      } finally {
        setLoading(false);
      }
    }
    loadData();
  }, [metric]);

  return (
    <div className="space-y-8">
      {/* Page Title */}
      <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h2 className="text-2xl font-bold tracking-tight text-slate-900">
            Sales & Physical Demand Analytics
          </h2>
          <p className="text-sm text-slate-500">
            Historical observed daily transactions across {branches.length || 54} stores and 33 product families.
          </p>
        </div>
        <div className="flex items-center gap-2 rounded-lg border border-slate-200 bg-white p-1 text-xs font-semibold">
          <button
            onClick={() => setMetric("volume")}
            className={`rounded-md px-3 py-1.5 transition ${
              metric === "volume"
                ? "bg-sky-600 text-white shadow-sm"
                : "text-slate-600 hover:text-slate-900"
            }`}
          >
            Physical Demand (Units)
          </button>
          <button
            onClick={() => setMetric("revenue")}
            className={`rounded-md px-3 py-1.5 transition ${
              metric === "revenue"
                ? "bg-sky-600 text-white shadow-sm"
                : "text-slate-600 hover:text-slate-900"
            }`}
          >
            Estimated Revenue ($)
          </button>
        </div>
      </div>

      {error && (
        <div className="rounded-lg border border-rose-200 bg-rose-50 p-4 text-xs font-medium text-rose-700">
          {error}
        </div>
      )}

      {/* Main Bar Chart: Top Product Families */}
      <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
        <h3 className="text-base font-bold text-slate-900 mb-1">
          Top 10 Product Families by {metric === "volume" ? "Physical Units" : "Estimated Revenue"}
        </h3>
        <p className="text-xs text-slate-500 mb-6">
          Kaggle 2013 Ecuadorian grocery transaction records
        </p>

        <div className="h-80 w-full">
          {loading ? (
            <div className="flex h-full items-center justify-center text-xs text-slate-400">
              Loading product family analytics...
            </div>
          ) : topProducts.length === 0 ? (
            <div className="flex h-full items-center justify-center text-xs text-slate-400">
              No product sales records found.
            </div>
          ) : (
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={topProducts}>
                <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#f1f5f9" />
                <XAxis
                  dataKey="product_name"
                  tick={{ fontSize: 11, fill: "#64748b" }}
                  interval={0}
                  angle={-20}
                  textAnchor="end"
                  height={60}
                />
                <YAxis
                  tick={{ fontSize: 11, fill: "#64748b" }}
                  tickFormatter={(val) =>
                    metric === "volume"
                      ? `${(val / 1_000_000).toFixed(0)}M`
                      : `$${(val / 1_000_000).toFixed(0)}M`
                  }
                />
                <Tooltip
                  formatter={(val: any) => [
                    metric === "volume" ? `${formatNumber(val)} units` : formatCurrency(val),
                    metric === "volume" ? "Physical Demand" : "Estimated Revenue",
                  ]}
                />
                <Bar
                  dataKey={metric === "volume" ? "total_quantity_sold" : "total_estimated_revenue"}
                  fill={metric === "volume" ? "#0284c7" : "#0d9488"}
                  radius={[4, 4, 0, 0]}
                />
              </BarChart>
            </ResponsiveContainer>
          )}
        </div>
      </div>

      {/* Branch Performance Rankings Table */}
      <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h3 className="text-base font-bold text-slate-900">
              Branch Store Performance Rankings
            </h3>
            <p className="text-xs text-slate-500">
              Aggregated across active retail store branches (Quito, Guayaquil, Cuenca, etc.)
            </p>
          </div>
          <span className="rounded bg-sky-50 px-2.5 py-1 text-xs font-semibold text-sky-700">
            {branches.length} Branches Loaded
          </span>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead className="border-b border-slate-100 bg-slate-50/75 text-slate-600 uppercase tracking-wider font-semibold">
              <tr>
                <th className="py-2.5 px-3">Branch ID</th>
                <th className="py-2.5 px-3">Store Name</th>
                <th className="py-2.5 px-3">City</th>
                <th className="py-2.5 px-3">Province</th>
                <th className="py-2.5 px-3">Store Type</th>
                <th className="py-2.5 px-3">Total Physical Units</th>
                <th className="py-2.5 px-3">Estimated Revenue</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 text-slate-700">
              {loading ? (
                <tr>
                  <td colSpan={7} className="py-6 text-center text-slate-400">
                    Loading branch store performance...
                  </td>
                </tr>
              ) : branches.length === 0 ? (
                <tr>
                  <td colSpan={7} className="py-6 text-center text-slate-400">
                    No branch records available.
                  </td>
                </tr>
              ) : (
                branches.map((b) => (
                  <tr key={b.id} className="hover:bg-slate-50/80 transition-colors">
                    <td className="py-2.5 px-3 font-semibold text-slate-900">#{b.id}</td>
                    <td className="py-2.5 px-3 font-medium">{b.branch_name}</td>
                    <td className="py-2.5 px-3">{b.city}</td>
                    <td className="py-2.5 px-3">{b.state}</td>
                    <td className="py-2.5 px-3">
                      <span className="rounded bg-slate-100 px-2 py-0.5 font-bold text-slate-700">
                        Type {b.store_type}
                      </span>
                    </td>
                    <td className="py-2.5 px-3 font-semibold text-slate-900">
                      {formatNumber(b.total_quantity_sold)}
                    </td>
                    <td className="py-2.5 px-3 font-semibold text-emerald-700">
                      {formatCurrency(b.total_estimated_revenue)}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
