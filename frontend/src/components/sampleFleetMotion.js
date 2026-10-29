// Presentation simulation only: no GPS, routing-provider or database writes.
export const CYCLE_SECONDS = 240;
const DEPOTS = [[13.0285, 77.5197], [12.9352, 77.6245], [12.9698, 77.7500]];
const mix = (a, b, fraction) => a.map((value, index) => value + (b[index] - value) * fraction);

export function sampleFleetAt(vehicles, elapsedSeconds) {
  return vehicles.filter(v => /^SAMPLE-\d+$/.test(v.vehicle_no)).slice(0, 25).map((vehicle, index) => {
    const origin = DEPOTS[index % DEPOTS.length];
    const spread = 0.009 + (index % 9) * 0.0015;
    const direction = index % 2 ? 1 : -1;
    const path = [origin, [origin[0] + spread, origin[1] + direction * spread],
      [origin[0] + spread * 1.6, origin[1] + direction * spread * 0.3],
      [origin[0] + spread * 0.5, origin[1] - direction * spread * 0.5], origin];
    const offset = (index * 7) % 160;
    const initialCycle = Math.floor(offset / CYCLE_SECONDS);
    const time = Math.max(0, elapsedSeconds) + offset;
    const completedCycles = Math.floor(time / CYCLE_SECONDS) - initialCycle;
    const phase = time % CYCLE_SECONDS;
    const leg = Math.floor(phase / 60);
    const local = phase % 60;
    const fraction = Math.min(local / 44, 1);
    const position = mix(path[leg], path[leg + 1], fraction);
    const unloading = local >= 44;
    const deliveredThisCycle = Math.min(3, leg + (unloading && leg < 3 ? 1 : 0));
    const capacity = Math.max(0, Number(vehicle.load_capacity_kg) || 0);
    const initialLoad = Math.min(capacity, Math.max(0, Number(vehicle.reading?.load_kg) || capacity * (0.4 + (index % 7) * 0.07)));
    const startingFuel = Number(vehicle.reading?.fuel_percent ?? (45 + index));
    // A schematic closed loop, not verified road distance or a fuel model.
    const loopKm = spread * 111 * 5;
    const tripProgress = (leg + fraction) / 4;
    const fuel = Math.max(0, startingFuel - tripProgress * (1.2 + index * 0.12));
    const status = unloading ? (leg === 3 ? 'Reloading' : 'Delivering') : (leg === 3 ? 'Returning' : 'Driving');
    return {
      id: vehicle.id, plate: vehicle.vehicle_no, type: vehicle.type, fuelType: vehicle.fuel_type,
      capacity, lat: position[0], lng: position[1], path, status,
      loadKg: Math.round(initialLoad * (1 - deliveredThisCycle / 3)),
      fuelPercent: Math.round(fuel * 10) / 10,
      speedKmh: unloading ? 0 : 18 + (index * 7) % 39,
      odometerKm: Math.round((Number(vehicle.reading?.odometer_km) || 0) + (completedCycles + tripProgress) * loopKm),
      delivered: completedCycles * 3 + deliveredThisCycle,
      nextStop: unloading ? (leg === 3 ? 'Depot reload' : `Drop ${leg + 1}`) : (leg === 3 ? 'Depot' : `Drop ${leg + 1}`),
      color: unloading ? '#c08a2e' : leg === 3 ? '#326fa0' : '#1b6a45',
    };
  });
}
