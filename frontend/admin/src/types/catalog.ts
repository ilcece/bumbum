import type { ItemFacts } from "../../../shared/itemPresentation";

export type Project = "fashion" | "jewelry";
export type ItemStatus = "draft" | "active" | "disabled" | "archived";
export type ChipStatus = "pending" | "bound" | "disabled" | "lost" | "retired";
export type HandoverKind = "periodic" | "loss" | "resale";
export type ItemWorkflow =
  | "assembly"
  | "verification"
  | "available"
  | "delivery"
  | "claim"
  | "activation"
  | "allocation"
  | "sale"
  | "held"
  | "missing_issue"
  | "review"
  | "archived"
  | "lost"
  | "disabled";
export type QueryValue = string | number | boolean | null | undefined;
export type CatalogQuery = Record<string, QueryValue>;
export type FormValues = Record<string, unknown>;

export type ItemProfile = {
  name: string;
  description: string | null;
  material: string | null;
  care_instructions: string | null;
  meaning?: string | null;
  image_urls: string[];
};
export type DigitalRight = { kind: "renewal" | "resale"; rule_version: string };
export type ClaimCodeStatus = {
  id: number;
  issued_at?: string;
  expires_at: string;
  consumed_at: string | null;
  revoked_at: string | null;
};
export type AuditSnapshot = {
  status?: ItemStatus;
  generation?: number;
  physical_uid?: string;
  chip_uid?: string;
  chip_status?: ChipStatus;
  user_uid?: string;
  lost_at?: string | null;
  sold?: boolean | number;
  first_sold_at?: string | null;
  quota_review?: boolean | number;
  quota_year?: number | null;
  quota_used?: number | null;
};
export type AuditDetail = {
  evidence?: string;
  external_order_no?: string;
  work_id?: number;
  candidate?: AuditSnapshot;
  before?: AuditSnapshot;
  after?: AuditSnapshot;
  source?: string;
  key_version?: number;
  expires_at?: string;
  removed?: Record<string, number>;
};
export type TestManifest = {
  warning?: string;
  expected_initial?: {
    items: number;
    lifecycle_taps: number;
    sold_taps: number;
  };
  items?: { item_id: number; uid: string; scenario: string }[];
  photos?: {
    sha256: string;
    page: string;
    style_name: string;
    artist: string;
    license: string;
  }[];
};

