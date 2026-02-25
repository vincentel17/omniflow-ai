import type { HTMLAttributes, InputHTMLAttributes, ReactNode, SelectHTMLAttributes, TextareaHTMLAttributes } from "react";

import { cn } from "../../lib/cn";

export function Button({ className, ...props }: React.ButtonHTMLAttributes<HTMLButtonElement>) {
  return (
    <button
      className={cn(
        "focus-ring inline-flex items-center justify-center gap-2 rounded-2xl border border-transparent bg-[rgb(var(--primary))] px-4 py-2 text-sm font-semibold text-[rgb(var(--primary-foreground))] transition hover:brightness-95 disabled:cursor-not-allowed disabled:opacity-60",
        className
      )}
      {...props}
    />
  );
}

export function ButtonGhost({ className, ...props }: React.ButtonHTMLAttributes<HTMLButtonElement>) {
  return (
    <button
      className={cn(
        "focus-ring inline-flex items-center justify-center gap-2 rounded-2xl border border-[rgb(var(--border))] bg-transparent px-3 py-2 text-sm text-[rgb(var(--foreground))] transition hover:bg-[rgb(var(--muted))]",
        className
      )}
      {...props}
    />
  );
}

export function Card({ className, ...props }: HTMLAttributes<HTMLDivElement>) {
  return <div className={cn("surface-card", className)} {...props} />;
}

export function CardHeader({ className, ...props }: HTMLAttributes<HTMLDivElement>) {
  return <div className={cn("border-b border-[rgb(var(--border))] p-4", className)} {...props} />;
}

export function CardTitle({ className, ...props }: HTMLAttributes<HTMLHeadingElement>) {
  return <h2 className={cn("text-base font-semibold", className)} {...props} />;
}

export function CardContent({ className, ...props }: HTMLAttributes<HTMLDivElement>) {
  return <div className={cn("p-4", className)} {...props} />;
}

export function Badge({ className, tone = "neutral", children }: { className?: string; tone?: "neutral" | "success" | "warn" | "danger" | "info"; children: ReactNode }) {
  const toneClass =
    tone === "success"
      ? "bg-emerald-500/15 text-emerald-300"
      : tone === "warn"
        ? "bg-amber-400/20 text-amber-700 dark:text-amber-200"
        : tone === "danger"
          ? "bg-rose-500/15 text-rose-300"
          : tone === "info"
            ? "bg-[rgb(var(--accent-teal))]/20 text-teal-800 dark:text-teal-200"
            : "bg-[rgb(var(--muted))] text-[rgb(var(--muted-foreground))]";

  return <span className={cn("inline-flex items-center rounded-full px-2.5 py-1 text-xs font-medium", toneClass, className)}>{children}</span>;
}

export function Input({ className, ...props }: InputHTMLAttributes<HTMLInputElement>) {
  return <input className={cn("focus-ring w-full rounded-xl border border-[rgb(var(--border))] bg-[rgb(var(--card))] px-3 py-2 text-sm", className)} {...props} />;
}

export function Textarea({ className, ...props }: TextareaHTMLAttributes<HTMLTextAreaElement>) {
  return <textarea className={cn("focus-ring w-full rounded-xl border border-[rgb(var(--border))] bg-[rgb(var(--card))] px-3 py-2 text-sm", className)} {...props} />;
}

export function Select({ className, ...props }: SelectHTMLAttributes<HTMLSelectElement>) {
  return <select className={cn("focus-ring w-full rounded-xl border border-[rgb(var(--border))] bg-[rgb(var(--card))] px-3 py-2 text-sm", className)} {...props} />;
}

export function Checkbox({ className, ...props }: InputHTMLAttributes<HTMLInputElement>) {
  return <input className={cn("focus-ring h-4 w-4 rounded border border-[rgb(var(--border))]", className)} type="checkbox" {...props} />;
}

export function DataTable({ className, ...props }: HTMLAttributes<HTMLTableElement>) {
  return <table className={cn("table-base", className)} {...props} />;
}

export function Skeleton({ className }: { className?: string }) {
  return <div className={cn("animate-pulse rounded-xl bg-[rgb(var(--muted))]", className)} />;
}

export function EmptyState({ title, description, action }: { title: string; description: string; action?: ReactNode }) {
  return (
    <div className="surface-card p-8 text-center">
      <p className="text-base font-semibold">{title}</p>
      <p className="mt-2 text-sm text-[rgb(var(--muted-foreground))]">{description}</p>
      {action ? <div className="mt-4">{action}</div> : null}
    </div>
  );
}

export function Pagination({ page, hasNext, onPrev, onNext }: { page: number; hasNext: boolean; onPrev: () => void; onNext: () => void }) {
  return (
    <div className="mt-4 flex items-center justify-between">
      <p className="text-sm text-[rgb(var(--muted-foreground))]">Page {page}</p>
      <div className="flex gap-2">
        <ButtonGhost disabled={page <= 1} onClick={onPrev} type="button">
          Previous
        </ButtonGhost>
        <ButtonGhost disabled={!hasNext} onClick={onNext} type="button">
          Next
        </ButtonGhost>
      </div>
    </div>
  );
}
