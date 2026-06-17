"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import { motion, AnimatePresence, useReducedMotion } from "motion/react";
import { Menu, X } from "lucide-react";
import { ThemeToggle } from "@/components/ThemeToggle";
import { GitHubMark } from "@/components/GitHubMark";
import { Magnetic } from "@/components/Magnetic";
import { cn } from "@/lib/cn";

const NAV_LINKS = [
  { href: "/",              label: "Overview",     exact: true  },
  { href: "/compare/",     label: "Compare",      exact: false },
  { href: "/trends/",      label: "Trends",       exact: false },
  { href: "/methodology/", label: "Methodology",  exact: false },
  { href: "/score-guide/", label: "Score guide",  exact: false },
];

function isActive(pathname: string, href: string, exact: boolean) {
  return exact ? pathname === href : pathname.startsWith(href);
}

// The PRIMER caliper glyph — the signature instrument, scaled to a brand mark.
// A measurement track with engraved ticks and an indicator at the true reading.
function PrimerMark({ className }: { className?: string }) {
  return (
    <svg width="22" height="22" viewBox="0 0 22 22" fill="none" className={className} aria-hidden="true">
      <line x1="2" y1="11" x2="20" y2="11" stroke="currentColor" strokeWidth="1.25" strokeLinecap="round" />
      <line x1="4"  y1="7" x2="4"  y2="15" stroke="currentColor" strokeWidth="1" opacity=".55" />
      <line x1="8"  y1="8.5" x2="8"  y2="13.5" stroke="currentColor" strokeWidth="1" opacity=".4" />
      <line x1="16" y1="8.5" x2="16" y2="13.5" stroke="currentColor" strokeWidth="1" opacity=".4" />
      <line x1="18" y1="7" x2="18" y2="15" stroke="currentColor" strokeWidth="1" opacity=".55" />
      <circle cx="12.5" cy="11" r="2.4" fill="var(--accent-signal)" stroke="var(--surface-base)" strokeWidth="1.25" />
    </svg>
  );
}

const NAV_SPRING = { type: "spring", stiffness: 420, damping: 34, mass: 0.7 } as const;

function NavLink({
  href,
  label,
  active,
  highlighted,
  onHover,
}: {
  href: string;
  label: string;
  active: boolean;
  highlighted: boolean;
  onHover: () => void;
}) {
  return (
    <Link
      href={href}
      onPointerEnter={onHover}
      className={cn(
        "relative px-3.5 py-2 text-sm font-medium tracking-[-0.01em] rounded-lg transition-colors duration-200",
        active ? "text-[var(--text-primary)]" : "text-[var(--text-secondary)] hover:text-[var(--text-primary)]"
      )}
      aria-current={active ? "page" : undefined}
    >
      {/* Shared-element background — springs between items on hover/route change */}
      {highlighted && (
        <motion.span
          layoutId="nav-pill"
          className="absolute inset-0 z-0 rounded-lg bg-[var(--surface-raised)] border border-[var(--border-hairline)]"
          transition={NAV_SPRING}
        />
      )}
      <span className="relative z-10">{label}</span>
      {/* Active underline — accent, tracks the current route */}
      {active && (
        <motion.span
          layoutId="nav-underline"
          className="absolute inset-x-3 -bottom-0.5 h-px bg-[var(--accent-signal)] z-10"
          transition={NAV_SPRING}
        />
      )}
    </Link>
  );
}

