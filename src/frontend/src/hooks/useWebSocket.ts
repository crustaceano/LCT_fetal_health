import { useEffect, useRef, useState } from 'react';

export interface MonitorData {
  timestamp: number;
  channel1: number;
  channel2: number;
  heartRate: number;
  fetalMovement: number;
  contractions: number;
  alertFlag?: boolean;
  analytics?: string[];
}

export interface WebsData {
  uterus: [number, number][],
  bpm: [number, number][],
  elapsed: number,
  heartRate: number;
  fetalMovement: number;
  contractions: number;
  alertFlag?: boolean;
  analytics?: {ts: number, predictions: string[]}[];
}

interface UseWebSocketProps {
  url: string;
  isActive: boolean;
}

export const useWebSocket = ({ url, isActive }: UseWebSocketProps) => {
  const [data, setData] = useState<WebsData>({
    uterus: [],
    bpm: [],
    elapsed: 0,
    heartRate: 0,
    fetalMovement: 0,
    contractions: 0,
    alertFlag: false,
    analytics: []
  });
  const [analytics, setAnalytics] = useState<string[]>([]);
  const [isConnected, setIsConnected] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);
  const startTimeRef = useRef<number>(0);

  useEffect(() => {
    console.log(isActive)
    if (!isActive) {
      if (wsRef.current) {
        wsRef.current.close();
        wsRef.current = null;
      }
      setIsConnected(false);
      return;
    }
    

    const ws = new WebSocket(url);
    wsRef.current = ws;
    startTimeRef.current = Date.now();

    ws.onopen = () => {
      console.log('WebSocket connected');
      setIsConnected(true);
    };

    ws.onmessage = (event) => {
      try {
        const message = JSON.parse(event.data);
        
        if (message.type === 'snapshot') {
          const currentTime = Date.now();
          
          if ((message.bpm && (message.bpm[message.bpm.length -1][1] > 210 || message.bpm[message.bpm.length -1][1] < 100)) || (message.uterus && (message.uterus[message.uterus.length -1][1] > 80)) )
            setData({...data, elapsed: message.elapsed, bpm: message.bpm, uterus: message.uterus, heartRate: message.heartRate, fetalMovement: message.fetalMovement, contractions: message.contractions, alertFlag: true});
          else
          setData({...data, elapsed: message.elapsed, bpm: message.bpm, uterus: message.uterus, heartRate: message.heartRate, fetalMovement: message.fetalMovement, contractions: message.contractions, alertFlag: false});
          setAnalytics(message.analytics)
          // if (message.bpm && Array.isArray(message.bpm)) {
          //   const newBpm: WebsData['bpm'] = message.bpm.map((point: [number, number], idx: number) => {
          //     // const [elapsed] = point;
          //     // const uterusValue = message.uterus?.[idx]?.[1] || 0;
          //     const bpmValue = message.bpm?.[idx]?.[1] || 0;
              
          //     return {
          //       timestamp: startTimeRef.current + elapsed * 1000,
          //       channel1: bpmValue,
          //       channel2: uterusValue,
          //       heartRate: bpmValue,
          //       fetalMovement: 0,
          //       contractions: 0,
          //       alertFlag: false
          //     };
          //   });

            
          // }
        }

        // if (message.analytics) {
        //   setAnalytics(prev => [...prev, ...message.analytics]);
        // }
      } catch (error) {
        console.error('Error parsing WebSocket message:', error);
      }
    };

    ws.onerror = (error) => {
      console.error('WebSocket error:', error);
      setIsConnected(false);
    };

    ws.onclose = () => {
      console.log('WebSocket disconnected');
      setIsConnected(false);
    };

    return () => {
      ws.close();
    };
  }, [url, isActive]);

  const clearData = () => {
    setData({
    uterus: [],
    bpm: [],
    elapsed: 0,
    heartRate: 0,
    fetalMovement: 0,
    contractions: 0,
    alertFlag: false,
    analytics: []
  });
    setAnalytics([]);
  };

  return { data, analytics, isConnected, clearData };
};
