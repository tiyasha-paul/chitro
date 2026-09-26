import React from 'react';

// --- Button ---
type ButtonProps = React.ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: 'primary' | 'secondary' | 'quiet' | 'destructive' | 'outline';
  isLoading?: boolean;
  loading?: boolean;
  size?: 'sm' | 'md' | 'lg' | string;
  asChild?: boolean;
};

export const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className = '', variant = 'primary', isLoading, loading, size, asChild, children, disabled, ...props }, ref) => {
    const isSpinnerLoading = isLoading ?? loading ?? false;
    let baseStyles = 'inline-flex items-center justify-center rounded-lg font-bold text-sm px-4 py-2 transition-colors disabled:opacity-50 disabled:pointer-events-none';
    if (size === 'sm') {
      baseStyles = 'inline-flex items-center justify-center rounded-md font-bold text-xs px-3 py-1.5 transition-colors disabled:opacity-50 disabled:pointer-events-none';
    } else if (size === 'lg') {
      baseStyles = 'inline-flex items-center justify-center rounded-xl font-bold text-base px-6 py-3 transition-colors disabled:opacity-50 disabled:pointer-events-none';
    }

    let variantStyles = '';
    if (variant === 'primary') {
      variantStyles = 'bg-[var(--accent)] text-white hover:bg-[var(--accent-hover)]';
    } else if (variant === 'secondary') {
      variantStyles = 'bg-[var(--surface-raised)] border border-[var(--border-strong)] text-[var(--text-primary)] hover:bg-[var(--surface-highlight)]';
    } else if (variant === 'outline') {
      variantStyles = 'bg-transparent border border-[var(--border-strong)] text-[var(--text-primary)] hover:bg-[var(--surface-highlight)]';
    } else if (variant === 'quiet') {
      variantStyles = 'bg-transparent text-[var(--text-secondary)] hover:text-[var(--text-primary)] hover:bg-[var(--accent-light)]';
    } else if (variant === 'destructive') {
      variantStyles = 'bg-[var(--danger)] text-white hover:bg-[var(--danger-bg)] hover:text-[var(--danger)] border border-[var(--danger)]';
    }

    const combinedClassName = `${baseStyles} ${variantStyles} ${className}`.trim();

    if (asChild && React.isValidElement(children)) {
      const child = children as React.ReactElement<{ className?: string }>;
      return React.cloneElement(child, {
        className: `${combinedClassName} ${child.props.className ?? ''}`.trim(),
        ...props,
      });
    }

    return (
      <button
        ref={ref}
        className={combinedClassName}
        disabled={disabled || isSpinnerLoading}
        {...props}
      >
        {isSpinnerLoading && (
          <svg className="animate-spin -ml-1 mr-2 h-4 w-4" fill="none" viewBox="0 0 24 24">
            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
          </svg>
        )}
        {children}
      </button>
    );
  }
);
Button.displayName = 'Button';

// --- Input ---
type InputProps = React.InputHTMLAttributes<HTMLInputElement>;
export const Input = React.forwardRef<HTMLInputElement, InputProps>(
  ({ className = '', ...props }, ref) => {
    return (
      <input ref={ref} className={`field ${className}`} {...props} />
    );
  }
);
Input.displayName = 'Input';

// --- Textarea ---
type TextareaProps = React.TextareaHTMLAttributes<HTMLTextAreaElement>;
export const Textarea = React.forwardRef<HTMLTextAreaElement, TextareaProps>(
  ({ className = '', ...props }, ref) => {
    return (
      <textarea ref={ref} className={`field min-h-[100px] ${className}`} {...props} />
    );
  }
);
Textarea.displayName = 'Textarea';

// --- Card ---
type CardProps = React.HTMLAttributes<HTMLDivElement>;
export const Card = React.forwardRef<HTMLDivElement, CardProps>(
  ({ className = '', ...props }, ref) => {
    return (
      <div
        ref={ref}
        className={`bg-[var(--surface-raised)] border border-[var(--border)] rounded-xl shadow-sm ${className}`}
        {...props}
      />
    );
  }
);
Card.displayName = 'Card';

// --- Badge ---
type BadgeProps = React.HTMLAttributes<HTMLSpanElement> & {
  variant?: 'default' | 'secondary' | 'success' | 'warning' | 'danger' | string;
  tone?: 'default' | 'secondary' | 'success' | 'warning' | 'danger' | string;
};
export const Badge = ({ className = '', variant, tone, children, ...props }: BadgeProps) => {
  const resolved = tone ?? variant ?? 'default';
  let styles = 'inline-flex items-center px-2 py-0.5 rounded-md text-xs font-semibold';

  if (resolved === 'success') {
    styles += ' bg-[var(--success-bg)] text-[var(--success)]';
  } else if (resolved === 'warning') {
    styles += ' bg-[var(--warning-bg)] text-[var(--warning-text)]';
  } else if (resolved === 'danger') {
    styles += ' bg-[var(--danger-bg)] text-[var(--danger)]';
  } else {
    styles += ' bg-[var(--border)] text-[var(--text-secondary)]';
  }

  return <span className={`${styles} ${className}`.trim()} {...props}>{children}</span>;
};

