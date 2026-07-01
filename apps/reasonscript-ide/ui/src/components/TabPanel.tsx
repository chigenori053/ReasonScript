import { useEffect, useState, type ReactNode } from "react";

interface Tab {
  id: string;
  label: string;
  content: ReactNode;
}

interface Props {
  tabs: Tab[];
  defaultTab?: string;
  activeTab?: string;
  onActiveTabChange?: (tabId: string) => void;
}

export default function TabPanel({ tabs, defaultTab, activeTab, onActiveTabChange }: Props) {
  const [internalActive, setInternalActive] = useState(defaultTab ?? tabs[0]?.id ?? "");
  const active = activeTab ?? internalActive;
  const activeExists = tabs.some((t) => t.id === active);
  const resolvedActive = activeExists ? active : tabs[0]?.id ?? "";

  useEffect(() => {
    if (!activeExists && tabs[0]?.id && activeTab == null) {
      setInternalActive(tabs[0].id);
    }
  }, [activeExists, activeTab, tabs]);

  const setActive = (tabId: string) => {
    if (activeTab == null) {
      setInternalActive(tabId);
    }
    onActiveTabChange?.(tabId);
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100%" }}>
      <div
        style={{
          display: "flex",
          borderBottom: "1px solid #1f2937",
          background: "#0f172a",
          flexShrink: 0,
        }}
      >
        {tabs.map((t) => (
          <button
            key={t.id}
            onClick={() => setActive(t.id)}
            style={{
              padding: "6px 14px",
              fontSize: 12,
              background: "transparent",
              border: "none",
              borderBottom: resolvedActive === t.id ? "2px solid #3b82f6" : "2px solid transparent",
              color: resolvedActive === t.id ? "#e5e7eb" : "#6b7280",
              cursor: "pointer",
              whiteSpace: "nowrap",
            }}
          >
            {t.label}
          </button>
        ))}
      </div>
      <div style={{ flex: 1, overflow: "hidden" }}>
        {tabs.find((t) => t.id === resolvedActive)?.content}
      </div>
    </div>
  );
}
