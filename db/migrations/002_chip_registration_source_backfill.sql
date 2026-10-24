-- 仅凭唯一一条首次登记记录补齐来源；歧义记录保持未知，不刷新登记或更新时间。
UPDATE chip c
JOIN (
  SELECT target_id, MAX(JSON_UNQUOTE(JSON_EXTRACT(detail,'$.source'))) AS source
  FROM admin_audit WHERE action='chip.register' AND target_type='chip'
  GROUP BY target_id
  HAVING COUNT(*)=1 AND MAX(JSON_UNQUOTE(JSON_EXTRACT(detail,'$.source'))) IN ('manual','nfc_cool')
) a ON a.target_id=CAST(c.id AS CHAR)
SET c.registration_source=a.source,c.updated_at=c.updated_at
WHERE c.registration_source='unknown';
