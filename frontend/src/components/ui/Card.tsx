import { clsx } from 'clsx';
import { ReactNode } from 'react';

interface CardProps {
  children: ReactNode;
  className?: string;
  title?: string;
}

export default function Card({ children, className, title }: CardProps) {
  return (
    <div
      className={clsx(
        'bg-[#111118] border border-[#1e1e2e] rounded-xl p-6',
        className
      )}
    >
      {title && (
        <h3 className="text-[#9ca3af] text-xs font-semibold mb-4 uppercase tracking-wider">
          {title}
        </h3>
      )}
      {children}
    </div>
  );
}
