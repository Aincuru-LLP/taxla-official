import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";
import { TooltipProvider } from "@/components/ui/tooltip";
import Sidebar from "@/components/Sidebar";
import { BootAuth } from "@/components/BootAuth";
import { QueryProvider } from "@/components/QueryProvider";

const inter = Inter({
  variable: "--font-inter",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "TAXLA Operations — MSME & Udyam Platform",
  description: "Internal Case Management & Udyam Registration Operations",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body
        className={`${inter.variable} font-sans antialiased min-h-screen bg-slate-50 text-slate-900 overflow-hidden`}
      >
        <TooltipProvider>
          <QueryProvider>
            {/* Hydrate the Zustand authStore from the HttpOnly refresh cookie */}
            <BootAuth />
            <div className="flex h-screen overflow-hidden">
              {/* Sidebar automatically hides on /login and /form/* */}
              <Sidebar />
              <main className="flex-1 overflow-auto bg-slate-50">{children}</main>
            </div>
          </QueryProvider>
        </TooltipProvider>
      </body>
    </html>
  );
}