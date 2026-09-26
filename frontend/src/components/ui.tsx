import type { ButtonHTMLAttributes, InputHTMLAttributes, ReactNode, TextareaHTMLAttributes } from "react";

type ButtonProps = ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: "primary" | "secondary" | "quiet";
};

export function Button({ className = "", variant = "primary", ...props }: ButtonProps) {
  const styles = {
    primary: "bg-[#8f1029] text-white hover:bg-[#700b20]",
    secondary: "border border-[#d8c6bc] bg-[#fffaf3] text-[#321d20] hover:border-[#8f1029]",
    quiet: "text-[#6f4548] hover:bg-[#f7e6df]",
  };
  return (
    <button
      className={`inline-flex min-h-11 items-center justify-center rounded-full px-5 text-sm font-semibold transition focus:outline-none focus:ring-2 focus:ring-[#8f1029] focus:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-55 ${styles[variant]} ${className}`}
      {...props}
    />
  );
}

export function Input({ className = "", ...props }: InputHTMLAttributes<HTMLInputElement>) {
  return <input className={`field ${className}`} {...props} />;
}

export function Textarea({ className = "", ...props }: TextareaHTMLAttributes<HTMLTextAreaElement>) {
  return <textarea className={`field min-h-28 resize-y ${className}`} {...props} />;
}

export function Card({ children, className = "" }: { children: ReactNode; className?: string }) {
  return <section className={`rounded-3xl border border-[#ead9cf] bg-[#fffdf9] p-6 shadow-[0_10px_30px_rgba(73,38,37,0.06)] ${className}`}>{children}</section>;
}

export function Badge({ children, tone = "neutral" }: { children: ReactNode; tone?: "neutral" | "warm" | "success" | "danger" }) {
  const styles = {
    neutral: "bg-[#f4ebe5] text-[#63474a]",
    warm: "bg-[#fff0b8] text-[#6d4a00]",
    success: "bg-[#dff0df] text-[#285f35]",
    danger: "bg-[#f7dce0] text-[#861a31]",
  };
  return <span className={`inline-flex rounded-full px-3 py-1 text-xs font-semibold capitalize ${styles[tone]}`}>{children}</span>;
}

export function StatusBadge({ status }: { status: string }) {
  const normalized = status.replaceAll("_", " ");
  const tone = status.includes("failed") || status.includes("rejected") ? "danger" : status.includes("approved") || status.includes("published") ? "success" : status.includes("pending") ? "warm" : "neutral";
  return <Badge tone={tone}>{normalized}</Badge>;
}

export function PageHeader({ eyebrow, title, children }: { eyebrow: string; title: string; children?: ReactNode }) {
  return <header className="flex flex-col justify-between gap-5 border-b border-[#ead9cf] pb-7 sm:flex-row sm:items-end"><div><p className="eyebrow">{eyebrow}</p><h1 className="mt-2 text-4xl text-[#321d20] sm:text-5xl">{title}</h1></div>{children}</header>;
}

export function LoadingState({ label = "Loading workspace…" }: { label?: string }) {
  return <div className="py-16 text-center text-sm text-[#77595a]"><span className="mr-2 inline-block size-2 animate-pulse rounded-full bg-[#a5213b]" />{label}</div>;
}

export function EmptyState({ title, detail, action }: { title: string; detail: string; action?: ReactNode }) {
  return <Card className="border-dashed bg-[#fff8e8] py-14 text-center"><h2 className="text-2xl text-[#321d20]">{title}</h2><p className="mx-auto mt-3 max-w-md text-[#77595a]">{detail}</p>{action && <div className="mt-6">{action}</div>}</Card>;
}
