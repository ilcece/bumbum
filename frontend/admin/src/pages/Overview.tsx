import { useEffect, useState } from "react";
import { PageContainer, ProCard } from "@ant-design/pro-components";
import {
  Alert,
  Button,
  Col,
  Row,
  Select,
  Space,
  Statistic,
  Table,
  Typography,
} from "antd";
import { DataScope } from "../components/TestDataScope";
import { useLocation, history } from "@umijs/max";
import { Link } from "@umijs/max";
import { Row as Record, statistics } from "../catalog";
import "../chart.css";
import { TapDailyChart } from "../TapDailyChart";
export default function Overview() {
  const location = useLocation(),
    q = new URLSearchParams(location.search),
    dataScope = q.get("data_scope") || "business",
    batch = q.get("test_batch_id") || undefined;
  const [scope, setScope] = useState("sold"),
    [range, setRange] = useState("30d"),
    [data, setData] = useState<Record>(),
    [error, setError] = useState(""),
    [retry, setRetry] = useState(0);
  useEffect(() => {
    let live = true;
    setData(undefined);
    statistics({ scope, range, data_scope: dataScope, test_batch_id: batch })
      .then((x) => {
        if (live) {
          setData(x);
          setError("");
        }
      })
      .catch((e) => {
        if (live) setError(e.message);
      });
    return () => {
      live = false;
    };
  }, [scope, range, retry, dataScope, batch]);
  return (
    <PageContainer title={false}>
      <div className="page-stack">
        <DataScope
          scope={dataScope}
          batch={batch ? Number(batch) : undefined}
          onChange={(scope, id) =>
            history.replace({
              pathname: location.pathname,
              search: new URLSearchParams({
                data_scope: scope,
                ...(id ? { test_batch_id: String(id) } : {}),
              }).toString(),
            })
          }
        />
        {dataScope !== "business" && (
          <Alert
            type="warning"
            title="当前统计含测试数据，合成触碰不代表真实读卡。"
          />
        )}
        {dataScope === "business" && data?.counts.items === 0 && (
          <Alert
            type="info"
            title="当前没有业务数据，可切换测试数据进行验收。"
          />
        )}
        <Space>
          <Select
            value={scope}
            onChange={setScope}
            options={[
              { value: "sold", label: "售出后的有效触碰" },
              { value: "all", label: "生命周期全部有效触碰" },
            ]}
          />
          <Select
            value={range}
            onChange={setRange}
            options={[
              { value: "7d", label: "近7天" },
              { value: "30d", label: "近30天" },
              { value: "all", label: "全部时间" },
            ]}
          />
          <Button onClick={() => setRetry((x) => x + 1)}>刷新数据</Button>
        </Space>
        {error && <Alert type="error" title={error} />}
        <ProCard gutter={16} ghost>
          <ProCard>
            <Statistic
              title="有效触碰"
              value={data?.total ?? "—"}
              suffix="次"
            />
          </ProCard>
          <ProCard>
            <Statistic
              title="被触碰物品"
              value={data?.touched_items ?? "—"}
              suffix="件"
            />
          </ProCard>
        </ProCard>
        <ProCard title="档案与持有概况" headerBordered>
          <Row gutter={24}>
            {[
              ["数字身份", data?.counts.items],
              ["芯片", data?.counts.chips],
              ["已确认售出", data?.counts.sold_items],
              ["已建立持有关系", data?.counts.claimed_items],
              ["当前持有人", data?.counts.holders],
            ].map(([k, v]) => (
              <Col key={String(k)} flex={1}>
                <Statistic title={k} value={v ?? "—"} />
              </Col>
            ))}
          </Row>
          <Typography.Paragraph type="secondary">
            账户与持有关系按当前数据范围统计。首次用户认领服务尚未开放，触碰不代表售出或拥有。
          </Typography.Paragraph>
        </ProCard>
        <ProCard title="有效触碰趋势" headerBordered>
          <Typography.Paragraph type="secondary">
            北京时间；有效验签事件按稳定数字身份统计，配置核验与重复读数不计次。
          </Typography.Paragraph>
          {data && (
            <TapDailyChart
              daily={data.daily.map((x: any) => ({
                date: x.day,
                valid_taps: x.total,
              }))}
              today={new Date(data.as_of).toLocaleDateString("sv-SE", {
                timeZone: "Asia/Shanghai",
              })}
            />
          )}
          <Table<Record>
            rowKey="day"
            dataSource={data?.daily}
            size="small"
            pagination={{ pageSize: 10 }}
            columns={[
              { title: "日期", dataIndex: "day" },
              { title: "有效触碰", dataIndex: "total" },
            ]}
          />
        </ProCard>
        <ProCard title="快捷入口">
          <Space>
            <Link to="/catalog">维护款式与发行</Link>
            <Link to="/items">数字物品</Link>
            <Link to="/chips">登记与配置芯片</Link>
          </Space>
        </ProCard>
      </div>
    </PageContainer>
  );
}
