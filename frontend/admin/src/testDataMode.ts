// 仅保存本标签页的验收显示偏好，不保存认证资料或改变对象来源。
const key = "bumbum-admin-test-batch";
export function testBatch(): number | undefined {
  const value = sessionStorage.getItem(key);
  return value &&
    /^[1-9]\d*$/.test(value) &&
    Number.isSafeInteger(Number(value))
    ? Number(value)
    : undefined;
}
export function dataScope() {
  const batch = testBatch();
  return batch
    ? { data_scope: "test", test_batch_id: batch }
    : { data_scope: "business", test_batch_id: undefined };
}
export function setTestBatch(batch?: number) {
  if (batch) sessionStorage.setItem(key, String(batch));
  else sessionStorage.removeItem(key);
  // 切换只在设置执行，整页重新读取，避免保留上一范围的列表或候选数据。
  window.location.assign("/system?tab=settings");
}
