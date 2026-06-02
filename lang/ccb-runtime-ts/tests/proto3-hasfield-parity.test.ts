/**
 * CONTRACT-05 (D55) — proto3 submessage presence parity test (TS side).
 *
 * Phase 7.1 Plan 01, Task 08.
 *
 * The TS proto3 surface emits OPTIONAL fields as `T | undefined`.
 * Presence check = `value !== undefined`. Truthy fallback
 * (`if (msg.field)`) is wrong for two reasons: (a) `{}` is truthy in
 * JS, so a present-but-empty submessage looks the same as a populated
 * one; (b) the absent case is `undefined`, not `null`, and falsy on its
 * own — but downstream code that conflates `undefined` with `null`
 * breaks.
 *
 * The TS proto types in this repo currently only type the P4
 * SkillInstructions field on SessionPayload (see
 * lang/ccb-runtime-ts/src/proto/types.ts:34-44). P1 / P5 are not
 * present in the TS type surface today; the test asserts what the
 * TS contract actually exposes. Rust + Python sides cover P1 / P4 / P5
 * in full.
 *
 * Mirrored in:
 *   - tests/contract/contract_v1/test_proto3_hasfield_parity.py (Python)
 *   - crates/grid-runtime/tests/proto3_hasfield_parity.rs (Rust)
 */

import { describe, expect, test } from "bun:test";
import type {
    SessionPayload,
    SkillInstructions,
} from "../src/proto/types.js";

describe("proto3 HasField parity (CONTRACT-05 / D55)", () => {
    test("P4 SkillInstructions absent on default-constructed SessionPayload", () => {
        const p: SessionPayload = {};
        expect(p.skillInstructions).toBeUndefined();
    });

    test("P4 SkillInstructions present after assignment", () => {
        const p: SessionPayload = {
            skillInstructions: { skillId: "x" },
        };
        expect(p.skillInstructions).not.toBeUndefined();
        expect(p.skillInstructions?.skillId).toBe("x");
    });

    test("truthy fallback anti-pattern documentation", () => {
        // The anti-pattern this test guards against:
        //   if (payload.skillInstructions) { ... }  // wrong: {} is truthy
        // Correct pattern:
        //   if (payload.skillInstructions !== undefined) { ... }
        // OR, when downstream code only cares about specific fields:
        //   if (payload.skillInstructions?.skillId) { ... }
        const empty: SessionPayload = {
            skillInstructions: {} as SkillInstructions,
        };
        expect(empty.skillInstructions).not.toBeUndefined();
        expect(Object.keys(empty.skillInstructions!).length).toBe(0);
    });
});
