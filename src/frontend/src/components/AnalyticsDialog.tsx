import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { ScrollArea } from '@/components/ui/scroll-area';

interface AnalyticsDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  analytics: {ts: number, predictions: string[]}[];
}

export const AnalyticsDialog = ({ open, onOpenChange, analytics }: AnalyticsDialogProps) => {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-lg max-h-[80vh]">
        <DialogHeader>
          <DialogTitle>Аналитика</DialogTitle>
        </DialogHeader>
        
        <ScrollArea className="h-[400px] pr-4">
  {(!analytics || analytics.length === 0) ? (
    <p className="text-sm text-muted-foreground text-center py-8">
      Нет данных аналитики
    </p>
  ) : (
    <div className="space-y-2">
      {analytics.reverse().map((item, index) => {
        const tsNumber = typeof item.ts === 'number' ? item.ts : Number(item.ts || 0);
        const timeStr = new Date(tsNumber * 1000).toLocaleTimeString('ru-RU', {
          hour: '2-digit',
          minute: '2-digit',
          second: '2-digit',
        });

        return (
          <div
            key={index}
            className="p-5 rounded-lg bg-muted text-sm font-mono"
          >
            <div className="flex items-center justify-between mb-3">
              <span className="text-xs text-muted-foreground">Время</span>
              <span className="font-semibold">{timeStr}</span>
            </div>

            <ul className="list-disc pl-5 space-y-1">
              {item.predictions?.map((pred: any, index2: number) => (
                <li key={index2}>
                  {typeof pred === 'string' ? pred : JSON.stringify(pred)}
                </li>
              ))}
            </ul>
          </div>
        );
      })}
    </div>
  )}
</ScrollArea>
      </DialogContent>
    </Dialog>
  );
};
