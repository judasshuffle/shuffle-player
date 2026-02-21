export const BANKS = {
  Default: [
    {
      name: "Tempest MVP",
      effectId: "tempestTunnel",
      params: {
        spin: 1.5,
        trail: 0.08,
        zap: 1.0,
        spawn: 2,
        shockwave: 1.0,
        beatThresh: 1.25,
        glow: false,
        phosphor: true,
      },
    },
    {
      name: "Hot & Zappy",
      effectId: "tempestTunnel",
      params: {
        spin: 2.2,
        trail: 0.06,
        zap: 1.8,
        spawn: 4,
        shockwave: 1.2,
        beatThresh: 1.22,
        glow: true,
        phosphor: true,
      },
    },
    {
      name: "Slow Phosphor",
      effectId: "tempestTunnel",
      params: {
        spin: 0.8,
        trail: 0.05,
        zap: 0.7,
        spawn: 1,
        shockwave: 0.8,
        beatThresh: 1.28,
        glow: false,
        phosphor: true,
      },
    },
  ],

  Minimal: [
    {
      name: "Wireframe Clean",
      effectId: "tempestTunnel",
      params: {
        spin: 1.2,
        trail: 0.16,
        zap: 0.9,
        spawn: 0,
        shockwave: 0.0,
        beatThresh: 1.30,
        glow: false,
        phosphor: false,
      },
    },
  ],

  VLM: [
    {
      name: "Minter 01 (Tunnel)",
      effectId: "tempestTunnel",
      params: { spin: 1.4, trail: 0.07, zap: 1.2, spawn: 2, shockwave: 1.0, beatThresh: 1.25, glow: false, phosphor: true },
    },
    {
      name: "Minter 02 (Rings)",
      effectId: "ringShock",
      params: { spin: 1.2, trail: 0.08, zap: 1.1, spawn: 3, shockwave: 1.5, beatThresh: 1.22, glow: true, phosphor: true },
    },
    {
      name: "Minter 03 (Burst)",
      effectId: "vectorBurst",
      params: { spin: 0.8, trail: 0.07, zap: 1.3, spawn: 2, shockwave: 0.8, beatThresh: 1.26, glow: true, phosphor: true },
    },
    {
      name: "Minter 04 (Clean Rings)",
      effectId: "ringShock",
      params: { spin: 0.6, trail: 0.14, zap: 0.8, spawn: 1, shockwave: 1.0, beatThresh: 1.32, glow: false, phosphor: false },
    },
  ],
};

export function listBanks() {
  return Object.keys(BANKS);
}

export function listPresets(bankName) {
  return (BANKS[bankName] ?? []).map(p => p.name);
}

export function getPreset(bankName, presetName) {
  const bank = BANKS[bankName] ?? [];
  return bank.find(p => p.name === presetName) ?? bank[0] ?? null;
}