export interface CatalogRow {
  id: number | string;
  name?: string | null;
  code?: string;
  project?: Project | null;
  status?: ItemStatus | "deleted";
  created_at?: string;
  updated_at?: string;
  test_batch_id?: number | null;
  image_urls?: string[];
  description?: string | null;
  material?: string | null;
  care_instructions?: string | null;
  specs?: string[];
  style_id?: number | null;
  style_name?: string;
  style_code?: string;
  issue_id?: number | null;
  issue_name?: string | null;
  issue_total?: number | null;
  edition_number?: number | null;
  mode?: "fixed" | "period" | "unlimited";
  total?: number | null;
  starts_at?: string | null;
  ends_at?: string | null;
  confirmed_at?: string | null;
  sealed_at?: string | null;
  counting_rule?: string | null;
  seal_evidence?: string | null;
  item_count?: number;
  active_item_count?: number;
  issue_count?: number;
  ever_used?: boolean | number;
  item_id?: number | null;
  item_uid?: string | null;
  chip_id?: number | null;
  chip_uid?: string | null;
  chip_status?: ChipStatus;
  batch_no?: string | null;
  registration_source?: "unknown" | "manual" | "nfc_cool";
  provisioned_at?: string | null;
  keys_generated?: boolean | number;
  is_validation?: boolean | number;
  candidate_id?: number | null;
  candidate_item_id?: number | null;
  physical_item_id?: number | null;
  physical_uid?: string | null;
  supplier_serial?: string | null;
  assembly_status?: "installed" | "prepared" | "replaced" | "available";
  spec?: string | null;
  workflow?: ItemWorkflow;
  generation?: number;
  lost_at?: string | null;
  loss_evidence?: string | null;
  ended_at?: string | null;
  started_at?: string;
  installed_at?: string | null;
  sold?: boolean | number;
  first_sold_at?: string | null;
  sale_evidence?: string | null;
  owner_id?: string | null;
  owner_name?: string | null;
  owner_public_uid?: string | null;
  owner_phone_verified?: boolean | number;
  quota_year?: number | null;
  quota_used?: number | null;
  quota_review?: boolean | number;
  order_id?: number | null;
  order_unit_id?: number | null;
  external_order_no?: string;
  channel?: string;
  unit_count?: number;
  delivered_count?: number;
  position?: number;
  product_name?: string;
  ordered_spec?: string | null;
  expected_style_id?: number | null;
  expected_style_name?: string | null;
  expected_spec?: string | null;
  physical_style_name?: string | null;
  physical_matches?: boolean | number | null;
  item_status?: ItemStatus | null;
  whole_id?: number | null;
  allocated_at?: string | null;
  delivered_at?: string | null;
  delivered_generation?: number | null;
  delivered_spec?: string | null;
  delivered_physical_uid?: string | null;
  delivered_chip_uid?: string | null;
  holder_uid?: string | null;
  first_delivery_reference?: string | null;
  claim_code_id?: number | null;
  claim_expires_at?: string | null;
  claim_consumed_at?: string | null;
  claim_revoked_at?: string | null;
  public_uid?: string;
  user_uid?: string | null;
  nickname?: string | null;
  phone?: string | null;
  masked_phone?: string | null;
  held_items?: number;
  username?: string | null;
  action?: string;
  operation?: string;
  object_code?: string | null;
  object_exists?: boolean | number;
  target_id?: number | string;
  outcome?: string | null;
  summary?: string | null;
  detail?: AuditDetail;
  event?: "tap" | "claim" | "first_delivery" | "renewal" | "resale";
  occurred_at?: string;
  actor_state?: string | null;
  manifest?: TestManifest;
}

export interface StyleRecord extends Pick<
  CatalogRow,
  "created_at" | "updated_at" | "test_batch_id"
> {
  name: string;
  description: string | null;
  material: string | null;
  care_instructions: string | null;
  image_urls: string[];
  id: number;
  code: string;
  project: Project;
  specs: string[];
  issue_count: number;
  item_count: number;
  active_item_count: number;
}
export interface IssueRecord extends Pick<
  CatalogRow,
  | "created_at"
  | "updated_at"
  | "test_batch_id"
  | "description"
  | "counting_rule"
  | "seal_evidence"
  | "ever_used"
> {
  id: number;
  name: string;
  style_id: number;
  project: Project;
  series: string | null;
  style_name: string;
  style_code: string;
  mode: "fixed" | "period" | "unlimited";
  total: number | null;
  confirmed_at: string | null;
  sealed_at: string | null;
  starts_at: string | null;
  ends_at: string | null;
  item_count: number;
  suggested_edition_number?: number;
  suggested_item_uid?: string;
}
export interface ChipRecord extends Pick<
  CatalogRow,
  "created_at" | "updated_at" | "test_batch_id" | "is_validation"
> {
  id: number;
  chip_uid: string;
  chip_status: ChipStatus;
  project: Project | null;
  item_id: number | null;
  item_uid: string | null;
  batch_no: string | null;
  registration_source: "unknown" | "manual" | "nfc_cool";
  provisioned_at: string | null;
  keys_generated: boolean | number;
  candidate_id: number | null;
  candidate_item_id: number | null;
}
export interface PhysicalItemRecord extends Pick<
  CatalogRow,
  | "created_at"
  | "updated_at"
  | "test_batch_id"
  | "assembly_status"
  | "item_id"
  | "order_id"
  | "order_unit_id"
> {
  id: number;
  style_id: number;
  physical_uid: string;
  style_name: string;
  spec: string | null;
  batch_no: string | null;
  supplier_serial: string | null;
}
export interface WholeRecord extends Pick<
  CatalogRow,
  "physical_item_id" | "physical_uid" | "chip_status" | "spec" | "installed_at"
