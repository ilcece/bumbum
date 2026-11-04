import React, { useMemo, useState } from 'react';
import {
  Alert,
  Badge,
  Button,
  Card,
  Col,
  Divider,
  Empty,
  Input,
  Row,
  Select,
  Space,
  Statistic,
  Switch,
  Table,
  Tag,
  Tooltip,
  Typography,
} from 'antd';
import {
  ArrowRightOutlined,
  CheckCircleOutlined,
  ClearOutlined,
  InfoCircleOutlined,
  KeyOutlined,
  LinkOutlined,
  PlusOutlined,
  ReloadOutlined,
  SearchOutlined,
  ShoppingOutlined,
  SyncOutlined,
  ToolOutlined,
  WarningOutlined,
} from '@ant-design/icons';
import type { ColumnsType } from 'antd/es/table';
import {
  computeTapStatsSnapshot,
  PROJECT_SHORT_LABELS,
  type ChipView,
  type ItemView,
  type ProjectCode,
  type TapEventRecord,
  type TapStatsItemRow,
  type TapStatsQuery,
} from '../data/mockBackend';

const { Text } = Typography;

export type ChipPresetFilter = 'all' | 'pending' | 'bound_unprovisioned' | 'lost';
export type ItemPresetFilter = 'all' | 'draft';

interface OverviewPageProps {
  chips: ChipView[];
  items: ItemView[];
  tapEvents: TapEventRecord[];
  excludeValidationInStats: boolean;
  onToggleExcludeValidationInStats: (val: boolean) => void;
  simulateApiError?: boolean;
  onRecoverApiError?: () => void;
  onNavigate: (page: 'overview' | 'chips' | 'items' | 'audit' | 'checks') => void;
  onNavigateChipsWithPreset: (preset: ChipPresetFilter) => void;
  onNavigateItemsWithPreset: (preset: ItemPresetFilter) => void;
  onOpenItemDetail: (itemId: number) => void;
  onOpenChipDetail: (chipId: number) => void;
  onSimulateNewTap: () => void;
}

const RANGE_LABELS: Record<'7d' | '30d' | 'all', string> = {
  '7d': '近7天（含今日，自然日）',
  '30d': '近30天（含今日，自然日）',
  all: '累计（自首条有效记录起）',
};

