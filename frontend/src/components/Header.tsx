"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import { api } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
import { Activity, Database, CheckCircle2, AlertCircle, LogOut, User } from "lucide-react";

export const Header: React.FC = () => {
  const [isHealthy, setIsHealthy] = useState<boolean | null>(null);
  const { user, logout } = useAuth();

  useEffect(() => {
    api
      .getHealth()
      .then((res) => setIsHealthy(res.status === "healthy"))
      .catch(() => setIsHealthy(false));
  }, []);

  const getRoleBadge = (role: string) => {
    switch (role) {
      case "ADMIN":
        return "bg-purple-100 text-purple-700 border-purple-200";
      case "ANALYST":
        return "bg-sky-100 text-sky-700 border-sky-200";
      default:
        return "bg-slate-100 text-slate-700 border-slate-200";
    }
  };

  return (
    <header className="sticky top-0 z-30 flex h-16 w-full items-center justify-between border-b border-slate-200 bg-white/95 px-8 backdrop-blur-sm">
      <div className="flex items-center gap-3">
        <h1 className="text-lg font-bold text-slate-800">
          SmartDist AI Management Portal
        </h1>
        <span className="hidden sm:inline-block rounded-md bg-slate-100 px-2.5 py-1 text-xs font-semibold text-slate-600">
          54 Stores • 33 Families • 2013 Public Dataset
        </span>
      </div>

      <div className="flex items-center gap-4">
        {/* Backend health status badge */}
        <div className="flex items-center gap-2 rounded-full border border-slate-200 bg-slate-50 px-3 py-1 text-xs font-medium text-slate-700">
          <Activity className="h-3.5 w-3.5 text-sky-500" />
          <span>Backend API:</span>
          {isHealthy === null ? (
            <span className="text-slate-400">Checking...</span>
          ) : isHealthy ? (
            <span className="flex items-center gap-1 text-emerald-600 font-semibold">
              <span className="h-2 w-2 rounded-full bg-emerald-500 animate-pulse" />
              Connected
            </span>
          ) : (
            <span className="flex items-center gap-1 text-rose-500 font-semibold">
              <AlertCircle className="h-3.5 w-3.5" />
              Disconnected
            </span>
          )}
        </div>

        {/* User profile & RBAC role badge */}
        {user ? (
          <div className="flex items-center gap-3 border-l border-slate-200 pl-4">
            <div className="flex items-center gap-2">
              <div className="flex h-8 w-8 items-center justify-center rounded-full bg-indigo-600 text-xs font-bold text-white uppercase">
                {user.username.slice(0, 2)}
              </div>
              <div className="hidden sm:flex flex-col text-left">
                <span className="text-xs font-bold text-slate-800 leading-tight">
                  {user.username}
                </span>
                <span className={`inline-block text-[10px] font-semibold border rounded px-1.5 py-0.2 mt-0.5 ${getRoleBadge(user.role)}`}>
                  {user.role}
                </span>
              </div>
            </div>
            <button
              onClick={logout}
              title="Sign Out"
              className="rounded-lg p-1.5 text-slate-400 hover:bg-slate-100 hover:text-slate-700 transition-colors"
            >
              <LogOut className="h-4 w-4" />
            </button>
          </div>
        ) : (
          <Link
            href="/login"
            className="flex items-center gap-1.5 rounded-lg bg-indigo-600 px-3.5 py-1.5 text-xs font-semibold text-white shadow-sm hover:bg-indigo-700 transition-colors"
          >
            <User className="h-3.5 w-3.5" />
            Sign In
          </Link>
        )}
      </div>
    </header>
  );
};

