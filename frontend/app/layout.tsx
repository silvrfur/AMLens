import type { Metadata, Viewport } from "next";
import { Providers } from "@/components/providers";
import { AppShell } from "@/components/layout/app-shell";
import "./globals.css";

export const metadata: Metadata = {
  title: { default: "AMLens | Compliance Workspace", template: "%s | AMLens" },
  description: "An investigator-led workspace for reviewing transaction monitoring alerts and AI-generated investigation drafts.",
  applicationName: "AMLens",
  generator: "v0.app",
};
export const viewport: Viewport = { colorScheme: "light dark", themeColor: [{ media: "(prefers-color-scheme: light)", color: "#f6f8fb" }, { media: "(prefers-color-scheme: dark)", color: "#101923" }], width: "device-width", initialScale: 1 };

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="en" suppressHydrationWarning><body className="antialiased"><Providers><AppShell>{children}</AppShell></Providers></body></html>;
}
