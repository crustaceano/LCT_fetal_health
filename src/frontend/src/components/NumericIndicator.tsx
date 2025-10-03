import { cn } from '@/lib/utils';

interface NumericIndicatorProps {
  label: string;
  value: number;
  unit: string;
  isAlert?: boolean;
}

export const NumericIndicator = ({ label, value, unit, isAlert }: NumericIndicatorProps) => {
  return (
    <div className={cn(
      "flex flex-col gap-1 p-4 rounded-lg border transition-colors",
      isAlert ? "bg-destructive/10 border-destructive" : "bg-card border-border"
    )}>
      <span className="text-xs text-muted-foreground uppercase tracking-wide">{label}</span>
      <div className="flex items-baseline gap-2">
        <span className={cn(
          "text-3xl font-mono font-bold",
          isAlert ? "text-destructive" : "text-primary"
        )}>
          {value.toFixed(0)}
        </span>
        <span className="text-sm text-muted-foreground">{unit}</span>
      </div>
    </div>
  );
};
