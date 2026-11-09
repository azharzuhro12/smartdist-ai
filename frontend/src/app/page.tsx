"use client";

import React, { useEffect, useState } from "react";
import {
  TrendingUp,
  DollarSign,
  Store,
  AlertTriangle,
  ArrowRight,
  Sparkles,
} from "lucide-react";
import Link from "next/link";
import { KPICard } from "@/components/KPICard";
import { api, AnomalyItem, DataSummaryResponse, OptimizationSummaryItem } from "@/lib/api";
import { formatNumber } from "@/lib/utils";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from "recharts";

export default function DashboardOverviewPage() {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [dataSummary, setDataSummary] = useState<DataSummaryResponse | null>(null);
  const [totalDemand, setTotalDemand] = useState<number | null>(null);
  const [totalRevenue, setTotalRevenue] = useState<number | null>(null);
  const [totalAnomaliesCount, setTotalAnomaliesCount] = useState<number | null>(null);
  const [topProducts, setTopProducts] = useState<any[]>([]);
  const [anomalies, setAnomalies] = useState<AnomalyItem[]>([]);
  const [inventoryItems, setInventoryItems] = useState<OptimizationSummaryItem[]>([]);
  const [executiveSummary, setExecutiveSummary] = useState<string | null>(null);
  const [summaryLoading, setSummaryLoading] = useState(false);

  useEffect(() => {
    async function loadData() {
      try {
        setLoading(true);
        setError(null);
        const [sumRes, branchRes, prodRes, anomRes, invRes] = await Promise.allSettled([
          api.getDataSummary(),
          api.getBranchPerformance(),
          api.getTopProducts(6),
          api.getAnomalies(undefined, undefined, 5),
          api.getInventorySummary(1, 5),
        ]);

        if (sumRes.status === "fulfilled" && sumRes.value) {
          setDataSummary(sumRes.value);
        }
        if (branchRes.status === "fulfilled" && branchRes.value?.rows) {
          const rows = branchRes.value.rows;
          const demandSum = rows.reduce(
            (acc: number, r: any) => acc + Number(r.total_quantity_sold || 0),
            0
          );
          const revSum = rows.reduce(
            (acc: number, r: any) => acc + Number(r.total_estimated_revenue || 0),
            0
          );
          setTotalDemand(demandSum);
          setTotalRevenue(revSum);
        }
        if (prodRes.status === "fulfilled" && prodRes.value?.rows) {
          setTopProducts(prodRes.value.rows);
        }
        if (anomRes.status === "fulfilled" && anomRes.value) {
          setAnomalies(anomRes.value.items || []);
          setTotalAnomaliesCount(anomRes.value.total ?? anomRes.value.items?.length ?? 0);
        }
        if (invRes.status === "fulfilled" && invRes.value?.items) {
          setInventoryItems(invRes.value.items);
        }

        const allRejected = [sumRes, branchRes, prodRes, anomRes, invRes].every(
          (r) => r.status === "rejected"
        );
        if (allRejected) {
          setError("Unable to reach SmartDist AI backend API. Please verify that the backend server is running.");
        }
      } catch (err: any) {
        setError(err.message || "Failed to load dashboard data.");
      } finally {
        setLoading(false);
      }
    }
    loadData();
  }, []);

  const handleGenerateBriefing = async () => {
    try {
      setSummaryLoading(true);
      setError(null);
      const res = await api.executeWorkflow("executive_briefing");
      setExecutiveSummary(res.report);
    } catch (err: any) {
      setError(err.message || "Failed to generate executive briefing.");
    } finally {
      setSummaryLoading(false);
    }
  };

  const formattedDemand =
    totalDemand !== null ? `${(totalDemand / 1_000_000).toFixed(1)}M` : loading ? "Loading..." : "N/A";
  const formattedRevenue =
    totalRevenue !== null ? `$${(totalRevenue / 1_000_000).toFixed(1)}M` : loading ? "Loading..." : "N/A";
  const formattedStores =
    dataSummary !== null ? `${dataSummary.branches} Stores` : loading ? "Loading..." : "N/A";
  const formattedSalesCount =
    dataSummary !== null
      ? `${formatNumber(dataSummary.daily_sales_records)} historical daily records`
      : "Historical daily POS records";
  const formattedAnomalies =
    totalAnomaliesCount !== null
      ? `${totalAnomaliesCount} Flagged`
      : loading
      ? "Loading..."
      : `${anomalies.length} Flagged`;

  return (
    <div className="space-y-8">
      {/* Top Banner / Actions */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h2 className="text-2xl font-bold tracking-tight text-slate-900">
            Executive Operations Dashboard
          </h2>
          <p className="text-sm text-slate-500">
            Real-time retail intelligence, machine learning forecasting, and autonomous decision engine.
          </p>
        </div>
        <div className="flex items-center gap-3">
          <button
            onClick={handleGenerateBriefing}
            disabled={summaryLoading}
            className="flex items-center gap-2 rounded-lg bg-sky-600 px-4 py-2 text-sm font-semibold text-white shadow hover:bg-sky-700 disabled:opacity-50 transition"
          >
            <Sparkles className="h-4 w-4" />
            {summaryLoading ? "Synthesizing AI Briefing..." : "Generate AI Briefing"}
          </button>
          <Link
            href="/assistant"
            className="flex items-center gap-2 rounded-lg border border-slate-300 bg-white px-4 py-2 text-sm font-semibold text-slate-700 shadow-sm hover:bg-slate-50 transition"
          >
            Open Assistant <ArrowRight className="h-4 w-4" />
          </Link>
        </div>
      </div>

      {error && (
        <div className="rounded-lg border border-rose-200 bg-rose-50 p-4 text-xs font-medium text-rose-700">
          {error}
        </div>
      )}

      {/* AI Briefing Modal/Card if generated */}
      {executiveSummary && (
        <div className="rounded-xl border border-sky-200 bg-sky-50/70 p-6 shadow-sm">
          <div className="flex items-center justify-between pb-3 border-b border-sky-100">
            <span className="flex items-center gap-2 font-bold text-sky-900">
              <Sparkles className="h-4 w-4 text-sky-600" /> SmartDist AI Executive Briefing
            </span>
            <button
              onClick={() => setExecutiveSummary(null)}
              className="text-xs text-sky-700 hover:text-sky-900 font-semibold"
            >
              Dismiss
            </button>
          </div>
          <div className="mt-4 whitespace-pre-line text-sm leading-relaxed text-slate-800">
            {executiveSummary}
          </div>
        </div>
      )}

      {/* KPI Cards */}
      <div className="grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-4">
        <KPICard
          title="Total Observed Demand"
          value={formattedDemand}
          subtitle={formattedSalesCount}
          icon={TrendingUp}
          provenance="KAGGLE_PUBLIC"
        />
        <KPICard
          title="Estimated Revenue"
          value={formattedRevenue}
          subtitle="Observed Volume × Unit Reference Price"
          icon={DollarSign}
          provenance="DERIVED"
        />
        <KPICard
          title="Active Retail Network"
          value={formattedStores}
          subtitle={
            dataSummary
              ? `${dataSummary.products} products across ${dataSummary.warehouses} warehouses`
              : "Enterprise branch network"
          }
          icon={Store}
          provenance="ENTERPRISE_DB"
        />
        <KPICard
          title="Active Anomalies"
          value={formattedAnomalies}
          subtitle="Statistical & ML residual ensemble"
          icon={AlertTriangle}
          provenance="MODEL_GENERATED"
        />
      </div>

      {/* Main Grid: Chart + Inventory Risk */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        {/* Sales by Top Product Family */}
        <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm lg:col-span-2">
          <div className="flex items-center justify-between mb-4">
            <div>
              <h3 className="text-base font-bold text-slate-900">
                Top Product Families by Physical Volume
              </h3>
              <p className="text-xs text-slate-500">
                Units sold aggregated across all active retail store branches
              </p>
            </div>
            <Link
              href="/sales"
              className="text-xs font-semibold text-sky-600 hover:text-sky-800 flex items-center gap-1"
            >
              View Full Analytics <ArrowRight className="h-3 w-3" />
            </Link>
          </div>

          <div className="h-72 w-full">
            {loading ? (
              <div className="flex h-full items-center justify-center text-xs text-slate-400">
                Loading volume distribution...
              </div>
            ) : topProducts.length > 0 ? (
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={topProducts}>
                  <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#f1f5f9" />
                  <XAxis
                    dataKey="product_name"
                    tick={{ fontSize: 11, fill: "#64748b" }}
                    interval={0}
                    angle={-15}
                    textAnchor="end"
                    height={50}
                  />
                  <YAxis
                    tick={{ fontSize: 11, fill: "#64748b" }}
                    tickFormatter={(val) => `${(val / 1_000_000).toFixed(0)}M`}
                  />
                  <Tooltip
                    formatter={(val: any) => [`${formatNumber(val)} units`, "Volume"]}
                    labelStyle={{ fontWeight: "bold" }}
                  />
                  <Bar dataKey="total_quantity_sold" fill="#0284c7" radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            ) : (
              <div className="flex h-full items-center justify-center text-xs text-slate-400">
                No product volume records available.
              </div>
            )}
          </div>
        </div>

        {/* Priority Replenishment Widget */}
        <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
          <div className="flex items-center justify-between mb-4">
            <div>
              <h3 className="text-base font-bold text-slate-900">
                Priority Replenishment
              </h3>
              <p className="text-xs text-slate-500">
                Stockout risks & reorder triggers
              </p>
            </div>
            <Link
              href="/inventory"
              className="text-xs font-semibold text-sky-600 hover:text-sky-800 flex items-center gap-1"
            >
              Full Engine <ArrowRight className="h-3 w-3" />
            </Link>
          </div>

          <div className="space-y-3">
            {loading ? (
              <div className="py-8 text-center text-xs text-slate-400">
                Evaluating inventory policies...
              </div>
            ) : inventoryItems.length === 0 ? (
              <div className="py-8 text-center text-xs text-slate-400">
                No replenishment records available.
              </div>
            ) : (
              inventoryItems.slice(0, 4).map((it, idx) => {
                const isReorder = (it.recommended_order_quantity ?? 0) > 0;
                const decision = it.decision || "NO_ACTION";
                const rop =
                  it.reorder_point !== null && it.reorder_point !== undefined
                    ? it.reorder_point.toFixed(1)
                    : "N/A";
                const orderQty = it.recommended_order_quantity ?? 0;
                return (
                  <div
                    key={idx}
                    className="rounded-lg border border-slate-100 bg-slate-50/60 p-3 text-xs"
                  >
                    <div className="flex items-center justify-between font-semibold text-slate-800">
                      <span className="truncate max-w-[140px]">{it.product_name}</span>
                      <span
                        className={`rounded px-1.5 py-0.5 text-[10px] font-bold ${
                          isReorder
                            ? "bg-rose-100 text-rose-700"
                            : "bg-emerald-100 text-emerald-700"
                        }`}
                      >
                        {decision}
                      </span>
                    </div>
                    <div className="mt-1 flex items-center justify-between text-slate-500">
                      <span>{it.branch_name}</span>
                      <span className="font-medium text-slate-700">ROP: {rop}</span>
                    </div>
                    {isReorder && (
                      <div className="mt-1.5 font-medium text-sky-700">
                        Order: {orderQty} units
                      </div>
                    )}
                  </div>
                );
              })
            )}
          </div>
        </div>
      </div>

      {/* Recent Anomalies Table */}
      <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h3 className="text-base font-bold text-slate-900">
              Recent Sales Anomalies Requiring Review
            </h3>
            <p className="text-xs text-slate-500">
              Flagged by statistical z-score, forecast residual, and Isolation Forest
            </p>
          </div>
          <Link
            href="/anomalies"
            className="text-xs font-semibold text-sky-600 hover:text-sky-800 flex items-center gap-1"
          >
            Explore All Anomalies <ArrowRight className="h-3 w-3" />
          </Link>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead className="border-b border-slate-100 bg-slate-50/75 text-slate-600 uppercase tracking-wider font-semibold">
              <tr>
                <th className="py-2.5 px-3">Date</th>
                <th className="py-2.5 px-3">Product Family</th>
                <th className="py-2.5 px-3">Store Branch</th>
                <th className="py-2.5 px-3">Type</th>
                <th className="py-2.5 px-3">Observed</th>
                <th className="py-2.5 px-3">Expected</th>
                <th className="py-2.5 px-3">Severity</th>
                <th className="py-2.5 px-3">Status</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 text-slate-700">
              {loading ? (
                <tr>
                  <td colSpan={8} className="py-6 text-center text-slate-400">
                    Loading recent anomalies...
                  </td>
                </tr>
              ) : anomalies.length === 0 ? (
                <tr>
                  <td colSpan={8} className="py-6 text-center text-slate-400">
                    No recent anomalies found.
                  </td>
                </tr>
              ) : (
                anomalies.map((anom) => (
                  <tr key={anom.id} className="hover:bg-slate-50/80 transition-colors">
                    <td className="py-2.5 px-3 font-medium text-slate-900">{anom.anomaly_date}</td>
                    <td className="py-2.5 px-3">{anom.product_name || `Product #${anom.product_id}`}</td>
                    <td className="py-2.5 px-3">{anom.branch_name || `Store #${anom.branch_id}`}</td>
                    <td className="py-2.5 px-3">
                      <span
                        className={`inline-block font-semibold px-2 py-0.5 rounded text-[10px] ${
                          anom.direction === "SPIKE"
                            ? "bg-amber-100 text-amber-800"
                            : "bg-blue-100 text-blue-800"
                        }`}
                      >
                        {anom.direction}
                      </span>
                    </td>
                    <td className="py-2.5 px-3 font-semibold">{formatNumber(anom.observed_quantity)}</td>
                    <td className="py-2.5 px-3 text-slate-500">{formatNumber(anom.expected_quantity)}</td>
                    <td className="py-2.5 px-3">
                      <span
                        className={`font-bold px-2 py-0.5 rounded text-[10px] ${
                          anom.severity === "CRITICAL"
                            ? "bg-rose-100 text-rose-700"
                            : anom.severity === "HIGH"
                            ? "bg-orange-100 text-orange-700"
                            : "bg-yellow-100 text-yellow-800"
                        }`}
                      >
                        {anom.severity} ({anom.anomaly_score.toFixed(2)})
                      </span>
                    </td>
                    <td className="py-2.5 px-3">
                      <span className="font-semibold text-slate-600">{anom.investigation_status}</span>
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
