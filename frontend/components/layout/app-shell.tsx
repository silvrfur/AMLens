"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import type { FormEvent, ReactNode } from "react";
import { useQuery } from "@tanstack/react-query";
import { Activity, AlertCircle, Bell, BookOpen, ChevronLeft, ChevronRight, ClipboardList, FileUp, LayoutDashboard, Menu, Moon, Search, Settings, Shield, Sun, X } from "lucide-react";
import { api, appConfig } from "@/lib/api/client";

const navigation = [
  { label: "Dashboard", href: "/", icon: LayoutDashboard },
  { label: "Upload Data", href: "/upload", icon: FileUp },
  { label: "Alert Queue", href: "/alerts", icon: AlertCircle, count: "25" },
  { label: "Investigations", href: "/investigations", icon: ClipboardList },
  { label: "Knowledge Base", href: "/knowledge", icon: BookOpen },
  { label: "Audit Trail", href: "/audit", icon: Activity },
  { label: "Settings", href: "/settings", icon: Settings },
];

export function AppShell({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const [collapsed, setCollapsed] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);
  const [dark, setDark] = useState(false);
  const [search, setSearch] = useState("");
  const [userOpen, setUserOpen] = useState(false);
  const [notificationsOpen, setNotificationsOpen] = useState(false);
  const searchRef = useRef<HTMLInputElement>(null);
  const health = useQuery({ queryKey: ["health"], queryFn: api.getHealth, staleTime: 20_000, refetchInterval: 30_000 });
  const healthStates = health.data ? [health.data.backend, health.data.agent, health.data.rag, health.data.queue] : [];
  const healthClass = health.isError ? "status-offline" : healthStates.includes("offline") ? "status-offline" : healthStates.includes("degraded") ? "status-warning" : health.isPending ? "status-checking" : "status-healthy";
  const healthLabel = health.isError ? "Health status unavailable" : healthStates.includes("offline") ? "Service offline" : healthStates.includes("degraded") ? "Service attention required" : health.isPending ? "Checking services" : "All systems operational";
  const title = navigation.find((item) => item.href === pathname)?.label ?? (pathname.startsWith("/alerts/") ? "Alert Detail" : pathname.startsWith("/investigations/") ? "Investigation Review" : "AMLens");

  useEffect(() => {
    setDark(document.documentElement.classList.contains("dark"));
    const onKeyDown = (event: KeyboardEvent) => {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") {
        event.preventDefault();
        searchRef.current?.focus();
      }
    };
    const onThemeChange = (event: Event) => setDark(Boolean((event as CustomEvent<boolean>).detail));
    window.addEventListener("keydown", onKeyDown);
    window.addEventListener("amlens-theme-change", onThemeChange);
    return () => {
      window.removeEventListener("keydown", onKeyDown);
      window.removeEventListener("amlens-theme-change", onThemeChange);
    };
  }, []);

  function handleSearch(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const value = search.trim().toUpperCase();
    if (value.startsWith("ALT-")) router.push(`/alerts/${encodeURIComponent(value)}`);
    else if (value.startsWith("INV-")) router.push(`/investigations/${encodeURIComponent(value)}`);
    else router.push(`/alerts?search=${encodeURIComponent(search.trim())}`);
  }
  function toggleTheme() {
    const next = !document.documentElement.classList.contains("dark");
    setDark(next);
    document.documentElement.classList.toggle("dark", next);
    document.documentElement.classList.toggle("light", !next);
    window.dispatchEvent(new CustomEvent("amlens-theme-change", { detail: next }));
  }

  return <div className={`app-frame ${collapsed ? "is-collapsed" : ""}`}>
    <aside className={`app-sidebar ${mobileOpen ? "mobile-open" : ""}`} aria-label="Primary navigation">
      <div className="brand-row"><div className="brand-mark"><Shield aria-hidden="true" /></div>{!collapsed && <div className="brand-copy"><strong>AMLens</strong><span>COMPLIANCE WORKSPACE</span></div>}<button className="sidebar-collapse" aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"} onClick={() => setCollapsed(!collapsed)}><ChevronLeft aria-hidden="true" /></button></div>
      <div className="workspace-label">WORKSPACE</div>
      <nav className="nav-list">
        {navigation.map(({ label, href, icon: Icon, count }) => {
          const active = href === "/" ? pathname === "/" : pathname === href || pathname.startsWith(`${href}/`);
          return <Link key={href} href={href} onClick={() => setMobileOpen(false)} title={collapsed ? label : undefined} className={`nav-item ${active ? "active" : ""}`} aria-current={active ? "page" : undefined}>
            <Icon aria-hidden="true" /><span>{label}</span>{count && !collapsed && <small>{count}</small>}
          </Link>;
        })}
      </nav>
      <div className="sidebar-bottom"><div className="sidebar-status"><span className={`status-dot ${healthClass}`} />{!collapsed && <span>{healthLabel}</span>}</div>{!collapsed && <div className="sidebar-version">AMLens · v0.9.4</div>}</div>
    </aside>
    {mobileOpen && <button className="sidebar-backdrop" aria-label="Close navigation" onClick={() => setMobileOpen(false)} />}
    <div className="app-main">
      <header className="topbar">
        <div className="topbar-leading"><button className="mobile-menu" aria-label="Open navigation" onClick={() => setMobileOpen(true)}><Menu /></button><div className="breadcrumb"><span>AMLens</span><ChevronRight aria-hidden="true" /><strong>{title}</strong></div></div>
        <div className="topbar-actions">
          <form onSubmit={handleSearch} className="global-search" role="search"><Search aria-hidden="true" /><input ref={searchRef} aria-label="Search alerts or investigations" placeholder="Search alerts or investigations…" value={search} onChange={(event) => setSearch(event.target.value)} onKeyDown={(event) => { if (event.key === "Enter" && (event.nativeEvent.isComposing || event.keyCode === 229)) event.preventDefault(); }} /><kbd>⌘ K</kbd></form>
          <div className="env-badge"><span className="env-dot" />{appConfig.mocks ? "DEV · Mock data" : "LIVE API"}</div>
          <button className="icon-button theme-button" aria-label={dark ? "Switch to light mode" : "Switch to dark mode"} onClick={toggleTheme}>{dark ? <Sun /> : <Moon />}</button>
          <div className="notification-wrap"><button className="icon-button notification-button" aria-label="Notifications" aria-expanded={notificationsOpen} aria-controls="notification-popover" onClick={() => setNotificationsOpen((value) => !value)}><Bell /><i /></button>{notificationsOpen && <div className="notifications-popover" id="notification-popover" role="region" aria-label="Notifications"><strong>Queue attention</strong><p>25 alerts are available for analyst review.</p><Link href="/alerts" onClick={() => setNotificationsOpen(false)}>Open alert queue</Link></div>}</div>
          <div className="user-menu-wrap"><button className="user-menu" aria-expanded={userOpen} onClick={() => setUserOpen(!userOpen)}><span className="user-avatar">JM</span><span className="user-name">Jordan Miller<small>Demo Analyst</small></span><ChevronRight className="user-chevron" /></button>{userOpen && <div className="user-popover"><strong>Jordan Miller</strong><span>Analyst ID: ANL-2048</span><button onClick={() => { router.push("/settings"); setUserOpen(false); }}>Account settings</button></div>}</div>
        </div>
      </header>
      <div className="app-content">
        <div className="ai-draft-banner" role="note"><span className="banner-icon"><AlertCircle aria-hidden="true" /></span><strong>AI-Generated Draft — Requires Investigator Review</strong><span className="banner-divider" /><span>AI output is advisory only. Final decisions remain with the investigator.</span></div>
        <main id="main-content" className="page-content">{children}</main>
        <footer className="app-footer"><span>AMLens internal compliance tooling</span><span>All activity is recorded in the audit trail</span></footer>
      </div>
    </div>
  </div>;
}
