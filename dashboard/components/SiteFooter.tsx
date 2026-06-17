import Link from "next/link";
import { GitHubMark } from "@/components/GitHubMark";

// Footer with thesis, secondary nav, and build/commit stamp (§6, §M7)
export default function SiteFooter() {
  return (
    <footer className="border-t border-[var(--border-hairline)] mt-16">
      <div className="max-w-[1200px] mx-auto px-6 py-6 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
        {/* Thesis */}
        <span className="t-body text-[var(--text-tertiary)]">
          <span className="font-semibold text-[var(--text-secondary)]">PRIMER</span> — Every context-file tool generates. PRIMER measures.
        </span>

        {/* Footer links */}
        <nav className="flex flex-wrap items-center gap-x-4 gap-y-1" aria-label="Footer navigation">
          {[
            { href: "/methodology/", label: "Methodology" },
            { href: "/score-guide/", label: "Score guide" },
            { href: "/export/",      label: "Export"      },
          ].map(({ href, label }) => (
            <Link
              key={href}
              href={href}
              className="text-[13px] font-medium text-[var(--text-tertiary)] hover:text-[var(--text-secondary)] transition-colors duration-150"
            >
              {label}
            </Link>
          ))}
          <a
            href="https://github.com/kanwa2006/primer"
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-1.5 text-[13px] font-medium text-[var(--text-tertiary)] hover:text-[var(--text-secondary)] transition-colors duration-150"
            aria-label="PRIMER on GitHub"
          >
            <GitHubMark size={13} /> GitHub
          </a>
        </nav>
      </div>
    </footer>
  );
}
