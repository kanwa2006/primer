import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";
import SiteHeader from "@/components/SiteHeader";
import SiteFooter from "@/components/SiteFooter";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
  display: "swap",
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
  display: "swap",
});

export const metadata: Metadata = {
  title: "PRIMER — context-file measurement",
  description:
    "PRIMER measures whether this repo's AI-agent context file improves coding-agent success, under controlled conditions.",
  openGraph: {
    title: "PRIMER",
    description:
      "PRIMER measures whether this repo's AI-agent context file improves coding-agent success, under controlled conditions.",
    type: "website",
  },
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html
      lang="en"
      className={`${geistSans.variable} ${geistMono.variable}`}
      suppressHydrationWarning
      style={{ viewTransitionName: "root" } as React.CSSProperties}
    >
      <body className="bg-white text-zinc-900 font-sans antialiased">
        <SiteHeader />
        <div className="border-b border-zinc-200 bg-zinc-50">
          <p className="max-w-5xl mx-auto px-6 py-2 text-xs text-zinc-500 leading-relaxed">
            {"PRIMER measures whether this repo's AI-agent context file improves coding-agent success, under controlled conditions."}
          </p>
        </div>
        {children}
        <SiteFooter />
      </body>
    </html>
  );
}