export const OverviewPage: React.FC<OverviewPageProps> = ({
  chips,
  items,
  tapEvents,
  excludeValidationInStats,
  onToggleExcludeValidationInStats,
  simulateApiError = false,
  onRecoverApiError,
  onNavigate,
  onNavigateChipsWithPreset,
  onNavigateItemsWithPreset,
  onOpenItemDetail,
  onOpenChipDetail,
  onSimulateNewTap,
}) => {
  // 全局库存独立刷新时间戳
  const [inventoryRefreshedAt, setInventoryRefreshedAt] = useState<string>(() =>
    new Date().toLocaleTimeString('zh-CN', { hour12: false })
  );
  const [inventoryLoading, setInventoryLoading] = useState(false);

  // 有效触碰统计：严格区分“当前下拉输入”与“已生效查询条件（appliedQuery）”
  const [draftProject, setDraftProject] = useState<'' | ProjectCode>('');
  const [draftRange, setDraftRange] = useState<'7d' | '30d' | 'all'>('7d');
  const [draftKeyword, setDraftKeyword] = useState<string>('');

  const [appliedQuery, setAppliedQuery] = useState<TapStatsQuery>({
    project: '',
    range: '7d',
    q: '',
    page: 1,
  });
  const [statsLoading, setStatsLoading] = useState(false);
  const [hoveredBarIndex, setHoveredBarIndex] = useState<number | null>(null);

  const statsSnapshot = useMemo(
    () => computeTapStatsSnapshot(appliedQuery, items, tapEvents, excludeValidationInStats),
    [appliedQuery, items, tapEvents, excludeValidationInStats]
  );

  const scopeDirty = draftProject !== appliedQuery.project || draftRange !== appliedQuery.range;
  const keywordDirty = draftKeyword.trim() !== appliedQuery.q;

  // 全局库存指标（不受下方触碰筛选影响）
  const totalChips = chips.filter((c) => c.chip_status !== 'retired').length;
  const pendingChips = chips.filter((c) => c.chip_status === 'pending' && c.item_id === null).length;
  const boundUnprovisionedChips = chips.filter(
    (c) => c.chip_status === 'bound' && !c.provisioned_at
  ).length;
  const lostChips = chips.filter((c) => c.chip_status === 'lost').length;
  const totalItems = items.length;
  const draftItemsCount = items.filter((i) => i.status === 'draft').length;

  // P2-4：从当前真实数据动态派生待办提醒，避免硬编码芯片 ID 被清理后点击无响应
  const firstPendingNeedBatchOrBindChip = useMemo(
    () =>
      chips.find((c) => c.chip_status === 'pending' && c.item_id === null && !c.batch_no) ||
      chips.find((c) => c.chip_status === 'pending' && c.item_id === null) ||
      null,
    [chips]
  );

  const firstBoundNeedProvisionChip = useMemo(
    () => chips.find((c) => c.chip_status === 'bound' && !c.provisioned_at) || null,
    [chips]
  );

  const handleRefreshInventory = () => {
    setInventoryLoading(true);
    setTimeout(() => {
      setInventoryRefreshedAt(new Date().toLocaleTimeString('zh-CN', { hour12: false }));
      setInventoryLoading(false);
    }, 240);
  };

  const handleApplyScope = () => {
    setStatsLoading(true);
    setTimeout(() => {
      setDraftKeyword('');
      setAppliedQuery({
        project: draftProject,
        range: draftRange,
        q: '',
        page: 1,
      });
      setStatsLoading(false);
    }, 200);
  };

  const handleRefreshStats = () => {
    // 刷新统计只按当前已生效的条件重新获取，不提交尚未查询的下拉选项或关键词
    setStatsLoading(true);
    setTimeout(() => {
      setAppliedQuery((prev) => ({ ...prev }));
      setStatsLoading(false);
    }, 200);
  };

  const handleSearchItems = () => {
    if ([...draftKeyword].length > 128) return;
    setStatsLoading(true);
    setTimeout(() => {
      setAppliedQuery((prev) => ({
        ...prev,
        q: draftKeyword.trim(),
        page: 1,
      }));
      setStatsLoading(false);
    }, 180);
  };

  const handleClearKeyword = () => {
    setDraftKeyword('');
    setAppliedQuery((prev) => ({
      ...prev,
      q: '',
      page: 1,
    }));
  };

  const columns: ColumnsType<TapStatsItemRow> = [
    {
      title: '物品类别',
      dataIndex: 'project',
      key: 'project',
      width: 110,
      render: (project: ProjectCode) => (
        <Tag color={project === 'fashion' ? 'blue' : 'gold'}>{PROJECT_SHORT_LABELS[project]}</Tag>
      ),
    },
    {
      title: '物品编号',
      dataIndex: 'item_uid',
      key: 'item_uid',
      width: 190,
      render: (uid: string, record) => (
        <Space size={6}>
          <Button
            type="link"
            size="small"
            style={{
              padding: 0,
              fontWeight: 600,
            }}
            onClick={() => onOpenItemDetail(record.item_id)}
          >
            {uid}
          </Button>
          <Text copyable={{ text: uid }} />
        </Space>
      ),
    },
    {
      title: '当前物品名称',
      dataIndex: 'name',
      key: 'name',
      render: (name: string | null) =>
        name ? (
          <Text style={{ wordBreak: 'break-word' }}>{name}</Text>
        ) : (
          <Tag color="default">未填写</Tag>
        ),
    },
    {
      title: '有效触碰次数',
      dataIndex: 'valid_taps',
      key: 'valid_taps',
      width: 140,
      align: 'right',
      render: (val: number) => (
        <Text strong style={{ fontSize: 15, color: '#1677ff' }}>
          {val.toLocaleString('zh-CN')} 次
        </Text>
      ),
    },
    {
      title: '最近触碰时间（北京时间）',
      dataIndex: 'last_tap_at',
      key: 'last_tap_at',
      width: 210,
      render: (val: string) => (
        <Text type="secondary" style={{ fontSize: 13 }}>
          {new Date(val).toLocaleString('zh-CN', {
            timeZone: 'Asia/Shanghai',
            hour12: false,
          })}
        </Text>
      ),
    },
  ];

  const maxDailyValue = useMemo(
    () => Math.max(1, ...statsSnapshot.daily.map((d) => d.valid_taps)),
    [statsSnapshot.daily]
  );

  const activePoint =
    hoveredBarIndex !== null && statsSnapshot.daily[hoveredBarIndex]
      ? statsSnapshot.daily[hoveredBarIndex]
      : statsSnapshot.daily[statsSnapshot.daily.length - 1];

  return (
    <div className="space-y-5">
      {simulateApiError && (
        <Alert
          type="error"
          showIcon
          icon={<WarningOutlined />}
          message="工作台统计接口读取失败 (503 Service Unavailable)"
          description="无法从后端获取最新的全局库存与有效触碰统计快照，请检查网络连接或点击右侧按钮重试。"
          action={
            <Button size="small" type="primary" danger onClick={onRecoverApiError}>
              立即重试加载
            </Button>
          }
        />
      )}

      {/* 页面主标题与全局库存概况 */}
      <Card
        size="small"
        title={
          <Space>
            <span>全局库存与配卡待办概况</span>
            <Tag color="blue">点击卡片可带筛选条件直达</Tag>
          </Space>
        }
        extra={
          <Space wrap>
            <Text type="secondary" style={{ fontSize: 12 }}>
              库存更新于 {inventoryRefreshedAt}
            </Text>
            <Button
              size="small"
              icon={<ReloadOutlined spin={inventoryLoading} />}
              onClick={handleRefreshInventory}
            >
              刷新概况
            </Button>
          </Space>
        }
        styles={{ body: { padding: '18px 24px' } }}
      >
        <Row gutter={[16, 16]}>
          <Col xs={24} sm={12} lg={6}>
            <Card
              size="small"
              hoverable
              role="button"
              tabIndex={0}
              aria-label={`有效芯片总数 ${totalChips} 枚，回车查看全部芯片`}
              onClick={() => onNavigateChipsWithPreset('all')}
              onKeyDown={(e) => {
                if (e.key === 'Enter' || e.key === ' ') {
                  e.preventDefault();
                  onNavigateChipsWithPreset('all');
                }
              }}
              style={{ background: '#f8fafc', borderColor: '#e2e8f0' }}
            >
              <Statistic
                title={
                  <Space>
                    <LinkOutlined style={{ color: '#1677ff' }} />
                    <span>有效芯片总数</span>
                    <Tag style={{ marginInlineEnd: 0 }}>全局库存</Tag>
                  </Space>
                }
                value={totalChips}
                suffix="枚"
              />
              <div className="mt-2 flex items-center justify-between text-xs text-slate-500">
                <span>不受下方触碰筛选影响</span>
                <span className="text-blue-600">查看全部芯片 →</span>
              </div>
            </Card>
          </Col>

          <Col xs={24} sm={12} lg={6}>
            <Card
              size="small"
              hoverable
              role="button"
              tabIndex={0}
              aria-label={`待绑定芯片 ${pendingChips} 枚，回车筛选待绑定芯片`}
              onClick={() => onNavigateChipsWithPreset('pending')}
              onKeyDown={(e) => {
                if (e.key === 'Enter' || e.key === ' ') {
                  e.preventDefault();
                  onNavigateChipsWithPreset('pending');
                }
              }}
              style={{ background: '#f0f9ff', borderColor: '#bae6fd' }}
            >
              <Statistic
                title={
                  <Space>
                    <PlusOutlined style={{ color: '#0284c7' }} />
                    <span>待绑定芯片</span>
                    {pendingChips > 0 && <Badge status="processing" />}
                  </Space>
                }
                value={pendingChips}
                suffix="枚"
                valueStyle={{ color: '#0369a1' }}
              />
              <div className="mt-2 flex items-center justify-between text-xs text-slate-500">
                <span>含 NFC.cool 扫码待补录批次</span>
                <span className="text-sky-700">筛选待绑定芯片 →</span>
              </div>
            </Card>
          </Col>

          <Col xs={24} sm={12} lg={6}>
            <Card
              size="small"
              hoverable
              role="button"
              tabIndex={0}
              aria-label={`已绑定待实卡核验 ${boundUnprovisionedChips} 枚，回车筛选待核验芯片`}
              onClick={() => onNavigateChipsWithPreset('bound_unprovisioned')}
              onKeyDown={(e) => {
                if (e.key === 'Enter' || e.key === ' ') {
                  e.preventDefault();
                  onNavigateChipsWithPreset('bound_unprovisioned');
                }
              }}
              style={{ background: '#fffbeb', borderColor: '#fde68a' }}
            >
              <Statistic
                title={
                  <Space>
                    <KeyOutlined style={{ color: '#d97706' }} />
                    <span>已绑定待实卡核验</span>
                  </Space>
                }
                value={boundUnprovisionedChips}
                suffix="枚"
                valueStyle={{ color: '#b45309' }}
              />
              <div className="mt-2 flex items-center justify-between text-xs text-slate-500">
                <span>已关联物品，待生成密钥或双链接核验</span>
                <span className="text-amber-700">筛选待核验芯片 →</span>
              </div>
            </Card>
          </Col>

          <Col xs={24} sm={12} lg={6}>
            <Card
              size="small"
              hoverable
              role="button"
              tabIndex={0}
              aria-label={`数字物品档案共 ${totalItems} 件，其中草稿 ${draftItemsCount} 件，回车筛选草稿物品`}
              onClick={() => onNavigateItemsWithPreset('draft')}
              onKeyDown={(e) => {
                if (e.key === 'Enter' || e.key === ' ') {
                  e.preventDefault();
                  onNavigateItemsWithPreset('draft');
                }
              }}
              style={{ background: '#f8fafc', borderColor: '#e2e8f0' }}
            >
              <Statistic
                title={
                  <Space>
                    <ShoppingOutlined style={{ color: '#1677ff' }} />
                    <span>数字物品档案</span>
                    <Tag style={{ marginInlineEnd: 0 }}>全局库存</Tag>
                  </Space>
                }
                value={totalItems}
                suffix="件"
              />
              <div className="mt-2 flex items-center justify-between text-xs text-slate-500">
                <span>其中草稿状态 {draftItemsCount} 件</span>
                <span className="text-blue-600">筛选草稿物品 →</span>
              </div>
            </Card>
          </Col>
        </Row>

        {/* 待办与快捷操作区 */}
        <Divider style={{ margin: '16px 0 12px' }} />
        <div className="flex flex-wrap items-center justify-between gap-3">
          <Space wrap size={10}>
            <Text strong style={{ fontSize: 13 }}>
              快捷入口：
            </Text>
            <Button type="primary" icon={<LinkOutlined />} onClick={() => onNavigate('chips')}>
              芯片管理
            </Button>
            <Button icon={<ShoppingOutlined />} onClick={() => onNavigate('items')}>
              数字物品管理
            </Button>
            {lostChips > 0 && (
              <Button danger onClick={() => onNavigateChipsWithPreset('lost')}>
                待换新挂失芯片 ({lostChips})
              </Button>
            )}
          </Space>

          <Space wrap size={8}>
            <Text type="secondary" style={{ fontSize: 12 }}>
              实时待办提醒：
            </Text>
            {firstPendingNeedBatchOrBindChip && (
              <Tag
                color="processing"
                className="cursor-pointer"
                onClick={() => onOpenChipDetail(firstPendingNeedBatchOrBindChip.id)}
              >
                芯片 {firstPendingNeedBatchOrBindChip.chip_uid} 待
                {firstPendingNeedBatchOrBindChip.batch_no ? '绑定物品' : '补录批次并绑定'}
              </Tag>
            )}
            {firstBoundNeedProvisionChip && (
              <Tag
                color="warning"
                className="cursor-pointer"
                onClick={() => onOpenChipDetail(firstBoundNeedProvisionChip.id)}
              >
                芯片 {firstBoundNeedProvisionChip.chip_uid} 待完成
                {firstBoundNeedProvisionChip.keys_generated ? '双链接配置核验' : '密钥生成与核验'}
              </Tag>
            )}
            {lostChips > 0 && (
              <Tag
                color="error"
                className="cursor-pointer"
                onClick={() => onNavigateChipsWithPreset('lost')}
              >
                {lostChips} 枚挂失芯片待执行新卡接续
              </Tag>
            )}
            {!firstPendingNeedBatchOrBindChip &&
              !firstBoundNeedProvisionChip &&
              lostChips === 0 && (
                <Tag color="success">当前所有芯片均已完成绑定与核验，无积压待办</Tag>
              )}
          </Space>
        </div>
      </Card>

      {/* 有效触碰统计区（严格遵守 PRD 4.2.2 与 API 8.1） */}
      <Card
        size="small"
        title={
          <Space>
            <span>有效触碰统计</span>
            <Tooltip title="一次有效触碰是服务器通过完整 SUN/SDM 动态验证、接受新读数并成功保存的事件。后台配置核验、失败请求或 24 小时持续查看期间的免碰刷新均不重复计入。">
              <InfoCircleOutlined style={{ color: '#64748b' }} />
            </Tooltip>
          </Space>
        }
        extra={
          <Space size={12} wrap>
            <Space size={6}>
              <span className="text-xs text-slate-500">排除测试对象</span>
              <Switch
                disabled
                size="small"
                checked={excludeValidationInStats}
                onChange={onToggleExcludeValidationInStats}
              />
            </Space>

            <Button
              size="small"
              icon={<SyncOutlined spin={statsLoading} />}
              onClick={handleRefreshStats}
            >
              刷新统计
            </Button>
          </Space>
        }
        styles={{ body: { padding: '20px 24px' } }}
      >
        {/* 统计范围筛选栏 */}
        <div className="flex flex-wrap items-end justify-between gap-4 bg-slate-50 p-4 rounded-lg border border-slate-200/80">
          <Space wrap size={16} align="end">
            <div>
              <div className="text-xs font-medium text-slate-600 mb-1.5">统计类别</div>
              <Select
                style={{ width: 180 }}
                value={draftProject}
                onChange={(val) => setDraftProject(val)}
                options={[
                  { value: '', label: '全部类别 (服装 + 饰品)' },
                  { value: 'fashion', label: '仅看服装 (Fashion)' },
                  { value: 'jewelry', label: '仅看饰品 (Jewelry)' },
                ]}
              />
            </div>
            <div>
              <div className="text-xs font-medium text-slate-600 mb-1.5">统计时间范围</div>
              <Select
                style={{ width: 220 }}
                value={draftRange}
                onChange={(val) => setDraftRange(val)}
                options={[
                  { value: '7d', label: '近7天（含今日，北京自然日）' },
                  { value: '30d', label: '近30天（含今日，北京自然日）' },
                  { value: 'all', label: '累计（自首条有效记录起）' },
                ]}
              />
            </div>
            <Button
              type="primary"
              icon={<SearchOutlined />}
              loading={statsLoading}
              onClick={handleApplyScope}
            >
              查询统计
            </Button>
          </Space>

          <div className="text-xs text-slate-500 space-y-1 text-right">
            <div>
              <Text strong>当前已生效条件：</Text>
              <Tag color="blue" style={{ marginLeft: 4 }}>
                {appliedQuery.project ? PROJECT_SHORT_LABELS[appliedQuery.project] : '全部类别'}
              </Tag>
              <Tag color="geekblue">{RANGE_LABELS[appliedQuery.range]}</Tag>
              <span>
                （区间：{statsSnapshot.period.from_date || '无起始'} 至{' '}
                {statsSnapshot.period.to_date}）
              </span>
            </div>
            <div>
              数据截至：
              <Text code>
                {new Date(statsSnapshot.as_of).toLocaleString('zh-CN', {
                  timeZone: 'Asia/Shanghai',
                  hour12: false,
                })}
              </Text>
              （北京时间）
            </div>
          </div>
        </div>

        {/* 修改下拉但尚未点击查询统计的明确提示（PRD 4.2.2 要求） */}
        {scopeDirty && (
          <Alert
            className="mt-3"
            type="warning"
            showIcon
            message="筛选条件已修改，请点击「查询统计」生效；下方指标、趋势与明细当前仍展示原先已生效条件的数据。"
            action={
              <Button size="small" type="primary" onClick={handleApplyScope}>
                立即生效
              </Button>
            }
          />
        )}

        {/* 两个核心指标卡片 */}
        <Row gutter={[16, 16]} className="mt-4">
          <Col xs={24} sm={12}>
            <div className="p-4 rounded-lg border border-slate-200 bg-white flex items-center justify-between">
              <div>
                <div className="text-xs text-slate-500">
                  所选范围内 · 有效触碰次数
                </div>
                <div className="text-3xl font-bold text-slate-900 mt-1">
                  {statsSnapshot.summary.valid_taps.toLocaleString('zh-CN')}
                  <span className="text-sm font-normal text-slate-500 ml-1.5">次</span>
                </div>
                <div className="text-xs text-slate-500 mt-1">
                  精确整数展示 · 同一动态读数并发/刷新仅计 1 次
                </div>
              </div>
              <div className="w-11 h-11 rounded-full bg-blue-50 text-blue-600 flex items-center justify-center text-lg font-semibold">
                NFC
              </div>
            </div>
          </Col>
          <Col xs={24} sm={12}>
            <div className="p-4 rounded-lg border border-slate-200 bg-white flex items-center justify-between">
              <div>
                <div className="text-xs text-slate-500">
                  所选范围内 · 被触碰物品数
                </div>
                <div className="text-3xl font-bold text-slate-900 mt-1">
                  {statsSnapshot.summary.touched_items.toLocaleString('zh-CN')}
                  <span className="text-sm font-normal text-slate-500 ml-1.5">件</span>
                </div>
                <div className="text-xs text-slate-500 mt-1">
                  同一物品多次触碰计为 1 件 · 非独立用户数、非售后专属统计
                </div>
              </div>
              <div className="w-11 h-11 rounded-full bg-emerald-50 text-emerald-600 flex items-center justify-center">
                <CheckCircleOutlined style={{ fontSize: 20 }} />
              </div>
            </div>
          </Col>
        </Row>

        {/* 每日有效触碰趋势图 */}
        <div className="mt-5 p-4 rounded-lg border border-slate-200 bg-white">
          <div className="flex flex-wrap items-center justify-between gap-2 mb-3">
            <div>
              <Text strong>每日有效触碰趋势</Text>
              <Text type="secondary" className="ml-2 text-xs">
                （按北京时间自然日统计，缺日自动补 0）
              </Text>
            </div>
            {activePoint && (
              <Tag color="blue" style={{ margin: 0 }}>
                {activePoint.date}：{activePoint.valid_taps.toLocaleString('zh-CN')} 次
                {activePoint.date === statsSnapshot.period.to_date ? '（今日未结束）' : ''}
              </Tag>
            )}
          </div>

          {statsSnapshot.daily.length === 0 ? (
            <Empty description="所选时间暂无有效触碰记录" image={Empty.PRESENTED_IMAGE_SIMPLE} />
          ) : (
            <div className="overflow-x-auto pb-2">
              <div
                className="flex items-end gap-2 pt-6 pb-2 px-2"
                style={{ minWidth: Math.max(560, statsSnapshot.daily.length * 28) }}
              >
                {statsSnapshot.daily.map((entry, idx) => {
                  const heightPct = Math.round((entry.valid_taps / maxDailyValue) * 120);
                  const isToday = entry.date === statsSnapshot.period.to_date;
                  const isHovered = hoveredBarIndex === idx;
                  return (
                    <Tooltip
                      key={entry.date}
                      title={`${entry.date}${isToday ? ' (今日未结束)' : ''}：有效触碰 ${entry.valid_taps} 次`}
                    >
                      <div
                        tabIndex={0}
                        onMouseEnter={() => setHoveredBarIndex(idx)}
                        onMouseLeave={() => setHoveredBarIndex(null)}
                        onFocus={() => setHoveredBarIndex(idx)}
                        className="flex-1 flex flex-col items-center group cursor-pointer focus:outline-none"
                      >
                        <span className="text-[11px] text-slate-500 mb-1 font-mono">
                          {entry.valid_taps > 0 ? entry.valid_taps : ''}
                        </span>
                        <div className="w-full h-[124px] bg-slate-100 rounded-t flex items-end justify-center overflow-hidden">
                          <div
                            className="w-full rounded-t transition-all duration-150"
                            style={{
                              height: entry.valid_taps === 0 ? 3 : Math.max(10, heightPct),
                              backgroundColor:
                                entry.valid_taps === 0
                                  ? '#cbd5e1'
                                  : isHovered
                                    ? '#1d4ed8'
                                    : isToday
                                      ? '#3b82f6'
                                      : '#60a5fa',
                            }}
                          />
                        </div>
                        <span
                          className={`text-[11px] mt-1.5 font-mono ${
                            isToday ? 'font-semibold text-blue-600' : 'text-slate-500'
                          }`}
                        >
                          {entry.date.slice(5)}
                        </span>
                      </div>
                    </Tooltip>
                  );
                })}
              </div>
            </div>
          )}
        </div>

        {/* 物品触碰明细表 */}
        <div className="mt-6">
          <div className="flex flex-wrap items-center justify-between gap-3 mb-3">
            <div>
              <Text strong style={{ fontSize: 15 }}>
                物品触碰明细
              </Text>
              <Text type="secondary" className="ml-2 text-xs">
                （关键词仅筛选下方明细表，不影响上方指标卡片与每日趋势）
              </Text>
            </div>

            <Space wrap>
              <Input
                allowClear
                style={{ width: 260 }}
                placeholder="输入物品编号或当前名称筛选明细"
                value={draftKeyword}
                maxLength={128}
                onChange={(e) => setDraftKeyword(e.target.value)}
                onPressEnter={handleSearchItems}
              />
              <Button icon={<SearchOutlined />} onClick={handleSearchItems}>
                查询物品
              </Button>
              {appliedQuery.q && (
                <Button icon={<ClearOutlined />} onClick={handleClearKeyword}>
                  清空关键词
                </Button>
              )}
            </Space>
          </div>

          {keywordDirty && (
            <Alert
              className="mb-3"
              type="info"
              showIcon
              message="明细关键词已输入，请按回车或点击「查询物品」生效。"
            />
          )}

          {appliedQuery.q && (
            <div className="mb-2 text-xs text-slate-600">
              当前生效明细关键词：<Tag color="blue">{appliedQuery.q}</Tag>
            </div>
          )}

          <Table
            rowKey="item_uid"
            size="middle"
            columns={columns}
            dataSource={statsSnapshot.items}
            loading={statsLoading}
            pagination={{
              current: statsSnapshot.page,
              pageSize: 10,
              total: statsSnapshot.total_items,
              showSizeChanger: false,
              showTotal: (total, range) =>
                total > 0 ? `共 ${total} 件被触碰物品（第 ${range[0]}-${range[1]} 件）` : '共 0 件',
              onChange: (nextPage) =>
                setAppliedQuery((prev) => ({
                  ...prev,
                  page: nextPage,
                })),
            }}
            locale={{
              emptyText: appliedQuery.q ? (
                <Empty
                  image={Empty.PRESENTED_IMAGE_SIMPLE}
                  description={
                    <span>
                      没有匹配关键词「{appliedQuery.q}」的被触碰物品（上方全局有效触碰次数仍为{' '}
                      {statsSnapshot.summary.valid_taps} 次）
                    </span>
                  }
                >
                  <Button size="small" onClick={handleClearKeyword}>
                    清空关键词
                  </Button>
                </Empty>
              ) : (
                <Empty
                  image={Empty.PRESENTED_IMAGE_SIMPLE}
                  description="所选时间范围内没有发生过有效触碰的物品"
                />
              ),
            }}
          />

          {/* 常驻口径说明 */}
          <div className="mt-3 p-3 rounded bg-slate-50 border border-slate-200/70 text-xs text-slate-500 flex flex-wrap items-center justify-between gap-2">
            <span>
              <strong>统计口径说明：</strong>
              {statsSnapshot.first_recorded_at
                ? `所选类别首条有效记录时间：${new Date(
                    statsSnapshot.first_recorded_at
                  ).toLocaleString('zh-CN', {
                    timeZone: 'Asia/Shanghai',
                    hour12: false,
                  })}（北京时间）。`
                : '所选类别尚无有效记录。'}{' '}
              不含后台配置核验、重复读数请求及失败请求；24小时持续查看期间刷新页面不增加触碰次数。
            </span>
            <Button
              type="link"
              size="small"
              icon={<ArrowRightOutlined />}
              onClick={() => onNavigate('items')}
            >
              查看全部库存物品
            </Button>
          </div>
        </div>
      </Card>
    </div>
  );
};
