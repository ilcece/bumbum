import { ProCard } from "@ant-design/pro-components";
import { ArrowRightOutlined } from "@ant-design/icons";
import { Statistic } from "antd";

type MetricAction = { label: string; run: () => void };

export default function MetricCard({ title, value, unit, note, action }: {
  title: string;
  value?: number;
  unit: string;
  note?: string;
  action?: MetricAction;
}) {
  return <ProCard size="small" variant="outlined" className="metric-card">
    <Statistic title={title} value={value ?? "—"} suffix={value == null ? undefined : unit} />
    <div className="metric-card-caption">
      <span>{action?.label || note}</span>
      {action && <ArrowRightOutlined aria-hidden />}
    </div>
    {action && <button type="button" className="metric-card-action"
      aria-label={title + "，" + (value == null ? "数据未就绪" : value + unit) + "，" + action.label}
      onClick={action.run} />}
  </ProCard>;
}
