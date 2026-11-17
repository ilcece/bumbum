import { useEffect, useRef, useState } from "react";
import { read } from "../catalog";
import type { DetailMap, DetailResource } from "../types/catalog";

export function useCatalogRecord<R extends DetailResource>(
  resource: R,
  id?: number,
) {
  const [record, setRecord] = useState<DetailMap[R]>(),
    [error, setError] = useState(""),
    [loading, setLoading] = useState(false),
    [rev, setRev] = useState(0),
    seq = useRef(0),
    identity = useRef("");
  useEffect(() => {
    const n = ++seq.current;
    const nextIdentity = `${resource}:${id}`;
    if (identity.current !== nextIdentity) setRecord(undefined);
    identity.current = nextIdentity;
    setError("");
    if (id === undefined) return;
    if (!Number.isSafeInteger(id) || id < 1 || id > 2147483647) {
      setError("记录编号无效或超出页面可处理范围。");
      return;
    }
    setLoading(true);
    read(resource, id)
      .then((v) => {
        if (n === seq.current) setRecord(v);
      })
      .catch((e) => {
        if (n === seq.current) setError(e.message);
      })
      .finally(() => {
        if (n === seq.current) setLoading(false);
      });
  }, [resource, id, rev]);
  const shownRecord =
    identity.current === `${resource}:${id}` ? record : undefined;
  return {
    record: shownRecord,
    error,
    loading: loading && !shownRecord,
    reload: () => setRev((n) => n + 1),
  };
}
