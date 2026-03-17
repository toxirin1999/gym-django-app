// rpeHints.ts

export type Severity = "none" | "info" | "warn" | "danger";

export type SuggestionAction =
  | { type: "keep" }
  | { type: "increase_weight"; minKg: number; maxKg: number }
  | { type: "decrease_weight"; minKg: number; maxKg: number }
  | { type: "adjust_reps"; deltaReps: number }; // negativo = bajar reps

export type RpeHintInput = {
  setIndex: number; // 1..N
  totalSets: number;
  rpeTarget: number; // ej 6
  rpeFelt: number;   // ej 7
  repsDone: number;
  repsTargetMin: number; // ej 10
  repsTargetMax: number; // ej 12
  // opcional: para afinar escalones de peso según ejercicio
  smallestIncrementKg?: number; // ej 2.5
};

export type RpeHint = {
  show: boolean;
  severity: Severity;
  message: string;
  action: SuggestionAction;
  deltaRpe: number;
};

function clamp(n: number, a: number, b: number) {
  return Math.max(a, Math.min(b, n));
}

function defaultIncrement(inc?: number) {
  // si no lo pasas, usa 2.5 como “estándar”
  return inc && inc > 0 ? inc : 2.5;
}

function weightRange(inc: number, stepsMin: number, stepsMax: number) {
  return { minKg: inc * stepsMin, maxKg: inc * stepsMax };
}

export function getRpeHint(input: RpeHintInput): RpeHint {
  const {
    setIndex,
    totalSets,
    rpeTarget,
    rpeFelt,
    repsDone,
    repsTargetMin,
    repsTargetMax,
  } = input;

  const inc = defaultIncrement(input.smallestIncrementKg);
  const deltaRpe = rpeFelt - rpeTarget;

  const isFirstSet = setIndex === 1;
  const isLastSet = setIndex === totalSets;

  const repsInRange = repsDone >= repsTargetMin && repsDone <= repsTargetMax;
  const repsAboveRange = repsDone > repsTargetMax;
  const repsBelowRange = repsDone < repsTargetMin;

  // Si aún no hay datos válidos, no mostramos nada
  if (!Number.isFinite(rpeTarget) || !Number.isFinite(rpeFelt)) {
    return { show: false, severity: "none", message: "", action: { type: "keep" }, deltaRpe: 0 };
  }

  // Regla base por delta RPE
  // ΔRPE <= -2: muy fácil / conservador
  if (deltaRpe <= -2) {
    if (isLastSet) {
      return {
        show: true,
        severity: "info",
        message: "Muy conservador, pero al ser la última serie: prioriza buena técnica y finaliza sólido.",
        action: { type: "keep" },
        deltaRpe,
      };
    }
    const { minKg, maxKg } = weightRange(inc, 1, 2); // +2.5 a +5
    return {
      show: true,
      severity: "info",
      message: `Demasiado fácil para el objetivo. Sube ${minKg}–${maxKg} kg en la próxima serie.`,
      action: { type: "increase_weight", minKg, maxKg },
      deltaRpe,
    };
  }

  // ΔRPE = -1: algo fácil
  if (deltaRpe === -1) {
    if (!repsInRange && repsAboveRange && !isLastSet) {
      // Si además te pasaste de reps, mejor subir un poco más
      const { minKg, maxKg } = weightRange(inc, 1, 2);
      return {
        show: true,
        severity: "info",
        message: `Fácil y por encima de reps. Sube ${minKg}–${maxKg} kg en la próxima serie.`,
        action: { type: "increase_weight", minKg, maxKg },
        deltaRpe,
      };
    }
    if (isLastSet) {
      return {
        show: true,
        severity: "info",
        message: "Un poco fácil. Apunta a subir carga o reps la próxima sesión.",
        action: { type: "keep" },
        deltaRpe,
      };
    }
    const { minKg, maxKg } = weightRange(inc, 1, 2);
    return {
      show: true,
      severity: "info",
      message: `Carga conservadora. Puedes subir ${minKg}–${maxKg} kg en la siguiente serie.`,
      action: { type: "increase_weight", minKg, maxKg },
      deltaRpe,
    };
  }

  // ΔRPE = 0: perfecto
  if (deltaRpe === 0) {
    return {
      show: true,
      severity: "info",
      message: "Serie ideal. Mantén carga y reps.",
      action: { type: "keep" },
      deltaRpe,
    };
  }

  // ΔRPE = +1: algo más duro (zona gris)
  if (deltaRpe === 1) {
    if (isFirstSet) {
      return {
        show: true,
        severity: "warn",
        message: "Un poco más exigente de lo esperado en la serie 1. Mantén y observa la próxima.",
        action: { type: "keep" },
        deltaRpe,
      };
    }
    if (isLastSet) {
      return {
        show: true,
        severity: "warn",
        message: "Algo más exigente. Prioriza completar reps con buena técnica.",
        action: { type: "keep" },
        deltaRpe,
      };
    }
    return {
      show: true,
      severity: "warn",
      message: "Algo más exigente de lo esperado. Mantén carga y ajusta si vuelve a subir el RPE.",
      action: { type: "keep" },
      deltaRpe,
    };
  }

  // ΔRPE >= +2: exceso claro
  if (deltaRpe >= 2) {
    // Preferir bajar reps en última serie; en otras, bajar peso o reps
    if (isLastSet) {
      const deltaReps = -clamp(deltaRpe, 1, 2); // baja 1–2 reps aprox
      return {
        show: true,
        severity: "danger",
        message: "RPE alto para el objetivo. Baja 1–2 reps para proteger técnica en esta última serie.",
        action: { type: "adjust_reps", deltaReps },
        deltaRpe,
      };
    }

    const { minKg, maxKg } = weightRange(inc, 1, 2); // -2.5 a -5
    return {
      show: true,
      severity: "danger",
      message: `RPE alto para el objetivo. Reduce ${minKg}–${maxKg} kg o baja 1–2 reps en la próxima serie.`,
      action: { type: "decrease_weight", minKg, maxKg },
      deltaRpe,
    };
  }

  // fallback
  return { show: false, severity: "none", message: "", action: { type: "keep" }, deltaRpe };
}
