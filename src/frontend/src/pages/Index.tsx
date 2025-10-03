import { useEffect, useState } from 'react';
import { Button } from '@/components/ui/button';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { MonitorChart } from '@/components/MonitorChart';
import { NumericIndicator } from '@/components/NumericIndicator';
import { StartSimulationDialog } from '@/components/StartSimulationDialog';
import { AnalyticsDialog } from '@/components/AnalyticsDialog';
import { useWebSocket } from '@/hooks/useWebSocket';
import { useMockData } from '@/hooks/useMockData';
import { Activity, BarChart3 } from 'lucide-react';

const Index = () => {
  const [timeWindow, setTimeWindow] = useState<number>(30);
  const [studyId, setStudyId] = useState<string>('');
  const [isSimulationRunning, setIsSimulationRunning] = useState(false);
  const [startDialogOpen, setStartDialogOpen] = useState(false);
  const [analyticsDialogOpen, setAnalyticsDialogOpen] = useState(false);



  // Replace with your actual WebSocket URL
  const { data: wsData, analytics, isConnected } = useWebSocket({
    url: 'ws://127.0.0.1:8000/ws',
    isActive: isSimulationRunning,
  });

  // Mock data when no simulation is running
  const mockData = useMockData(!isSimulationRunning);
  
  // Use mock data when simulation is not running, otherwise use WebSocket data
  const data = isSimulationRunning ? wsData : [];

  const handleStartSimulation = (id: string) => {
    setStudyId(id);
    setIsSimulationRunning(true);
  };

  const handleStopSimulation = () => {
    setStudyId('');
    setIsSimulationRunning(false);
  };

  // Get latest values for indicators
  // const latestData = data[data.length - 1];
  const heartRate = wsData?.heartRate || 0;
  const fetalMovement = wsData?.fetalMovement || 0;
  const contractions = wsData?.contractions || 0;
  const hasAlert = wsData?.alertFlag || false;

  return (
    <div className="min-h-screen bg-background p-4">
      <div className="max-w-[1800px] mx-auto space-y-4">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-3xl font-bold text-foreground flex items-center gap-2">
              <Activity className="h-8 w-8 text-primary" />
              Фетальный монитор
            </h1>
            <p className="text-sm text-muted-foreground mt-1">
              {isConnected ? (
                <span className="text-success">● Подключено</span>
              ) : (
                <span className="text-muted-foreground">○ Не подключено</span>
              )}
            </p>
          </div>
          
          <div className="flex items-center gap-3">
            <div className="flex items-center gap-2">
              <span className="text-sm text-muted-foreground">Временное окно:</span>
              <Select value={timeWindow.toString()} onValueChange={(v) => setTimeWindow(Number(v))}>
                <SelectTrigger className="w-32">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="10">10 сек</SelectItem>
                  <SelectItem value="30">30 сек</SelectItem>
                  <SelectItem value="60">60 сек</SelectItem>
                  <SelectItem value="180">3 мин</SelectItem>
                  <SelectItem value="600">10 мин</SelectItem>
                  <SelectItem value="1800">30 мин</SelectItem>
                </SelectContent>
              </Select>
            </div>
            
            <Button onClick={() => setStartDialogOpen(true)}>
              {isSimulationRunning ? 'Управление' : 'Начать эмуляцию'}
            </Button>
            
            <Button variant="outline" onClick={() => setAnalyticsDialogOpen(true)}>
              <BarChart3 className="h-4 w-4 mr-2" />
              Аналитика
            </Button>
          </div>
        </div>

        {/* Main Content */}
        <div className="grid grid-cols-1 lg:grid-cols-4 gap-4">
          {/* Charts */}
          <div className="lg:col-span-3 space-y-4">
            <div className="bg-card border border-border rounded-lg p-4 h-[300px]">
              <MonitorChart
                data={wsData.bpm}
                channel="bpm"
                color="hsl(142, 76%, 36%)"
                label="Канал 1 - Сердечный ритм (FHR)"
                timeWindow={timeWindow}
                yOffset={0}
                elapsed={wsData.elapsed}
              />
            </div>
            
            <div className="bg-card border border-border rounded-lg p-4 h-[300px]">
              <MonitorChart
                data={wsData.uterus}
                channel="uterus"
                color="hsl(217, 91%, 60%)"
                label="Канал 2 - Маточные сокращения (IUP)"
                timeWindow={timeWindow}
                yOffset={0}
                elapsed={wsData.elapsed}
              />
            </div>
          </div>

          {/* Indicators */}
          <div className="space-y-4">
            <NumericIndicator
              label="Сердечный ритм (FHR)"
              value={heartRate}
              unit="уд/мин"
              isAlert={hasAlert && (heartRate < 110 || heartRate > 160)}
            />
            
            <NumericIndicator
              label="Маточные сокращения (IUP)"
              value={fetalMovement}
              unit="/мин"
              isAlert={false}
            />
            
            <NumericIndicator
              label="Схватки"
              value={contractions}
              unit=""
              isAlert={hasAlert && contractions > 5}
            />

            <div className="p-4 rounded-lg border border-border bg-card">
              <div className="text-xs text-muted-foreground uppercase tracking-wide mb-2">
                Статус
              </div>
              <div className={`text-sm font-medium ${hasAlert ? 'text-destructive' : 'text-success'}`}>
                {hasAlert ? '⚠ Требуется внимание' : '✓ Нормальные показатели'}
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Dialogs */}
      <StartSimulationDialog
        open={startDialogOpen}
        onOpenChange={setStartDialogOpen}
        onStartSimulation={handleStartSimulation}
        onStopSimulation={handleStopSimulation}
        isRunning={isSimulationRunning}
      />

      <AnalyticsDialog
        open={analyticsDialogOpen}
        onOpenChange={setAnalyticsDialogOpen}
        analytics={analytics}
      />
    </div>
  );
};

export default Index;
