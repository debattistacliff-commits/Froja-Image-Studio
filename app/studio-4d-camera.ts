import type { CameraPosition } from "./spin-360";

export const CAMERA_ELEVATIONS = ["low", "eye", "high"] as const;

export function dragCamera(origin: CameraPosition, dx: number, dy: number, radius: number): CameraPosition {
  const azimuth = origin.azimuth + dx / radius * 90;
  const deadZone = radius * 0.35;
  const heightSteps = Math.sign(-dy) * Math.max(0, Math.ceil((Math.abs(dy) - deadZone) / (2 * deadZone)));
  const height = CAMERA_ELEVATIONS.indexOf(origin.elevation) + heightSteps;

  return {
    ...origin,
    azimuth: ((azimuth % 360) + 360) % 360,
    elevation: CAMERA_ELEVATIONS[Math.max(0, Math.min(height, CAMERA_ELEVATIONS.length - 1))],
  };
}

export function snapCamera(camera: CameraPosition): CameraPosition {
  return { ...camera, azimuth: (Math.round(camera.azimuth / 45) * 45) % 360 };
}
