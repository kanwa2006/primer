import Link from "next/link";

export default function SiteHeader() {
  return (
    <header className="border-b border-zinc-200 sticky top-0 z-10 bg-white/95 backdrop-blur-sm">
      <div className="max-w-5xl mx-auto px-6 h-14 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Link
            href="/"
            className="font-mono text-sm font-semibold text-zinc-900 tracking-tight hover:text-zinc-700 transition-colors duration-150"
          >
            PRIMER
          </Link>
        </div>

        <nav className="flex items-center gap-4">
          <Link
            href="/compare/"
            className="text-zinc-500 hover:text-zinc-700 text-xs font-mono transition-colors duration-150"
          >
            Compare
          </Link>
          <a
            href="https://github.com/kanwa2006/primer"
            target="_blank"
            rel="noopener noreferrer"
            className="text-zinc-500 hover:text-zinc-700 text-xs font-mono transition-colors duration-150"
            aria-label="PRIMER on GitHub"
          >
            GitHub
          </a>
        </nav>
      </div>
    </header>
  );
}
