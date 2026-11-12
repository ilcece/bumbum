import { useEffect, useState } from "react";
import { Alert, Button, Card, Descriptions, Drawer, Segmented, Space, Spin, Typography } from "antd";
import { itemFacts } from "../../../shared/itemPresentation";
import { h5Preview } from "../catalog";

type Perspective = "访客" | "待认领" | "持有人";
const claimSteps = ["认领入口", "手机号验证", "输入认领码", "确认认领"];

export default function ItemH5Preview({ id, onClose }: { id: number; onClose: () => void }) {
  const [item, setItem] = useState<Awaited<ReturnType<typeof h5Preview>>>();
  const [error, setError] = useState("");
  const [perspective, setPerspective] = useState<Perspective>("访客");
  const [step, setStep] = useState(0);
  useEffect(() => {
    let active = true;
    h5Preview(id).then((value) => { if (active) setItem(value); })
      .catch((reason) => { if (active) setError(reason.message); });
    return () => { active = false; };
  }, [id]);
  return (
    <Drawer open onClose={onClose} title={`手机页预览${item ? ` · ${item.item_uid}` : ""}`} size={440}>
      <Space orientation="vertical" size="middle" style={{ width: "100%" }}>
        <Alert type="info" showIcon title="只读预览 · 状态与账户为模拟" />
        <Segmented<Perspective> block options={["访客", "待认领", "持有人"]} value={perspective} onChange={(value) => { setPerspective(value); setStep(0); }} />
        {error ? <Alert type="error" title={error} /> : !item ? <Spin /> : (
          <Card size="small" cover={item.image_urls[0] && <img src={item.image_urls[0]} alt={item.name || "物品主图"} style={{ maxHeight: 280, objectFit: "contain" }} />}>
            <Typography.Title level={4}>{item.name || item.item_uid}</Typography.Title>
            <Descriptions size="small" column={1}>
              {itemFacts(item).map((fact) => <Descriptions.Item key={fact.label} label={fact.label}>{fact.value}</Descriptions.Item>)}
              {item.material && <Descriptions.Item label="材质">{item.material}</Descriptions.Item>}
              {item.description && <Descriptions.Item label="介绍">{item.description}</Descriptions.Item>}
              {item.care_instructions && <Descriptions.Item label="洗护说明">{item.care_instructions}</Descriptions.Item>}
            </Descriptions>
            {perspective === "待认领" && <Space orientation="vertical">
              <Typography.Text strong>{claimSteps[step]}</Typography.Text>
              <Typography.Text>{["认领这件物品", "输入手机号和短信验证码", "输入交付时收到的一次性认领码", "确认物品与脱敏手机号 138****0000"][step]}</Typography.Text>
              <Button onClick={() => setStep((step + 1) % claimSteps.length)}>{step < claimSteps.length - 1 ? "查看下一步" : "回到认领入口"}</Button>
            </Space>}
            {perspective === "持有人" && <Descriptions size="small" column={1}>
              <Descriptions.Item label="当前实体">{item.generation ? `第 ${item.generation} 代 · ${item.spec || "规格不适用"}` : "尚未安装"}</Descriptions.Item>
              <Descriptions.Item label="持有人">模拟账户 138****0000</Descriptions.Item>
              <Descriptions.Item label="本年换新用量">{item.quota_review ? "待核对" : `${item.quota_used ?? 0} 次`}</Descriptions.Item>
            </Descriptions>}
          </Card>
        )}
      </Space>
    </Drawer>
  );
}
