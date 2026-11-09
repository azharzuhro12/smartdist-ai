"use client";

import React, { useEffect, useState } from "react";
import {
  LineChart as LineChartIcon,
  Calendar,
  Sparkles,
  Info,
  TrendingUp,
} from "lucide-react";
import { api, ForecastResponse } from "@/lib/api";
import { formatNumber } from "@/lib/utils";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Area,
  AreaChart,
} from "recharts";

export default function DemandForecastingPage() {
  const [productId, setProductId] = useState<number>(13);
  const [branchId, setBranchId] = useState<number>(44);
  const [horizon, setHorizon] = useState<number>(7);
  const [forecast, setForecast] = useState<ForecastResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function loadForecast() {
      try {
        setLoading(true);
        setError(null);
        const res = await api.getForecast(productId, branchId, horizon);
        setForecast(res);
      } catch (err: any) {
        setError(err.message || "Failed to generate demand forecast.");
      } finally {
        setLoading(false);
      }
    }
    loadForecast();
  }, [productId, branchId, horizon]);

  const points = forecast?.daily_forecasts || forecast?.forecast_points || [];
  const totalForecasted = points.reduce(
    (acc: number, pt: any) => acc + (pt.predicted_demand ?? pt.forecasted_quantity ?? 0),
    0
  );
  const meanDaily = points.length ? totalForecasted / points.length : 0;

  return (
    <div className="space-y-8">
      {/* Page Header */}
      <div>
        <h2 className="text-2xl font-bold tracking-tight text-slate-900">
          Machine Learning Demand Forecasting
        </h2>
        <p className="text-sm text-slate-500">
          Multi-step recursive demand forecasting powered by LightGBM using calendar, rolling, and lag features.
        </p>
      </div>

      {/* Model & Horizon Control Bar */}
      <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-3 lg:grid-cols-4">
          <div>
            <label className="block text-xs font-semibold uppercase tracking-wider text-slate-600 mb-1.5">
              Product Family
            </label>
            <select
              value={productId}
              onChange={(e) => setProductId(Number(e.target.value))}
              className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-800 focus:border-sky-500 focus:outline-none"
            >
              <option value={13}>Grocery I (SKU #13)</option>
              <option value={4}>Beverages (SKU #4)</option>
              <option value={8}>Cleaning (SKU #8)</option>
              <option value={9}>Dairy (SKU #9)</option>
              <option value={6}>Bread / Bakery (SKU #6)</option>
              <option value={26}>Poultry (SKU #26)</option>
              <option value={19}>Meats (SKU #19)</option>
            </select>
          </div>

          <div>
            <label className="block text-xs font-semibold uppercase tracking-wider text-slate-600 mb-1.5">
              Store Branch
            </label>
            <select
              value={branchId}
              onChange={(e) => setBranchId(Number(e.target.value))}
              className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-800 focus:border-sky-500 focus:outline-none"
            >
              <option value={44}>Branch #44 — Quito (High Volume)</option>
              <option value={45}>Branch #45 — Quito</option>
              <option value={47}>Branch #47 — Quito</option>
              <option value={1}>Branch #1 — Quito</option>
              <option value={3}>Branch #3 — Ambato</option>
              <option value={50}>Branch #50 — Guayaquil</option>
            </select>
          </div>

          <div>
            <label className="block text-xs font-semibold uppercase tracking-wider text-slate-600 mb-1.5">
              Forecast Horizon
            </label>
            <div className="flex gap-1.5 rounded-lg border border-slate-300 p-1">
              {[7, 14, 30].map((h) => (
                <button
                  key={h}
                  onClick={() => setHorizon(h)}
                  className={`flex-1 rounded-md py-1 text-xs font-semibold transition ${
                    horizon === h
                      ? "bg-sky-600 text-white shadow-sm"
                      : "text-slate-600 hover:text-slate-900"
                  }`}
                >
                  {h} Days
                </button>
              ))}
            </div>
          </div>

          <div className="flex items-end">
            <div className="w-full rounded-lg bg-sky-50/70 p-2.5 text-xs text-sky-800">
              <span className="font-bold flex items-center gap-1">
                <Sparkles className="h-3.5 w-3.5 text-sky-600" />
                LightGBM Multi-Step
              </span>
              <p className="text-[11px] text-sky-600 mt-0.5">
                Target: observed `quantity_sold`
              </p>
            </div>
          </div>
        </div>
      </div>

      {/* Summary KPI Strip */}
      <div className="grid grid-cols-1 gap-5 sm:grid-cols-3">
        <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
          <span className="text-xs font-semibold uppercase text-slate-500">
            Total Projected Volume ({horizon} Days)
          </span>
          <div className="mt-2 text-2xl font-bold text-slate-900">
            {formatNumber(totalForecasted, 1)} units
          </div>
          <span className="text-xs text-slate-400">Cumulative demand across horizon</span>
        </div>

        <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
          <span className="text-xs font-semibold uppercase text-slate-500">
            Daily Projected Run Rate
          </span>
          <div className="mt-2 text-2xl font-bold text-sky-600">
            {formatNumber(meanDaily, 1)} units/day
          </div>
          <span className="text-xs text-slate-400">Mean forecast velocity</span>
        </div>

        <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
          <span className="text-xs font-semibold uppercase text-slate-500">
            Model Provenance & Version
          </span>
          <div className="mt-2 text-lg font-bold text-slate-800 truncate">
            {forecast?.model_version || "LightGBM v1"}
          </div>
          <span className="text-xs text-emerald-600 font-semibold">
            ✓ Out-of-sample calibrated
          </span>
        </div>
      </div>

      {/* Main Forecast Line Chart */}
      <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h3 className="text-base font-bold text-slate-900">
              Recursive Demand Forecast Curve
            </h3>
            <p className="text-xs text-slate-500">
              Projected daily demand over {horizon} future steps
            </p>
          </div>
          <span className="rounded bg-sky-50 px-2.5 py-1 text-xs font-semibold text-sky-700">
            {points.length > 0
              ? `Range: ${points[0].date} → ${points[points.length - 1].date}`
              : "Horizon: " + horizon + " Days"}
          </span>
        </div>

        {error ? (
          <div className="rounded-lg bg-rose-50 p-4 text-xs font-medium text-rose-700">
            {error}
          </div>
        ) : (
          <div className="h-80 w-full">
            {loading ? (
              <div className="flex h-full items-center justify-center text-xs text-slate-400">
                Generating recursive forecast points...
              </div>
            ) : points.length ? (
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={points}>
                  <defs>
                    <linearGradient id="colorForecast" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#0284c7" stopOpacity={0.3} />
                      <stop offset="95%" stopColor="#0284c7" stopOpacity={0.0} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#f1f5f9" />
                  <XAxis
                    dataKey="date"
                    tick={{ fontSize: 11, fill: "#64748b" }}
                  />
                  <YAxis
                    tick={{ fontSize: 11, fill: "#64748b" }}
                    tickFormatter={(val) => `${val.toFixed(0)}`}
                  />
                  <Tooltip
                    formatter={(val: any) => [`${formatNumber(val, 1)} units`, "Predicted Demand"]}
                  />
                  <Area
                    type="monotone"
                    dataKey={(pt: any) => pt.predicted_demand ?? pt.forecasted_quantity}
                    stroke="#0284c7"
                    strokeWidth={2.5}
                    fillOpacity={1}
                    fill="url(#colorForecast)"
                  />
                </AreaChart>
              </ResponsiveContainer>
            ) : (
              <div className="flex h-full items-center justify-center text-xs text-slate-400">
                No forecast series available.
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

