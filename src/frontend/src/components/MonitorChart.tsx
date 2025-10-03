import { useEffect, useRef } from 'react';

interface MonitorChartProps {
  data: [number, number][];   // [t_sec_from_start, value]
  elapsed: number;            // сек от старта
  channel: 'bpm' | 'uterus';
  color: string;
  label: string;
  timeWindow: number;         // сек
  yOffset: number;            // пикселей (можно 0)
}

export const MonitorChart = ({
  data, elapsed, channel, color, label, timeWindow, yOffset,
}: MonitorChartProps) => {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    // ===== размеры, ретина =====
    const rect = canvas.getBoundingClientRect();
    const dpr = window.devicePixelRatio || 1;
    canvas.width = rect.width * dpr;
    canvas.height = rect.height * dpr;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);

    // ===== фон =====
    ctx.fillStyle = 'hsl(222, 47%, 5%)';
    ctx.fillRect(0, 0, rect.width, rect.height);

    // ===== окно и данные (СЕК) =====
    const W = Math.max(0.001, timeWindow);
    const filtered = data.filter(([t]) => t >= elapsed - W && t <= elapsed);
    if (filtered.length < 2) {
      ctx.fillStyle = 'hsl(210, 40%, 98%)';
      ctx.font = '14px monospace';
      ctx.fillText(label, 10, 18);
      return;
    }

    // ===== конфиг порогов =====
    type BpmCfg = { hardMin: number; hardMax: number; warnLow: number; warnHigh: number; critLow: number; critHigh: number };
    type UtrCfg = { hardMin: number; hardMax: number; warnHigh: number; critHigh: number };

    const cfg =
      channel === 'bpm'
        ? ({ hardMin: 80, hardMax: 220, warnLow: 110, warnHigh: 180, critLow: 100, critHigh: 210 } as BpmCfg)
        : ({ hardMin: 0,  hardMax: 120, warnHigh: 60,  critHigh: 80  } as UtrCfg);

    // ===== домен Y: от критических границ + авторасширение =====
    let yMin = channel === 'bpm' ? (cfg as BpmCfg).critLow : (cfg as UtrCfg).hardMin;     // 100 / 0
    let yMax = channel === 'bpm' ? (cfg as BpmCfg).critHigh : (cfg as UtrCfg).critHigh;   // 210 / 80
    yMin = Math.max(yMin, (cfg as any).hardMin);
    yMax = Math.min(yMax, (cfg as any).hardMax);

    const vals = filtered.map(p => p[1]);
    const dMin = Math.min(...vals);
    const dMax = Math.max(...vals);
    if (dMin < yMin || dMax > yMax) {
      const pad = Math.max(1, (dMax - dMin) * 0.1);
      yMin = Math.min(yMin, dMin - pad);
      yMax = Math.max(yMax, dMax + pad);
    }
    if (yMin === yMax) { yMin -= 1; yMax += 1; }

    // ===== рамки, геометрия, helpers =====
    const padLeft = 44, padRight = 12, padTop = 10, padBottom = 28;
    const chartW = rect.width - padLeft - padRight;
    const chartH = rect.height - padTop - padBottom;

    // фон чарта
    ctx.fillStyle = 'rgba(255,255,255,0.02)';
    ctx.fillRect(padLeft, padTop, chartW, chartH);

    const clamp = (v: number, lo: number, hi: number) => Math.min(hi, Math.max(lo, v));

    const mapY = (v: number) => {
      const yNoOffset = padTop + (chartH - ((v - yMin) / (yMax - yMin)) * chartH);
      return clamp(yNoOffset + (yOffset || 0), padTop, padTop + chartH);
    };

    const mapX = (t: number) => {
      const frac = (elapsed - t) / W; // 0..1
      return padLeft + chartW * (1 - frac);
    };

    // ===== сетка X + подписи (сек/мин) =====
    const useMinutes = W > 181;
    let majorStepSec: number;
    if (useMinutes) {
      if (W <= 15 * 60) majorStepSec = 60;        // 1m
      else if (W <= 30 * 60) majorStepSec = 2 * 60;
      else if (W <= 60 * 60) majorStepSec = 5 * 60;
      else majorStepSec = 10 * 60;
    } else {
      majorStepSec = W <= 20 ? 2 : W <= 60 ? 5 : 10;
    }
    const formatTick = (sFromNow: number) => {
      if (!useMinutes) return `${sFromNow | 0}s`;
      const m = Math.round(sFromNow / 60);
      return `${m}m`;
    };

    ctx.strokeStyle = 'hsl(217, 33%, 12%)';
    ctx.lineWidth = 1;
    for (let s = 0; s <= W + 1e-6; s += majorStepSec) {
      const x = padLeft + chartW * (1 - s / W);
      if (x < padLeft || x > padLeft + chartW) continue;
      ctx.beginPath(); ctx.moveTo(x, padTop); ctx.lineTo(x, padTop + chartH); ctx.stroke();
      // подпись X
      ctx.fillStyle = 'hsl(215, 16%, 65%)';
      ctx.font = '12px monospace';
      ctx.textAlign = 'left';
      ctx.fillText(formatTick(s), x + 2, padTop + chartH + 16);
    }

    // ===== сетка Y (тики + единицы измерения) =====
    const units = channel === 'bpm' ? 'bpm' : 'mmHg'; // подстрой, если uterus в других единицах
    const yTicks = 5;
    for (let i = 0; i <= yTicks; i++) {
      const v = yMin + (i / yTicks) * (yMax - yMin);
      const y = mapY(v);
      ctx.beginPath(); ctx.moveTo(padLeft, y); ctx.lineTo(padLeft + chartW, y); ctx.stroke();
      // подпись Y
      ctx.fillStyle = 'hsl(215, 16%, 65%)';
      ctx.font = '12px monospace';
      ctx.textAlign = 'right';
      ctx.fillText(`${Math.round(v)}`, padLeft - 6, y + 4);
      ctx.textAlign = 'left';
    }
    // // подпись единиц возле оси
    // ctx.fillStyle = 'hsl(215, 16%, 65%)';
    // ctx.font = '12px monospace';
    // ctx.fillText(units, 6, padTop + 12);

    // ===== пороги + зона нормы =====
    const drawHLine = (val: number, style: string, caption?: string) => {
      const y = mapY(val);
      ctx.save();
      ctx.setLineDash([6, 4]);
      ctx.strokeStyle = style;
      ctx.lineWidth = 1.5;
      ctx.beginPath(); ctx.moveTo(padLeft, y); ctx.lineTo(padLeft + chartW, y); ctx.stroke();
      if (caption) {
        ctx.fillStyle = style;
        ctx.font = '12px monospace';
        ctx.fillText(caption, padLeft + 6, Math.max(padTop + 12, y - 4));
      }
      ctx.restore();
    };

    if (channel === 'bpm') {
      const c = cfg as BpmCfg;
      drawHLine(c.warnLow, 'hsl(48, 100%, 60%)', `warn ${c.warnLow}`);
      drawHLine(c.warnHigh,'hsl(48, 100%, 60%)', `warn ${c.warnHigh}`);
      drawHLine(c.critLow, 'hsl(0, 80%, 70%)',  `crit ${c.critLow}`);
      drawHLine(c.critHigh,'hsl(0, 80%, 70%)',  `crit ${c.critHigh}`);
      // зона нормы
      ctx.save();
      ctx.fillStyle = 'hsla(142, 70%, 40%, 0.06)';
      const yA = mapY(c.warnLow), yB = mapY(c.warnHigh);
      ctx.fillRect(padLeft, Math.min(yA, yB), chartW, Math.abs(yB - yA));
      ctx.restore();
    } else {
      const c = cfg as UtrCfg;
      drawHLine(c.warnHigh,'hsl(48, 100%, 60%)', `warn ${c.warnHigh}`);
      drawHLine(c.critHigh,'hsl(0, 80%, 70%)',  `crit ${c.critHigh}`);
    }

    // ===== линия с динамическим цветом =====
    const baseColor = color;
    const warnColor = 'hsl(48, 100%, 70%)';
    const critColor = 'hsl(0, 100%, 75%)';

    const pickColor = (v: number): string => {
      if (channel === 'bpm') {
        const c = cfg as BpmCfg;
        if (v < c.critLow || v > c.critHigh) return critColor;
        if (v < c.warnLow || v > c.warnHigh) return warnColor;
        return baseColor;
      } else {
        const c = cfg as UtrCfg;
        if (v > c.critHigh) return critColor;
        if (v > c.warnHigh) return warnColor;
        return baseColor;
      }
    };

    ctx.lineWidth = 2;
    let [t0, v0] = filtered[0];
    let x0 = mapX(t0);
    let y0 = mapY(v0);
    let col0 = pickColor(v0);

    ctx.strokeStyle = col0;
    ctx.beginPath();
    ctx.moveTo(x0, y0);

    for (let i = 1; i < filtered.length; i++) {
      const [t, v] = filtered[i];
      const x = mapX(t);
      const y = mapY(v);
      const col = pickColor(v);

      if (col !== col0) {
        ctx.lineTo(x, y);
        ctx.stroke();
        ctx.beginPath();
        ctx.strokeStyle = col;
        ctx.moveTo(x, y);
        col0 = col;
      } else {
        ctx.lineTo(x, y);
      }
      x0 = x; y0 = y;
    }
    ctx.stroke();

    // ===== подписи / легенда =====
    // заголовок
    ctx.fillStyle = 'hsl(210, 40%, 98%)';
    ctx.font = '14px monospace';
    ctx.textAlign = 'left';
    ctx.fillText(label, 50, 40);

  }, [data, elapsed, channel, color, label, timeWindow, yOffset]);

  return (
    <canvas
      ref={canvasRef}
      className="w-full h-full"
      style={{ imageRendering: 'crisp-edges' }}
    />
  );
};
