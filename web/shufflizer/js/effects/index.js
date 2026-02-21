import { effect as tempestTunnel } from "./tempestTunnel.js";
import { effect as ringShock } from "./ringShock.js";
import { effect as vectorBurst } from "./vectorBurst.js";

export const EFFECTS = [tempestTunnel, ringShock, vectorBurst];

export function getEffectById(id) {
  return EFFECTS.find(e => e.id === id) ?? EFFECTS[0];
}