> {
  id: number;
  item_id: number;
  chip_id: number;
  chip_uid: string;
  generation: number;
  started_at: string;
  ended_at: string | null;
  lost_at: string | null;
  loss_evidence: string | null;
  spec: string | null;
}
export interface HandoverRecord extends Pick<
  CatalogRow,
  | "created_at"
  | "physical_item_id"
  | "physical_uid"
  | "spec"
  | "provisioned_at"
  | "owner_id"
  | "owner_name"
  | "owner_public_uid"
> {
  id: number;
  item_id: number;
  chip_id: number;
  chip_uid: string;
  kind: HandoverKind;
  generation: number;
  source_id: number;
  target_id?: number;
  completed_at: string | null;
  prepare_evidence: string;
  recipient_name: string | null;
  recipient_public_uid: string | null;
}
export interface OwnershipRecord extends Pick<CatalogRow, "nickname"> {
  id: number;
  user_id: string;
  public_uid: string;
  masked_phone: string | null;
  is_active: boolean | number;
  bound_at: string;
  unbound_at: string | null;
}
export interface OrderUnit extends Pick<
  CatalogRow,
  | "created_at"
  | "test_batch_id"
  | "spec"
  | "style_id"
  | "physical_uid"
  | "physical_style_name"
  | "expected_style_id"
  | "expected_style_name"
  | "expected_spec"
  | "physical_matches"
  | "item_status"
  | "item_uid"
  | "whole_id"
  | "generation"
  | "chip_id"
  | "provisioned_at"
  | "chip_status"
  | "lost_at"
  | "loss_evidence"
  | "sold"
  | "first_sold_at"
  | "allocated_at"
  | "delivered_at"
  | "delivered_generation"
  | "delivered_spec"
  | "delivered_physical_uid"
  | "delivered_chip_uid"
  | "holder_uid"
  | "first_delivery_reference"
  | "claim_code_id"
  | "claim_expires_at"
  | "claim_consumed_at"
  | "claim_revoked_at"
> {
  id: number;
  order_id: number;
  position: number;
  product_name: string;
  channel: string;
  external_order_no: string;
  ordered_spec: string | null;
  physical_item_id: number | null;
  item_id: number | null;
  physical_matches: boolean | number | null;
}
export interface OrderRecord extends Pick<
  CatalogRow,
  "created_at" | "test_batch_id"
> {
  id: number;
  channel: string;
  external_order_no: string;
  units: OrderUnit[];
}
export interface ItemSummary extends Pick<
  CatalogRow,
  | "name"
  | "material"
  | "image_urls"
  | "created_at"
  | "updated_at"
  | "test_batch_id"
  | "issue_name"
  | "issue_total"
  | "edition_number"
  | "sold"
  | "first_sold_at"
  | "sale_evidence"
  | "is_validation"
  | "quota_year"
  | "quota_review"
  | "physical_item_id"
  | "physical_uid"
  | "installed_at"
  | "owner_id"
  | "owner_name"
  | "owner_phone_verified"
  | "owner_public_uid"
  | "whole_id"
  | "generation"
  | "spec"
  | "lost_at"
  | "loss_evidence"
  | "chip_id"
  | "chip_uid"
  | "chip_status"
  | "provisioned_at"
  | "keys_generated"
  | "workflow"
  | "order_unit_id"
> {
  id: number;
  item_uid: string;
  project: Project;
  status: ItemStatus;
  style_id: number | null;
  issue_id: number | null;
  quota_used: number | null;
}
export interface ItemRecord extends ItemSummary {
  wholes: WholeRecord[];
  handovers: HandoverRecord[];
  owners: OwnershipRecord[];
  rights: DigitalRight[];
  audit: AuditRecord[];
  order: OrderUnit | null;
  claim_code_status: ClaimCodeStatus | null;
  chip_state_before_loss?: "bound" | "disabled" | null;
  style?: StyleRecord;
  issue?: IssueRecord;
  legacy_profile?: ItemProfile | null;
}
export type OrderSummary = Pick<CatalogRow, "created_at" | "test_batch_id"> & {
  id: number;
  channel: string;
  external_order_no: string;
  unit_count: number;
  delivered_count: number;
};
export interface AuditRecord extends Pick<
  CatalogRow,
  | "username"
  | "operation"
  | "object_code"
  | "object_exists"
  | "outcome"
  | "summary"
