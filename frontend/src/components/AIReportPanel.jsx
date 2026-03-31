import React from 'react';
import { Zap, Activity, ShieldCheck, CreditCard } from 'lucide-react';

const AIReportPanel = ({ income = 50000, totalSpent = 15000, topCategory = "Food & Dining" }) => {

  // Logic for bullet points (Max 2 lines, no markdown, simple text)
  const behaviorInsights = [
    "Ultra-low burn rate: You've spent only 30% of your income.",
    `Essential focus: Most of your spending is on ${topCategory}.`
  ];

  const savingsTips = [
    "Increase your savings to 20% of income this month.",
    "Consider moving your excess funds to a High-Yield account."
  ];

  return (
    <div className="w-[400px] h-screen max-h-screen overflow-y-auto p-5 space-y-5 bg-[#0f172a] border-l border-slate-800 custom-scrollbar shadow-2xl text-slate-200">
      
      {/* ── HEADER ── */}
      <div className="flex justify-between items-center border-b border-slate-700 pb-4">
        <div className="flex items-center gap-3">
          <div className="p-2 bg-indigo-500/20 rounded-lg">
            <Zap className="w-5 h-5 text-indigo-400" />
          </div>
          <div>
            <h2 className="text-lg font-semibold tracking-tight text-white">AI Spending Report</h2>
            <p className="text-xs text-gray-400">March Insights</p>
          </div>
        </div>
        <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-emerald-500/10 border border-emerald-500/20">
          <div className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse" />
          <span className="text-[10px] font-bold text-emerald-500">LIVE</span>
        </div>
      </div>

      {/* ── A. MONTHLY SNAPSHOT ── */}
      <div className="bg-[#1e293b] rounded-xl p-4 shadow-sm border border-slate-700">
        <div className="flex items-center gap-2 mb-4">
          <Activity className="w-4 h-4 text-gray-400" />
          <h3 className="text-sm font-semibold text-gray-300">Monthly Snapshot</h3>
        </div>
        <div className="flex justify-between items-center">
          <div>
            <p className="text-sm text-gray-400 mb-1">Income</p>
            <p className="text-xl font-bold text-emerald-400">₹{income.toLocaleString()}</p>
          </div>
          <div className="text-right">
            <p className="text-sm text-gray-400 mb-1">Spent</p>
            <p className="text-xl font-bold text-orange-400">₹{totalSpent.toLocaleString()}</p>
          </div>
        </div>
      </div>

      {/* ── B. BEHAVIOR ANALYSIS ── */}
      <div className="bg-[#1e293b] rounded-xl p-4 shadow-sm border border-slate-700">
        <div className="flex items-center gap-2 mb-4">
          <ShieldCheck className="w-4 h-4 text-gray-400" />
          <h3 className="text-sm font-semibold text-gray-300">Behavior Analysis</h3>
        </div>
        <ul className="space-y-3">
          {behaviorInsights.map((insight, idx) => (
            <li key={idx} className="flex items-start gap-2">
              <span className="w-1.5 h-1.5 rounded-full bg-blue-400 mt-2 flex-shrink-0" />
              <p className="text-sm text-gray-300 leading-relaxed">{insight}</p>
            </li>
          ))}
        </ul>
      </div>

      {/* ── C. SAVINGS ADVICE ── */}
      <div className="bg-[#1e293b] rounded-xl p-4 shadow-sm border border-slate-700">
        <div className="flex items-center gap-2 mb-4">
          <CreditCard className="w-4 h-4 text-gray-400" />
          <h3 className="text-sm font-semibold text-gray-300">Savings Advice</h3>
        </div>
        <ul className="space-y-3">
          {savingsTips.map((tip, idx) => (
            <li key={idx} className="flex items-start gap-2">
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 mt-2 flex-shrink-0" />
              <p className="text-sm text-gray-300 leading-relaxed">{tip}</p>
            </li>
          ))}
        </ul>
      </div>

      <style>{`
        .custom-scrollbar::-webkit-scrollbar { width: 4px; }
        .custom-scrollbar::-webkit-scrollbar-track { background: transparent; }
        .custom-scrollbar::-webkit-scrollbar-thumb { background: #334155; border-radius: 10px; }
        .custom-scrollbar { scroll-behavior: smooth; }
      `}</style>

    </div>
  );
};

export default AIReportPanel;
