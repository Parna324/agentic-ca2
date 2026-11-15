import { clsx } from 'clsx';

const severityColors: Record<string, string> = {
  CRITICAL: 'bg-red-500/20 text-red-400 border border-red-500/30',
  HIGH: 'bg-orange-500/20 text-orange-400 border border-orange-500/30',
  MEDIUM: 'bg-yellow-500/20 text-yellow-400 border border-yellow-500/30',
  LOW: 'bg-blue-500/20 text-blue-400 border border-blue-500/30',
  INFO: 'bg-gray-500/20 text-gray-400 border border-gray-500/30',
  APPROVE: 'bg-green-500/20 text-green-400 border border-green-500/30',
  REQUEST_CHANGES: 'bg-red-500/20 text-red-400 border border-red-500/30',
  PENDING: 'bg-yellow-500/20 text-yellow-400 border border-yellow-500/30',
  RUNNING: 'bg-blue-500/20 text-blue-400 border border-blue-500/30',
  COMPLETED: 'bg-green-500/20 text-green-400 border border-green-500/30',
  FAILED: 'bg-red-500/20 text-red-400 border border-red-500/30',
};

interface BadgeProps {
  label: string;
  variant?: string;
  className?: string;
}

export default function Badge({ label, variant, className }: BadgeProps) {
  const colorClass =
    severityColors[variant || label] || 'bg-gray-500/20 text-gray-400 border border-gray-500/30';
  return (
    <span
      className={clsx(
        'inline-flex items-center px-2 py-0.5 rounded text-xs font-medium',
        colorClass,
        className
      )}
    >
      {label}
    </span>
  );
}
