import { useState } from 'react';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Label } from '@/components/ui/label';
import { toast } from 'sonner';

interface StartSimulationDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onStartSimulation: (studyId: string) => void;
  onStopSimulation: () => void;
  isRunning: boolean;
}

export const StartSimulationDialog = ({
  open,
  onOpenChange,
  onStartSimulation,
  onStopSimulation,
  isRunning
}: StartSimulationDialogProps) => {
  const [patientName, setPatientName] = useState<string>('');
  const [studyNumber, setStudyNumber] = useState<string>('');
  const [dataset, setDataset] = useState<string>('');

  const handleStart = async () => {
    if (!studyNumber || !dataset) {
      toast.error('Пожалуйста, заполните номер исследования и набор данных');
      return;
    }

    try {
      const userId = crypto.randomUUID();
      
      const response = await fetch('http://localhost:8000/start', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          user_id: userId,
          user_name: patientName || null,
          dataset: dataset,
          study_number: parseInt(studyNumber),
        }),
      });

      if (!response.ok) throw new Error('Failed to start simulation');

      const data = await response.json();
      onStartSimulation(data.id || userId);
      toast.success('Исследование начато');
      onOpenChange(false);
    } catch (error) {
      console.error('Error starting simulation:', error);
      toast.error('Ошибка при запуске исследования');
    }
  };

  const handleStop = async () => {
    try {
      const response = await fetch('http://localhost:8000/stop', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
      });

      if (!response.ok) throw new Error('Failed to stop simulation');

      onStopSimulation();
      toast.success('Исследование остановлено');
    } catch (error) {
      console.error('Error stopping simulation:', error);
      toast.error('Ошибка при остановке исследования');
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Управление эмуляцией</DialogTitle>
        </DialogHeader>
        
        {!isRunning ? (
          <div className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="patient-name">Имя пациента</Label>
              <Input
                id="patient-name"
                placeholder="Введите имя пациента (необязательно)"
                value={patientName}
                onChange={(e) => setPatientName(e.target.value)}
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="study-number">Номер исследования</Label>
              <Input
                id="study-number"
                type="number"
                placeholder="Введите номер"
                value={studyNumber}
                onChange={(e) => setStudyNumber(e.target.value)}
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="dataset">Набор данных</Label>
              <Select value={dataset} onValueChange={setDataset}>
                <SelectTrigger id="dataset">
                  <SelectValue placeholder="Выберите набор данных" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="regular">Regular</SelectItem>
                  <SelectItem value="hypoxia">Hypoxia</SelectItem>
                </SelectContent>
              </Select>
            </div>

            <Button onClick={handleStart} className="w-full">
              Начать исследование
            </Button>
          </div>
        ) : (
          <div className="space-y-4">
            <p className="text-sm text-muted-foreground">
              Исследование выполняется...
            </p>
            <Button onClick={handleStop} variant="destructive" className="w-full">
              Остановить исследование
            </Button>
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
};
