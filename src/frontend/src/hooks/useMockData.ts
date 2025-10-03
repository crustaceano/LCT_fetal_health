import { useEffect, useState } from 'react';
import { MonitorData } from './useWebSocket';

export const useMockData = (isActive: boolean) => {
  const [mockData, setMockData] = useState<MonitorData[]>([]);

  useEffect(() => {
    if (!isActive) {
      setMockData([]);
      return;
    }

    // Generate initial data points
    const now = Date.now();
    const initialData: MonitorData[] = [];
    
    for (let i = 240; i >= 0; i--) {
      const timestamp = now - (i * 125); // 125ms = 8 points per second
      initialData.push({
        timestamp,
        channel1: generateHeartRateWave(timestamp),
        channel2: generateContractionWave(timestamp),
        heartRate: 120 + Math.sin(timestamp / 5000) * 10,
        fetalMovement: Math.floor(Math.random() * 5) + 8,
        contractions: Math.floor(Math.random() * 3) + 2,
        alertFlag: false
      });
    }
    
    setMockData(initialData);

    // Update data every 125ms (8 times per second)
    const interval = setInterval(() => {
      setMockData(prev => {
        const now = Date.now();
        const newPoint: MonitorData = {
          timestamp: now,
          channel1: generateHeartRateWave(now),
          channel2: generateContractionWave(now),
          heartRate: 120 + Math.sin(now / 5000) * 10,
          fetalMovement: Math.floor(Math.random() * 5) + 8,
          contractions: Math.floor(Math.random() * 3) + 2,
          alertFlag: false
        };
        
        return [...prev, newPoint].slice(-1000); // Keep last 1000 points
      });
    }, 125);

    return () => clearInterval(interval);
  }, [isActive]);

  return mockData;
};

// Generate heart rate wave (simulated ECG)
function generateHeartRateWave(timestamp: number): number {
  const t = timestamp / 1000;
  const heartRateFreq = 2; // ~120 bpm
  
  // Base sine wave
  const baseWave = Math.sin(t * heartRateFreq * Math.PI * 2) * 30;
  
  // Add QRS complex spikes
  const phase = (t * heartRateFreq) % 1;
  let qrsSpike = 0;
  
  if (phase > 0.1 && phase < 0.3) {
    const spikePhase = (phase - 0.1) / 0.2;
    qrsSpike = Math.sin(spikePhase * Math.PI) * 50;
  }
  
  // Add some noise
  const noise = (Math.random() - 0.5) * 5;
  
  return baseWave + qrsSpike + noise;
}

// Generate contraction wave
function generateContractionWave(timestamp: number): number {
  const t = timestamp / 1000;
  const contractionFreq = 0.05; // Slow contractions
  
  // Slow wave
  const slowWave = Math.sin(t * contractionFreq * Math.PI * 2) * 40;
  
  // Add smaller variations
  const variation = Math.sin(t * 0.5 * Math.PI * 2) * 15;
  
  // Add noise
  const noise = (Math.random() - 0.5) * 3;
  
  return slowWave + variation + noise;
}
