const routeColors: Readonly<Record<string, string>> = {
  'V-01': '#1A66D6',
  'V-02': '#8F47C2',
  'V-03': '#00856C',
};

export function fleetColor(vehicleId: string, fallback: string) {
  return routeColors[vehicleId] ?? fallback;
}