> {
  id: number;
  action: string;
  created_at: string;
  target_id: string;
  detail: AuditDetail;
}
export interface ActivityRecord extends Pick<
  CatalogRow,
  "user_uid" | "actor_state" | "issue_id"
> {
  id: string;
  item_id: number;
  item_uid: string;
  event: "tap" | "claim" | "first_delivery" | "renewal" | "resale";
  occurred_at: string;
}
export interface TestBatchRecord extends Pick<
  CatalogRow,
  "created_at" | "updated_at"
> {
  id: number;
  name: string;
  code: string;
  status: "active" | "deleted";
  manifest: TestManifest;
}
export type TestBatchPreview = {
  id: number;
  counts: Record<string, number>;
  conflicts: unknown[];
  objects: unknown;
};
export type UserRecord = CatalogRow & { id: string; public_uid: string };
export type ResourceMap = {
  styles: StyleRecord;
  issues: IssueRecord;
  items: ItemSummary;
  chips: ChipRecord;
  "physical-items": PhysicalItemRecord;
  orders: OrderSummary;
  users: UserRecord;
  activity: ActivityRecord;
  audit: AuditRecord;
  "test-batches": TestBatchRecord;
};
export type DetailMap = Omit<ResourceMap, "items" | "orders"> & {
  items: ItemRecord;
  orders: OrderRecord;
};
export type CatalogResource = keyof ResourceMap;
export type DetailResource =
  "styles" | "issues" | "items" | "chips" | "physical-items" | "orders";
export type Page<T extends CatalogRow = CatalogRow> = {
  items: T[];
  total: number;
  page: number;
  page_size: number;
  total_pages?: number;
  page_adjusted?: boolean;
  writable?: boolean;
};
export type StatisticsItem = CatalogRow & {
  id: number;
  item_uid: string;
  tap_count: number;
  last_tap: string | null;
};
export type CatalogStatistics = {
  total: number;
  touched_items: number;
  as_of: string;
  timezone: "Asia/Shanghai";
  scope: "sold" | "all";
  range: "7d" | "30d" | "all";
  touch_item_counts: Record<"touched" | "repeat", number> &
    Partial<Record<"zero" | "missing_sale", number>>;
  workflow_counts: Record<ItemWorkflow, number>;
  daily: { day: string; total: number }[];
  by_chip: { chip_id: number; chip_uid: string; total: number }[];
  counts: {
    items: number;
    sold_items: number;
    claimed_items: number;
    holders: number;
    chips: number;
    users: number;
  };
  inventory: {
    items: number;
    active_items: number;
    pending_chips: number;
    unconfigured_chips: number;
  };
  details: Page<StatisticsItem>;
  holders: Page<UserRecord>;
  claim_service_available: boolean;
};
export type H5Preview = ItemFacts &
  ItemProfile & {
    id: number;
    item_uid: string;
    generation: number | null;
    spec: string | null;
    quota_year: number | null;
    quota_used: number | null;
    quota_review: boolean | number;
  };

