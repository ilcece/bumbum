import { command } from "../catalog";
import type {
  ActionPayloadMap,
  ActionResult,
  CatalogAction,
  FormValues,
  ItemProfile,
} from "../types/catalog";

const fields = {
  legacyProfile: ["item_id", "profile"],
  style: [
    "id",
    "project",
    "code",
    "name",
    "description",
    "material",
    "care_instructions",
    "specs",
    "image_urls",
    "shared_confirmed",
    "test_batch_id",
  ],
  issue: [
    "id",
    "style_id",
    "name",
    "series",
    "mode",
    "total",
    "starts_at",
    "ends_at",
    "counting_rule",
    "description",
  ],
  confirmIssue: ["issue_id", "evidence"],
  deleteIssue: ["issue_id"],
  seal: ["issue_id", "total", "evidence"],
  clearTestBatch: ["batch_id", "confirmed"],
  item: [
    "issue_id",
    "item_uid",
    "edition_number",
    "is_validation",
    "test_batch_id",
  ],
  bind: ["item_id", "chip_id", "spec"],
  createPhysicalItem: [
    "style_id",
    "physical_uid",
    "spec",
    "batch_no",
    "supplier_serial",
  ],
  installAssembly: ["item_id", "physical_item_id", "chip_id", "installed"],
  createOrder: ["channel", "external_order_no", "units", "test_batch_id"],
  matchOrderUnit: ["order_unit_id", "style_id", "spec"],
  orderPhysical: ["order_unit_id", "physical_item_id", "physical"],
  allocateOrderUnit: ["order_unit_id", "item_id"],
  releaseOrderUnit: ["order_unit_id", "evidence"],
  assembleOrderItem: [
    "order_unit_id",
    "issue_id",
    "item_uid",
    "edition_number",
    "physical_item_id",
    "chip_id",
    "installed",
    "is_validation",
  ],
  orderSale: ["order_unit_id", "item_id", "first_sold_at"],
  undoInstall: ["item_id", "whole_id", "evidence", "confirmed"],
  sale: ["item_id", "confirmed", "evidence", "first_sold_at"],
  saleBatch: ["item_ids", "confirmed", "evidence", "first_sold_at"],
  toggleItem: ["item_id", "status"],
  loseItem: ["item_id", "whole_id", "evidence"],
  cancelLoss: ["item_id", "whole_id", "lost_at", "evidence", "chip_state"],
  linkIssue: ["item_id", "issue_id", "edition_number", "evidence"],
  prepare: [
    "item_id",
    "kind",
    "physical_item_id",
    "chip_id",
    "installed",
    "evidence",
    "recipient_id",
    "seller_confirmation",
    "recipient_confirmation",
    "identity_review_required",
    "identity_verification_reference",
  ],
  complete: ["work_id", "evidence", "checked"],
  issueClaimCode: ["item_id", "delivery_reference", "confirmed"],
  reissueClaimCode: ["item_id", "delivery_reference", "confirmed"],
  validationItem: ["item_id", "enabled"],
  deleteItem: ["item_id"],
  validationChip: ["chip_id", "enabled"],
  deleteChip: ["chip_id"],
  register: [
    "chip_uid",
    "project",
    "batch_no",
    "is_validation",
    "test_batch_id",
  ],
  chipBatch: ["chip_id", "batch_no"],
  chipState: ["chip_id", "state", "evidence"],
  receipt: ["request_id"],
} satisfies { [A in CatalogAction]: readonly (keyof ActionPayloadMap[A])[] };
export function pickPayload<A extends CatalogAction>(
  action: A,
  value: FormValues,
): ActionPayloadMap[A] {
  if (action === "legacyProfile") {
    value = {
      ...value,
      profile: {
        ...(value.profile as Partial<ItemProfile>),
        image_urls: [],
      },
    };
  }
  return Object.fromEntries(
    (fields[action] as readonly string[])
      .filter((k) => value[k] !== undefined)
      .map((k) => [k, value[k]]),
  ) as ActionPayloadMap[A];
}

export const readActionReceipt = (requestId: string): Promise<ActionResult> =>
  command("receipt", { request_id: requestId }, crypto.randomUUID());

export const isOrdinaryAction = (action: CatalogAction) =>
  [
    "style",
    "issue",
    "item",
    "register",
    "legacyProfile",
    "chipBatch",
    "createOrder",
    "createPhysicalItem",
  ].includes(action);

export const isDestructiveAction = (action: CatalogAction) =>
  ["deleteItem", "deleteChip", "deleteIssue", "clearTestBatch"].includes(
    action,
  );

export const submitStoredCommand = <A extends CatalogAction>(
  action: A,
  payload: FormValues,
  requestId: string,
): Promise<ActionResult> =>
  command(action, payload as ActionPayloadMap[A], requestId);
