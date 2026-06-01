export default function SiteFooter() {
  return (
    <footer className="border-t border-zinc-200 mt-16">
      <div className="max-w-5xl mx-auto px-6 py-6 flex items-center justify-between">
        <span className="text-zinc-500 text-xs font-mono">
          PRIMER — Every context-file tool generates. PRIMER measures.
        </span>
        <a
          href="https://github.com/kanwa2006/primer"
          target="_blank"
          rel="noopener noreferrer"
          className="text-zinc-500 hover:text-zinc-700 text-xs font-mono transition-colors duration-150"
          aria-label="PRIMER on GitHub"
        >
          GitHub
        </a>
      </div>
    </footer>
  );
}
