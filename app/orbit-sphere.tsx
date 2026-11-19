import type { ReactNode } from "react";

type OrbitDirection = { azimuth: number; elevation: number };
const radians = (degrees: number) => (degrees * Math.PI) / 180;
export const wrapAzimuth = (azimuth: number) => ((Math.round(azimuth) % 360) + 360) % 360;

export function orbitDirection(direction: OrbitDirection) {
  const azimuth = radians(direction.azimuth);
  const elevation = radians(direction.elevation);
  return {
    x: Math.sin(azimuth) * Math.cos(elevation),
    y: Math.sin(elevation),
    z: Math.cos(azimuth) * Math.cos(elevation),
  };
}

export const GLOBE_CENTER = 180;
export const GLOBE_RADIUS = 137;

export function projectOrbit(direction: OrbitDirection) {
  const { x, y, z } = orbitDirection(direction);
  const pitch = radians(-12);
  const vertical = y * Math.cos(pitch) - z * Math.sin(pitch);
  const depth = y * Math.sin(pitch) + z * Math.cos(pitch);
  const cameraDistance = 5;
  const perspective = Math.sqrt(cameraDistance ** 2 - 1) / (cameraDistance - depth);
  return {
    x: GLOBE_CENTER + x * GLOBE_RADIUS * perspective,
    y: GLOBE_CENTER - vertical * GLOBE_RADIUS * perspective,
    depth: z,
    behind: direction.azimuth > 90 && direction.azimuth < 270,
  };
}

export function dragOrbit(origin: OrbitDirection, dx: number, dy: number, bounds: { width: number; height: number }) {
  return {
    azimuth: origin.azimuth + dx * 360 / bounds.width,
    elevation: origin.elevation - dy * 115 / bounds.height,
  };
}

export function OrbitScene({ image, pictureId, behind }: { image: string; pictureId: string; behind?: ReactNode }) {
  return (
    <>
      <defs>
        <clipPath id={pictureId}><rect x="104" y="137" width="152" height="86" rx="9" /></clipPath>
      </defs>
      <g className="ls-orbits">
        <circle cx="180" cy="180" r={GLOBE_RADIUS} />
        <ellipse cx="180" cy="180" rx="137" ry="34" transform="rotate(-26 180 180)" />
        <ellipse cx="180" cy="180" rx="137" ry="48" transform="rotate(54 180 180)" />
        <ellipse cx="180" cy="180" rx="137" ry="92" transform="rotate(-63 180 180)" />
      </g>
      {behind}
      <rect className="ls-picture" x="104" y="137" width="152" height="86" rx="9" />
      {image ? (
        <image href={image} x="104" y="137" width="152" height="86" preserveAspectRatio="xMidYMin slice" clipPath={`url(#${pictureId})`} />
      ) : (
        <text className="ls-picture-placeholder" x="180" y="184" textAnchor="middle">Your picture</text>
      )}
    </>
  );
}
