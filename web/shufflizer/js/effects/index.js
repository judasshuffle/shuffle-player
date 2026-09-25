import { effect as tempestTunnel } from "./tempestTunnel.js";
import { effect as ringShock } from "./ringShock.js";
import { effect as vectorBurst } from "./vectorBurst.js";
import { effect as kevsFractalTree } from "./kevsFractalTree.js";
import { effect as tempestBonusPyramids } from "./tempestBonusPyramids.js";
import { effect as warpBonusRings } from "./warpBonusRings.js";

export const EFFECTS = [
  tempestTunnel,
  ringShock,
  vectorBurst,
  kevsFractalTree,
  tempestBonusPyramids,
  warpBonusRings
];

export function getEffectById(id) {
  return EFFECTS.find(e => e.id === id) ?? EFFECTS[0];
}
