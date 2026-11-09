"use client";

import React from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  LayoutDashboard,
  TrendingUp,
  LineChart,
  Boxes,
  AlertTriangle,
  Bot,
  Layers,
  Sparkles,
} from "lucide-react";
import { cn } from "@/lib/utils";

const navigation = [
  { name: "Executive Overview", href: "/", icon: LayoutDashboard },
  { name: "Sales Analytics", href: "/sales", icon: TrendingUp },
  { name: "Demand Forecasting", href: "/forecasting", icon: LineChart },
  { name: "Inventory Decision", href: "/inventory", icon: Boxes },
  { name: "Anomaly Explorer", href: "/anomalies", icon: AlertTriangle },
  { name: "AI Assistant", href: "/assistant", icon: Bot, highlight: true },
];

export const Sidebar: React.FC = () => {
  const pathname = usePathname();

  return (
    <aside className="fixed inset-y-0 left-0 z-40 flex w-64 flex-col border-r border-slate-200 bg-white">
      {/* Brand Header */}
      <div className="flex h-16 items-center gap-3 border-b border-slate-200 px-6">
        <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-sky-600 text-white shadow-sm">
          <Layers className="h-5 w-5" />
        </div>
        <div>
          <span className="font-bold text-slate-900 tracking-tight text-base">
            SmartDist<span className="text-sky-600">.AI</span>
          </span>
          <p className="text-[11px] font-medium text-slate-400">Retail & Supply Chain</p>
        </div>
      </div>

      {/* Navigation items */}
      <nav className="flex-1 space-y-1.5 px-3 py-4">
        {navigation.map((item) => {
          const isActive = pathname === item.href;
          const Icon = item.icon;
          return (
            <Link
              key={item.name}
              href={item.href}
              className={cn(
                "group flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-colors",
                isActive
                  ? "bg-sky-50 text-sky-700"
                  : "text-slate-600 hover:bg-slate-50 hover:text-slate-900",
                item.highlight && !isActive && "text-sky-600 font-semibold"
              )}
            >
              <Icon
                className={cn(
                  "h-5 w-5 transition-colors",
                  isActive
                    ? "text-sky-600"
                    : item.highlight
                    ? "text-sky-500"
                    : "text-slate-400 group-hover:text-slate-600"
                )}
              />
              <span className="flex-1">{item.name}</span>
              {item.highlight && (
                <span className="flex items-center gap-1 rounded-full bg-sky-100 px-2 py-0.5 text-[10px] font-semibold text-sky-700">
                  <Sparkles className="h-3 w-3" /> AI
                </span>
              )}
            </Link>
          );
        })}
      </nav>

      {/* System Status Footer */}
      <div className="border-t border-slate-200 p-4">
        <div className="rounded-lg bg-slate-50 p-3 text-xs text-slate-500">
          <div className="flex items-center justify-between font-semibold text-slate-700">
            <span>Environment</span>
            <span className="rounded bg-emerald-100 px-1.5 py-0.5 text-[10px] font-bold text-emerald-700">
              Active
            </span>
          </div>
          <p className="mt-1 text-[11px] text-slate-500">FastAPI :8035 • PG 16 :5435</p>
          <div className="mt-2 text-[10px] text-slate-400">Phase 4 Master Application</div>
        </div>
      </div>
    </aside>
  );
};

