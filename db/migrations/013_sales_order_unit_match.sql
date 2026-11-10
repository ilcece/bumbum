-- 保留订单原文与历史分配，逐件保存人工核对的目录款式和规格。
CREATE TABLE sales_order_unit_match (
 unit_id BIGINT UNSIGNED PRIMARY KEY,
 style_id BIGINT UNSIGNED NOT NULL,
 spec VARCHAR(256) NULL,
 CONSTRAINT fk_order_match_unit FOREIGN KEY(unit_id) REFERENCES sales_order_unit(id) ON DELETE CASCADE,
 CONSTRAINT fk_order_match_style FOREIGN KEY(style_id) REFERENCES product_style(id)
) COMMENT='订单件已核对的履约目标';
