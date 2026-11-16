import type { ReactNode } from "react";
import { DeckSymbol } from "./tool-deck";

/** The LED colours Froja can glow in (one look, many lights). */
export const LED_COLOURS = [
  { id: "blue", label: "Ice blue" },
  { id: "green", label: "Green" },
  { id: "pink", label: "Pink" },
  { id: "purple", label: "Purple" },
  { id: "red", label: "Red" },
  { id: "amber", label: "Amber" },
  { id: "white", label: "White" },
] as const;

export function LedPicker({ value, onChange }: { value: string; onChange: (id: string) => void }) {
  return (
    <span className="led-picker" role="radiogroup" aria-label="LED light colour">
      {LED_COLOURS.map((c) => (
        <button key={c.id} role="radio" aria-checked={value === c.id} title={`${c.label} LEDs`} aria-label={`${c.label} LEDs`}
          className={`led-swatch led-dot-${c.id} ${value === c.id ? "picked" : ""}`} onClick={() => onChange(c.id)} />
      ))}
    </span>
  );
}

export type StationStep = { id: string; label: string };

/** The control strip at the top of every studio: home, previous / next studio, and (in Create) the step slider. */
export default function StationBar({ name, symbol, onHome, onPrev, onNext, prevName, nextName, steps, step, onStep, ledPicker, monitor }: {
  name: string;
  symbol: string;
  onHome: () => void;
  onPrev: () => void;
  onNext: () => void;
  prevName: string;
  nextName: string;
  steps?: StationStep[];
  step?: number;
  onStep?: (step: number) => void;
  ledPicker?: ReactNode;
  monitor?: ReactNode;
}) {
  const hasSteps = !!steps?.length && step !== undefined && !!onStep;
  return (
    <nav className="station-bar" aria-label="Froja studios">
      <button className="sb-round sb-home" onClick={onHome} title="All studios" aria-label="All studios">
        <img src="/brand/froja-logo-3d-flat.png" alt="" />
      </button>
      <button className="sb-round" onClick={onPrev} title={prevName} aria-label={`Previous studio: ${prevName}`}>‹</button>
      <div className="sb-name">
        <span className="sb-symbol"><DeckSymbol name={symbol} /></span>
        <b>{name}</b>
      </div>
      <button className="sb-round" onClick={onNext} title={nextName} aria-label={`Next studio: ${nextName}`}>›</button>
      {monitor}
      {ledPicker && <div className="sb-led">{ledPicker}</div>}

      {hasSteps && (
        <div className="sb-steps" role="tablist" aria-label="Create steps">
          {steps!.map((s, i) => (
            <button key={s.id} role="tab" aria-selected={i === step} className={`sb-step ${i === step ? "lit" : ""} ${i < step! ? "done" : ""}`} onClick={() => onStep!(i)}>
              <span className="sb-dot" />{i + 1} · {s.label}
            </button>
          ))}
        </div>
      )}
      {hasSteps && (
        <div className="sb-stepnav">
          <button className="sb-pill" disabled={step === 0} onClick={() => onStep!(Math.max(0, step! - 1))}>‹ Back</button>
          <button className="sb-pill sb-next" disabled={step === steps!.length - 1} onClick={() => onStep!(Math.min(steps!.length - 1, step! + 1))}>
            {step! < steps!.length - 1 ? `Next: ${steps![step! + 1].label} ›` : "Ready"}
          </button>
        </div>
      )}
    </nav>
  );
}
