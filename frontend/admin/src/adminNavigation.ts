import type { Location } from "react-router-dom";
import { CHIP_FILTERS } from "./api";

export type ReturnPoint = { path: string; scroll?: number; parent?: ReturnPoint };
const PATH = /^\/(?:chips|items)(?:\/[1-9][0-9]*(?:\/edit)?)?$/;
const PARAMETERS = new Set<string>([...CHIP_FILTERS, "page", "page_size", "has_chip", "unbound_only", "sku_code"]);

export function safeReturn(value: unknown, depth = 0): ReturnPoint | undefined {
  if (!value || typeof value !== "object" || depth > 4) return;
  const point = value as ReturnPoint;
  if (typeof point.path !== "string" || point.path.length > 4096) return;
  const [pathname, search = ""] = point.path.split("?");
  if (!PATH.test(pathname) || point.path.includes("#")) return;
  const query = new URLSearchParams(search);
  if ([...query.keys()].some(key => !PARAMETERS.has(key))) return;
  return { path: pathname + (search ? "?" + query : ""),
    scroll: typeof point.scroll === "number" && Number.isFinite(point.scroll) && point.scroll >= 0 ? point.scroll : 0,
    parent: safeReturn(point.parent, depth + 1) };
}

export function sourcePoint(location: Location): ReturnPoint {
  return { path: location.pathname + location.search, scroll: window.scrollY, parent: safeReturn(location.state?.returnTo) };
}