export type Source = { test_batch_id?: number };
export type EvidencePayload = { evidence: string };
export type PhysicalPayload = {
  style_id: number;
  physical_uid: string;
  spec?: string | null;
  batch_no?: string | null;
  supplier_serial?: string | null;
};
export type ItemPayload = Source & {
  issue_id: number;
  item_uid: string;
  edition_number?: number | null;
  is_validation?: boolean;
};
export type AssemblyPayload = {
  physical_item_id: number;
  chip_id: number;
  installed: boolean;
};
export type ClaimPayload = {
  item_id: number;
  delivery_reference: string;
  confirmed: boolean;
};
export type ActionPayloadMap = {
  legacyProfile: { item_id: number; profile: ItemProfile };
  style: Source &
    ItemProfile & {
      id?: number;
      project: Project;
      code: string;
      specs: string[];
      shared_confirmed?: boolean;
    };
  issue: {
    id?: number;
    style_id: number;
    name: string;
    series?: string;
    mode: IssueRecord["mode"];
    total?: number;
    starts_at?: string;
    ends_at?: string;
    counting_rule?: string;
    description?: string;
  };
  confirmIssue: EvidencePayload & { issue_id: number };
  deleteIssue: { issue_id: number };
  seal: EvidencePayload & { issue_id: number; total: number };
  clearTestBatch: { batch_id: number; confirmed: boolean };
  item: ItemPayload;
  bind: { item_id: number; chip_id: number; spec?: string };
  createPhysicalItem: PhysicalPayload;
  installAssembly: AssemblyPayload & { item_id: number };
  createOrder: Source & {
    channel: string;
    external_order_no: string;
    units: { product_name: string; ordered_spec?: string }[];
  };
  matchOrderUnit: { order_unit_id: number; style_id: number; spec?: string };
  orderPhysical: {
    order_unit_id: number;
    physical_item_id?: number;
    physical?: PhysicalPayload;
  };
  allocateOrderUnit: { order_unit_id: number; item_id: number };
  releaseOrderUnit: EvidencePayload & { order_unit_id: number };
  assembleOrderItem: ItemPayload & AssemblyPayload & { order_unit_id?: number };
  orderSale: {
    order_unit_id?: number;
    item_id?: number;
    first_sold_at?: string;
  };
  undoInstall: EvidencePayload & {
    item_id: number;
    whole_id: number;
    confirmed: boolean;
  };
  sale: EvidencePayload & {
    item_id: number;
    confirmed: boolean;
    first_sold_at?: string;
  };
  saleBatch: EvidencePayload & {
    item_ids: number[];
    confirmed: boolean;
    first_sold_at?: string;
  };
  toggleItem: { item_id: number; status: "active" | "disabled" };
  loseItem: EvidencePayload & { item_id: number; whole_id: number };
  cancelLoss: EvidencePayload & {
    item_id: number;
    whole_id: number;
    lost_at: string | null;
    chip_state: "bound" | "disabled";
  };
  linkIssue: EvidencePayload & {
    item_id: number;
    issue_id: number;
    edition_number?: number;
  };
  prepare: EvidencePayload &
    AssemblyPayload & {
      item_id: number;
      kind: HandoverKind;
      recipient_id?: string;
      seller_confirmation?: string;
      recipient_confirmation?: string;
      identity_review_required?: boolean;
      identity_verification_reference?: string;
    };
  complete: EvidencePayload & { work_id: number; checked: boolean };
  issueClaimCode: ClaimPayload;
  reissueClaimCode: ClaimPayload;
  validationItem: { item_id: number; enabled: boolean };
  deleteItem: { item_id: number };
  validationChip: { chip_id: number; enabled: boolean };
  deleteChip: { chip_id: number };
  register: Source & {
    chip_uid: string;
    project?: Project | null;
    batch_no?: string | null;
    is_validation?: boolean;
  };
  chipBatch: { chip_id: number; batch_no: string | null };
  chipState: EvidencePayload & {
    chip_id: number;
    state: "disabled" | "restore";
  };
  receipt: { request_id: string };
};
export type CatalogAction = keyof ActionPayloadMap;
export type ActionResult = {
  id: number;
  status?: ItemStatus | "deleted";
  claim_code?: string;
  expires_at?: string;
  physical_uid?: string;
  work_id?: number;
  removed?: Record<string, number>;
  image_urls?: string[];
  order_id?: number;
  order_unit_id?: number;
  external_order_no?: string;
};

export type StatisticsResult = CatalogStatistics;