// --- StatusBadge ---
export type StatusBadgeProps = {
  status: string;
  className?: string;
};
export const StatusBadge = ({ status, className = '' }: StatusBadgeProps) => {
  let label = status.replace(/_/g, ' ');
  let colorClass = 'border-l-gray-400 bg-gray-50';
  let dotClass = 'bg-gray-400';
  let textClass = 'text-gray-700';

  switch (status.toLowerCase()) {
    case 'draft':
      colorClass = 'border-l-gray-400 bg-[var(--surface)] border border-[var(--border)]';
      dotClass = 'bg-gray-400';
      textClass = 'text-[var(--text-secondary)]';
      break;
    case 'generated':
    case 'validated':
      colorClass = 'border-l-blue-500 bg-blue-50 border border-blue-100';
      dotClass = 'bg-blue-500';
      textClass = 'text-blue-800';
      break;
    case 'pending_approval':
      label = 'Needs review';
      colorClass = 'border-l-amber-500 bg-[var(--warning-bg)] border border-amber-200';
      dotClass = 'bg-amber-500';
      textClass = 'text-[var(--warning-text)]';
      break;
    case 'approved':
      colorClass = 'border-l-[var(--success)] bg-[var(--success-bg)] border border-green-200';
      dotClass = 'bg-[var(--success)]';
      textClass = 'text-[var(--success)]';
      break;
    case 'rejected':
      label = 'Needs changes';
      colorClass = 'border-l-[var(--danger)] bg-[var(--danger-bg)] border border-red-200';
      dotClass = 'bg-[var(--danger)]';
      textClass = 'text-[var(--danger)]';
      break;
    case 'validation_failed':
      label = 'Validation failed';
      colorClass = 'border-l-[var(--danger)] bg-[var(--danger-bg)] border border-red-200';
      dotClass = 'bg-[var(--danger)]';
      textClass = 'text-[var(--danger)]';
      break;
    case 'scheduled':
      colorClass = 'border-l-purple-500 bg-purple-50 border border-purple-200';
      dotClass = 'bg-purple-500';
      textClass = 'text-purple-800';
      break;
    case 'published':
      colorClass = 'border-l-[var(--success)] bg-[var(--success-bg)] border border-green-200';
      dotClass = 'bg-[var(--success)]';
      textClass = 'text-[var(--success)]';
      break;
    default:
      label = status;
  }

  return (
    <span className={`inline-flex items-center gap-1.5 px-2.5 py-1 text-xs font-semibold border-l-4 rounded-r-md ${colorClass} ${textClass} ${className}`}>
      <span className={`w-1.5 h-1.5 rounded-full ${dotClass}`}></span>
      <span className="capitalize">{label}</span>
    </span>
  );
};

// --- PageHeader ---
type PageHeaderProps = {
  title: string;
  description?: string;
  eyebrow?: string;
  action?: React.ReactNode;
  children?: React.ReactNode;
  className?: string;
};
export const PageHeader = ({ title, description, eyebrow, action, children, className = '' }: PageHeaderProps) => {
  const actions = action || children;
  return (
    <div className={`mb-8 flex flex-col sm:flex-row sm:items-end justify-between gap-4 ${className}`}>
      <div>
        {eyebrow && <div className="eyebrow mb-2">{eyebrow}</div>}
        <h1 className="text-3xl sm:text-4xl font-serif font-bold text-[var(--foreground)]">{title}</h1>
        {description && <p className="mt-2 text-[var(--text-secondary)]">{description}</p>}
      </div>
      {actions && <div className="flex items-center gap-3">{action}{children}</div>}
    </div>
  );
};

// --- LoadingState ---
type LoadingStateProps = {
  message?: string;
  label?: string;
  text?: string;
  className?: string;
};
export const LoadingState = ({ message, label, text, className = '' }: LoadingStateProps) => {
  const displayMessage = message ?? label ?? text ?? 'Loading...';
  return (
    <div className={`flex flex-col items-center justify-center p-12 text-center ${className}`}>
      <svg className="animate-spin mb-4 h-8 w-8 text-[var(--accent)]" fill="none" viewBox="0 0 24 24">
        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
        <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
      </svg>
      <p className="text-[var(--text-secondary)] font-medium">{displayMessage}</p>
    </div>
  );
};

// --- EmptyState ---
type EmptyStateProps = {
  title: string;
  description?: string;
  detail?: string;
  action?: React.ReactNode;
  icon?: React.ReactNode;
  className?: string;
};
export const EmptyState = ({ title, description, detail, action, icon, className = '' }: EmptyStateProps) => {
  const content = description ?? detail ?? '';
  return (
    <div className={`flex flex-col items-center justify-center p-12 text-center bg-[var(--surface-raised)] border border-dashed border-[var(--border-strong)] rounded-xl ${className}`}>
      {icon && <div className="mb-4 text-[var(--text-muted)]">{icon}</div>}
      <h3 className="text-lg font-bold text-[var(--foreground)] mb-1">{title}</h3>
      {content && <p className="text-[var(--text-secondary)] mb-6 max-w-sm">{content}</p>}
      {action && <div>{action}</div>}
    </div>
  );
};
