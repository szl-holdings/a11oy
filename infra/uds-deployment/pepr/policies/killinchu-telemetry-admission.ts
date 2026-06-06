/**
 * killinchu-telemetry-admission.ts
 * SZL Holdings — Formula Uplift E-12
 * SPDX-License-Identifier: Apache-2.0
 *
 * Pepr Admission Policy: validates killinchu drone telemetry packets before storage.
 * Source: UDS_PAYLOAD_UPLIFTS.md E-12 / v20 addendum (killinchu drone application)
 * Lean status: N/A — operational policy (POLICY, not THEOREM)
 * Warhacker flag: YES — killinchu is demo app; clean telemetry is prerequisite
 *
 * Blocks any ConfigMap labelled szl.io/telemetry-type=drone that is missing:
 *   timestamp, lat, lon, battery_pct, session_id
 * or where battery_pct <= 0 or GPS is out of range.
 *
 * Fail-OPEN on errors (don't block drone ops on unexpected exceptions).
 *
 * Signed-off-by: Yachay <yachay@szlholdings.ai>
 * Co-Authored-By: Perplexity Computer Agent <agent@perplexity.ai>
 */

import { Capability, a, Log } from "pepr";

export const KillinchuTelemetryAdmission = new Capability({
  name: "killinchu-telemetry-admission",
  description:
    "SZL E-12: Validates killinchu drone telemetry packets before storage. " +
    "Doctrine v11. Proof label: POLICY (operational invariant, no Lean theorem). " +
    "Fail-OPEN on errors — does not block drone ops on unexpected exceptions.",
  namespaces: ["szl-killinchu", "killinchu"],
});

const { When } = KillinchuTelemetryAdmission;

When(a.ConfigMap)
  .IsCreatedOrUpdated()
  .WithLabel("szl.io/telemetry-type", "drone")
  .Validate((cm) => {
    try {
      const d = cm.Raw?.data ?? {};

      // Required fields
      const required = ["timestamp", "lat", "lon", "battery_pct", "session_id"];
      for (const field of required) {
        if (!d[field]) {
          return cm.Deny(
            `SZL E-12 KillinchuTelemetry: drone telemetry missing required field '${field}'. ` +
            `Doctrine v11. Fail-OPEN policy: only blocks missing required fields.`
          );
        }
      }

      // Battery must be positive
      const battery = parseFloat(d["battery_pct"]);
      if (isNaN(battery) || battery <= 0) {
        return cm.Deny(
          `SZL E-12 KillinchuTelemetry: battery_pct=${d["battery_pct"]} must be > 0.`
        );
      }

      // GPS range check
      const lat = parseFloat(d["lat"]);
      const lon = parseFloat(d["lon"]);
      if (isNaN(lat) || isNaN(lon) || lat < -90 || lat > 90 || lon < -180 || lon > 180) {
        return cm.Deny(
          `SZL E-12 KillinchuTelemetry: GPS out of range: lat=${lat}, lon=${lon}.`
        );
      }

      return cm.Approve();
    } catch (e) {
      // Fail-OPEN: if unexpected error, log and allow (don't block drone ops)
      Log.warn(`KillinchuTelemetryAdmission: unexpected error (fail-open): ${e}`);
      return cm.Approve();
    }
  });
