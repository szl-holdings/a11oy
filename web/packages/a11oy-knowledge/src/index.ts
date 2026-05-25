export { classifyDualSpirit } from "./dual_spirit_classifier";
export type { SpiritSignal, DualSpiritVerdict } from "./dual_spirit_classifier";
export { detectDualUse } from "./dual_use_detector";
export type { DualUseRequest, DualUseResult, DualUseHit } from "./dual_use_detector";

import metatron from "./metatron_names_registry.json";
import watchers from "./watchers_taxonomy.json";
import dualSpirit from "./dual_spirit_attributes.json";
import physiognomy from "./physiognomy_agent_profile.json";
import capabilityAge from "./capability_age_table.json";
import pesherFormulae from "./pesher_formulae.json";

export const KNOWLEDGE_REGISTRIES = {
  metatron,
  watchers,
  dualSpirit,
  physiognomy,
  capabilityAge,
  pesherFormulae,
} as const;
