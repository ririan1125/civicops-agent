import React from "react";
import { BarChart3, Bot, FileSearch, ListChecks, Route, Search } from "lucide-react";
import { AgentRun } from "./pages/AgentRun";
import { Dashboard } from "./pages/Dashboard";
import { Evaluations } from "./pages/Evaluations";
import { RAGAssistant } from "./pages/RAGAssistant";
import { SQLAgent } from "./pages/SQLAgent";
import { Traces } from "./pages/Traces";

const tabs = [
  { id: "dashboard", label: "Dashboard", icon: BarChart3, view: <Dashboard /> },
  { id: "agent", label: "Agent Run", icon: Bot, view: <AgentRun /> },
  { id: "sql", label: "SQL Tool", icon: Search, view: <SQLAgent /> },
  { id: "rag", label: "Hybrid RAG", icon: FileSearch, view: <RAGAssistant /> },
  { id: "traces", label: "Traces", icon: Route, view: <Traces /> },
  { id: "evals", label: "Evals", icon: ListChecks, view: <Evaluations /> }
];

export function App() {
  const [active, setActive] = React.useState("dashboard");
  const current = tabs.find((tab) => tab.id === active) ?? tabs[0];

  return (
    <div className="app">
      <aside className="sidebar">
        <div className="brand">
          <span className="brand-mark">CO</span>
          <div>
            <strong>CivicOps</strong>
            <small>Agent Console</small>
          </div>
        </div>
        <nav>
          {tabs.map((tab) => {
            const Icon = tab.icon;
            return (
              <button className={active === tab.id ? "active" : ""} key={tab.id} onClick={() => setActive(tab.id)} title={tab.label}>
                <Icon size={17} /> {tab.label}
              </button>
            );
          })}
        </nav>
      </aside>
      {current.view}
    </div>
  );
}
