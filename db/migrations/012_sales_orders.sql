-- 订单逐件履约，仅新增结构，保留已有成交依据。
CREATE TABLE sales_order (
 id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
 test_batch_id BIGINT UNSIGNED NULL,
 source_scope BIGINT UNSIGNED GENERATED ALWAYS AS (COALESCE(test_batch_id,0)) STORED,
 channel VARCHAR(40) NOT NULL,
 external_order_no VARCHAR(64) NOT NULL,
 created_by BIGINT UNSIGNED NOT NULL,
 created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
 UNIQUE KEY uk_sales_order_source(source_scope,channel,external_order_no),
 CONSTRAINT fk_sales_order_batch FOREIGN KEY(test_batch_id) REFERENCES test_batch(id),
 CONSTRAINT fk_sales_order_admin FOREIGN KEY(created_by) REFERENCES admin_user(id)
) COMMENT='待履约订单与原始渠道来源';

CREATE TABLE sales_order_unit (
 id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
 order_id BIGINT UNSIGNED NOT NULL,
 position SMALLINT UNSIGNED NOT NULL,
 product_name VARCHAR(128) NOT NULL,
 ordered_spec VARCHAR(256) NULL,
 physical_item_id BIGINT UNSIGNED NULL UNIQUE,
 item_id BIGINT UNSIGNED NULL UNIQUE,
 allocated_at DATETIME(6) NULL,
 delivered_at DATETIME(6) NULL,
 delivery_whole_id BIGINT UNSIGNED NULL,
 first_claim_code_id BIGINT UNSIGNED NULL,
 UNIQUE KEY uk_order_unit_position(order_id,position),
 CONSTRAINT fk_order_unit_order FOREIGN KEY(order_id) REFERENCES sales_order(id) ON DELETE CASCADE,
 CONSTRAINT fk_order_unit_physical FOREIGN KEY(physical_item_id) REFERENCES physical_item(id),
 CONSTRAINT fk_order_unit_item FOREIGN KEY(item_id) REFERENCES item(id),
 CONSTRAINT fk_order_unit_delivery FOREIGN KEY(delivery_whole_id) REFERENCES whole_item(id),
 CONSTRAINT fk_order_unit_claim FOREIGN KEY(first_claim_code_id) REFERENCES item_claim_code(id)
) COMMENT='订单逐件准备、分配与首次交付，解除占用留审计';
