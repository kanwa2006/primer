import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";
import { ThemeProvider } from "@/components/ThemeProvider";
import SiteHeader from "@/components/SiteHeader";
import SiteFooter from "@/components/SiteFooter";
import { AuroraBg } from "@/components/AuroraBg";
import { CursorCompanion } from "@/components/CursorCompanion";

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

const _desc =
  "PRIMER answers one question with evidence: does this repo's CLAUDE.md make a coding agent measurably better, worse, or neither?";
const _ogImg = `${process.env.NEXT_PUBLIC_BASE_PATH ?? ""}/og-image.png`;

export const metadata: Metadata = {
  metadataBase: new URL(
    process.env.NEXT_PUBLIC_SITE_URL ?? "http://localhost:3000"
  ),
  title: "PRIMER — CLAUDE.md measurement",
  description: _desc,
  openGraph: {
    title: "PRIMER",
    description: _desc,
    type: "website",
    images: [_ogImg],
  },
  twitter: {
    card: "summary_large_image",
    title: "PRIMER",
    description: _desc,
    images: [_ogImg],
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
      <body className="bg-[var(--surface-base)] text-[var(--text-primary)] font-sans antialiased min-h-screen">
        <ThemeProvider
          attribute="class"
          defaultTheme="dark"
          enableSystem
          disableTransitionOnChange={false}
        >
          <AuroraBg />
          <CursorCompanion />
          <div className="relative z-10">
            <a
              href="#main-content"
              className="sr-only focus:not-sr-only focus:fixed focus:top-3 focus:left-3 focus:z-50 focus:px-4 focus:py-2 focus:rounded-md focus:bg-[var(--surface-raised)] focus:text-[var(--text-primary)] focus:border focus:border-[var(--accent-signal)] focus:shadow-card focus:outline-none text-sm font-medium"
            >
              Skip to main content
            </a>
            <SiteHeader />
            <main id="main-content" className="min-h-[calc(100vh-3.5rem)]">
              {children}
            </main>
            <SiteFooter />
          </div>
        </ThemeProvider>
      </body>
    </html>
  );
}