export default function SiteHeader() {
  const pathname = usePathname();
  const reduce = useReducedMotion();
  const [scrolled, setScrolled] = useState(false);
  const [open, setOpen] = useState(false);
  const [hovered, setHovered] = useState<string | null>(null);

  // Scroll-driven compression: background + blur appear, height compresses.
  useEffect(() => {
    let raf = 0;
    const onScroll = () => {
      if (raf) return;
      raf = requestAnimationFrame(() => {
        setScrolled(window.scrollY > 8);
        raf = 0;
      });
    };
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  // Close the mobile sheet on navigation.
  useEffect(() => setOpen(false), [pathname]);

  return (
    <header
      className={cn(
        "sticky top-0 z-40 transition-[height,background-color,border-color,backdrop-filter] duration-300",
        "border-b",
        scrolled
          ? "border-[var(--border-hairline)] bg-[var(--surface-base)]/80 backdrop-blur-[18px]"
          : "border-transparent bg-[var(--surface-base)]/30 backdrop-blur-[6px]"
      )}
      style={{ backdropFilter: scrolled ? "blur(18px)" : "blur(6px)" }}
    >
      <div
        className={cn(
          "max-w-[1200px] mx-auto px-5 sm:px-6 flex items-center justify-between gap-4 transition-[height] duration-300",
          scrolled ? "h-[3.25rem] sm:h-14" : "h-16 sm:h-[4.25rem]"
        )}
      >
        {/* Wordmark + caliper mark */}
        <Magnetic strength={2}>
          <Link
            href="/"
            className="group flex items-center gap-2 text-[var(--text-primary)] shrink-0"
            aria-label="PRIMER — home"
          >
            <PrimerMark className="text-[var(--text-secondary)] transition-colors group-hover:text-[var(--text-primary)]" />
            <span className="text-[15px] font-semibold tracking-[-0.02em]">PRIMER</span>
          </Link>
        </Magnetic>

        {/* Desktop nav — shared-element pill follows hover, settles on active route */}
        <nav
          className="hidden md:flex items-center gap-0.5"
          aria-label="Primary navigation"
          onPointerLeave={() => setHovered(null)}
        >
          {NAV_LINKS.map((l) => {
            const active = isActive(pathname, l.href, l.exact);
            const highlighted = hovered ? hovered === l.href : active;
            return (
              <NavLink
                key={l.href}
                href={l.href}
                label={l.label}
                active={active}
                highlighted={highlighted}
                onHover={() => setHovered(l.href)}
              />
            );
          })}
        </nav>

        {/* Actions */}
        <div className="flex items-center gap-1.5">
          <ThemeToggle />
          <Magnetic strength={2}>
            <a
              href="https://github.com/kanwa2006/primer"
              target="_blank"
              rel="noopener noreferrer"
              className="w-9 h-9 rounded-md flex items-center justify-center text-[var(--text-secondary)] hover:text-[var(--text-primary)] hover:bg-[var(--surface-raised)] transition-colors duration-150"
              aria-label="PRIMER on GitHub"
            >
              <GitHubMark size={16} />
            </a>
          </Magnetic>
          {/* Mobile menu button */}
          <button
            onClick={() => setOpen((v) => !v)}
            className="md:hidden w-11 h-11 -mr-1 rounded-md flex items-center justify-center text-[var(--text-secondary)] hover:text-[var(--text-primary)] transition-colors"
            aria-label={open ? "Close menu" : "Open menu"}
            aria-expanded={open}
            aria-controls="mobile-nav"
          >
            {open ? <X size={20} strokeWidth={1.75} /> : <Menu size={20} strokeWidth={1.75} />}
          </button>
        </div>
      </div>

      {/* Mobile sheet */}
      <AnimatePresence>
        {open && (
          <motion.nav
            id="mobile-nav"
            className="md:hidden overflow-hidden border-t border-[var(--border-hairline)] bg-[var(--surface-base)]/95 backdrop-blur-[18px]"
            initial={reduce ? { opacity: 0 } : { height: 0, opacity: 0 }}
            animate={reduce ? { opacity: 1 } : { height: "auto", opacity: 1 }}
            exit={reduce ? { opacity: 0 } : { height: 0, opacity: 0 }}
            transition={{ duration: 0.24, ease: [0.16, 1, 0.3, 1] }}
            aria-label="Mobile navigation"
          >
            <div className="px-4 py-2 flex flex-col">
              {NAV_LINKS.map((l) => {
                const active = (l.exact ? pathname === l.href : pathname.startsWith(l.href));
                return (
                  <Link
                    key={l.href}
                    href={l.href}
                    className={cn(
                      "flex items-center min-h-[44px] px-2 rounded-md text-[15px] font-medium tracking-tight transition-colors",
                      active
                        ? "text-[var(--accent-signal)]"
                        : "text-[var(--text-secondary)] hover:text-[var(--text-primary)] hover:bg-[var(--surface-raised)]"
                    )}
                    aria-current={active ? "page" : undefined}
                  >
                    {l.label}
                  </Link>
                );
              })}
            </div>
          </motion.nav>
        )}
      </AnimatePresence>
    </header>
  );
}
