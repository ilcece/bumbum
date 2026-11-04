import React, { useEffect, useMemo, useState } from 'react';
import {
  Alert,
  Button,
  Card,
  Checkbox,
  Col,
  Descriptions,
  Input,
  Modal,
  Radio,
  Row,
  Select,
  Space,
  Steps,
  Switch,
  Table,
  Tabs,
  Tag,
  Tooltip,
  Typography,
  message,
} from 'antd';
import {
  AuditOutlined,
  ClearOutlined,
  DeleteOutlined,
  LockOutlined,
  RetweetOutlined,
  StopOutlined,
  SwapOutlined,
  ToolOutlined,
} from '@ant-design/icons';
import {
  CHIP_STATUS_META,
  evaluateChipLifecycleLevel,
  ITEM_STATUS_META,
  PROJECT_SHORT_LABELS,
  validateItemUid,
  type AuditLogEntry,
  type ChipView,
  type ItemView,
  type ProjectCode,
  type TapEventRecord,
} from '../data/mockBackend';

const { Text } = Typography;

interface WorkflowGovernancePageProps {
  activeTab: 'cleanup' | 'correction' | 'replacement' | 'audit';
  onTabChange: (tab: 'cleanup' | 'correction' | 'replacement' | 'audit') => void;
  focusTarget?: {
    tab: 'cleanup' | 'correction' | 'replacement';
    chipId?: number;
    itemId?: number;
    nonce: number;
  } | null;
  chips: ChipView[];
  items: ItemView[];
  tapEvents: TapEventRecord[];
  auditLogs: AuditLogEntry[];
  excludeValidationInStats: boolean;
  onToggleExcludeValidationInStats: (val: boolean) => void;
  onOpenChipDetail: (chipId: number) => void;
  onOpenItemDetail: (itemId: number) => void;
  onDeleteL1Chip: (chipId: number, reason: string) => { ok: boolean; error?: string };
  onDeleteL1Item: (itemId: number, reason: string) => { ok: boolean; error?: string };
  onExitL2ValidationChip: (chipId: number, reason: string) => { ok: boolean; error?: string };
  onCorrectPendingChipProject: (
    chipId: number,
    newProject: ProjectCode | null,
    reason: string
  ) => { ok: boolean; error?: string };
  onCorrectItemIdentity: (
    itemId: number,
    newProject: ProjectCode,
    newItemUid: string,
    reason: string
  ) => { ok: boolean; error?: string };
  onUnbindOrRebindMisboundChip: (
    chipId: number,
    mode: 'unbind_to_pending' | 'rebind_to_target',
    targetItemId: number | null,
    reason: string
  ) => { ok: boolean; error?: string };
  onReportChipLost: (chipId: number, reason: string) => { ok: boolean; error?: string };
  onExecuteCarrierReplacement: (payload: {
    itemId: number;
    newChipId: number;
    scenario: 'loss_replacement' | 'resale_new_carrier';
    reason: string;
  }) => { ok: boolean; error?: string };
}

export const WorkflowGovernancePage: React.FC<WorkflowGovernancePageProps> = ({
  activeTab,
  onTabChange,
  focusTarget,
  chips,
  items,
  tapEvents,
  auditLogs,
  excludeValidationInStats,
  onToggleExcludeValidationInStats,
  onOpenChipDetail,
  onOpenItemDetail,
  onDeleteL1Chip,
  onDeleteL1Item,
  onExitL2ValidationChip,
  onCorrectPendingChipProject,
  onCorrectItemIdentity,
  onUnbindOrRebindMisboundChip,
  onReportChipLost,
  onExecuteCarrierReplacement,
}) => {
  // P1-4：B 工作流受控确认弹窗状态（原因初始留空，不预填模板，且需勾选确认）
  const [cleanupModalState, setCleanupModalState] = useState<{
    kind: 'l1_chip' | 'l2_chip' | 'l1_item';
    targetId: number;
    targetUid: string;
  } | null>(null);
  const [cleanupReason, setCleanupReason] = useState('');
  const [cleanupConfirmAck, setCleanupConfirmAck] = useState(false);

  const [corrSubMode, setCorrSubMode] = useState<'misbind' | 'chip_project' | 'item_identity'>(
    'misbind'
  );
  const [selectedMisboundChipId, setSelectedMisboundChipId] = useState<number | null>(107);
  const [misbindActionType, setMisbindActionType] = useState<
    'unbind_to_pending' | 'rebind_to_target'
  >('unbind_to_pending');
  const [misbindTargetItemId, setMisbindTargetItemId] = useState<number | null>(null);
  const [misbindReason, setMisbindReason] = useState('');
  const [misbindConfirmAck, setMisbindConfirmAck] = useState(false);

  const [selectedPendingChipId, setSelectedPendingChipId] = useState<number | null>(109);
  const [targetChipProject, setTargetChipProject] = useState<'' | ProjectCode>('');
  const [chipProjReason, setChipProjReason] = useState('');

  const [selectedDraftItemId, setSelectedDraftItemId] = useState<number | null>(6);
  const [corrItemProject, setCorrItemProject] = useState<ProjectCode>('fashion');
  const [corrItemUidInput, setCorrItemUidInput] = useState('FASH-2026-000008');
  const [corrItemReason, setCorrItemReason] = useState('');

  const [selectedCarrierItemId, setSelectedCarrierItemId] = useState<number | null>(8);
  const [replacementScenario, setReplacementScenario] = useState<
    'loss_replacement' | 'resale_new_carrier'
  >('loss_replacement');
  const [selectedNewChipId, setSelectedNewChipId] = useState<number | null>(104);
  const [newChipProvisionReady, setNewChipProvisionReady] = useState<boolean>(false);
  const [replacementReason, setReplacementReason] = useState(
    '原芯片因干洗高温损坏已挂失，使用新 NTAG424 DNA 芯片完成换卡并接续原物品数字档案'
  );
  const [replacementAck, setReplacementAck] = useState(false);
  const [reportLostModalChipId, setReportLostModalChipId] = useState<number | null>(null);
  const [reportLostReason, setReportLostReason] = useState('');

  // 当从芯片或物品详情抽屉携带 chipId / itemId 跳转到专项治理页时，自动切换到对应子场景并预选目标对象
  useEffect(() => {
    if (!focusTarget) return;
    if (focusTarget.tab === 'correction') {
      if (focusTarget.chipId) {
        const targetChip = chips.find((c) => c.id === focusTarget.chipId);
        if (targetChip) {
          if (targetChip.chip_status === 'pending' && targetChip.item_id === null) {
            setCorrSubMode('chip_project');
            setSelectedPendingChipId(targetChip.id);
          } else if (targetChip.item_id !== null) {
            setCorrSubMode('misbind');
            setSelectedMisboundChipId(targetChip.id);
          }
        }
      } else if (focusTarget.itemId) {
        const targetItem = items.find((i) => i.id === focusTarget.itemId);
        if (targetItem) {
          if (targetItem.bound_chip_id !== null) {
            setCorrSubMode('misbind');
            setSelectedMisboundChipId(targetItem.bound_chip_id);
          } else {
            setCorrSubMode('item_identity');
            setSelectedDraftItemId(targetItem.id);
            setCorrItemProject(targetItem.project);
            setCorrItemUidInput(targetItem.item_uid);
          }
        }
      }
    } else if (focusTarget.tab === 'replacement') {
      if (focusTarget.itemId) {
        setSelectedCarrierItemId(focusTarget.itemId);
      } else if (focusTarget.chipId) {
        const targetChip = chips.find((c) => c.id === focusTarget.chipId);
        if (targetChip?.item_id) {
          setSelectedCarrierItemId(targetChip.item_id);
        }
      }
    }
  }, [focusTarget, chips, items]);

  const selectedMisboundChip = useMemo(
    () => chips.find((c) => c.id === selectedMisboundChipId) || null,
    [chips, selectedMisboundChipId]
  );

  // P1-5：计算所选误绑定芯片是否已产生真实用户触碰记录
  const selectedMisboundChipTapCount = useMemo(() => {
    if (!selectedMisboundChip || !selectedMisboundChip.item_uid) return 0;
    return tapEvents.filter((e) => e.item_uid === selectedMisboundChip.item_uid).length;
  }, [selectedMisboundChip, tapEvents]);

  const isMisboundChipLockedForCorrection = Boolean(
    selectedMisboundChip &&
      (selectedMisboundChip.provisioned_at !== null || selectedMisboundChipTapCount > 0)
  );

  const selectedCarrierItem = useMemo(
    () => items.find((i) => i.id === selectedCarrierItemId) || null,
    [items, selectedCarrierItemId]
  );

  const availableNewChipsForReplacement = useMemo(() => {
    if (!selectedCarrierItem) return [];
    return chips.filter(
      (c) =>
        c.chip_status === 'pending' &&
        c.item_id === null &&
        (c.project === null || c.project === selectedCarrierItem.project)
    );
  }, [chips, selectedCarrierItem]);

  const openCleanupConfirmModal = (
    kind: 'l1_chip' | 'l2_chip' | 'l1_item',
    targetId: number,
    targetUid: string
  ) => {
    setCleanupModalState({ kind, targetId, targetUid });
    setCleanupReason('');
    setCleanupConfirmAck(false);
  };

  return (
    <div className="space-y-4">
      <Card size="small" styles={{ body: { padding: '8px 24px 24px' } }}>
        <Tabs
          activeKey={activeTab}
          onChange={(k) => onTabChange(k as WorkflowGovernancePageProps['activeTab'])}
          items={[
            {
              key: 'cleanup',
              label: (
                <Space>
                  <ClearOutlined />
                  <span>B工作流：验证对象识别与分层清理 (L1/L2/L3)</span>
                </Space>
              ),
              children: (
                <div className="space-y-5 pt-2">
                  <Alert
                    type="info"
                    showIcon
                    message="B工作流核心原则：以生命周期阶段 + 依赖关系决定清理边界，禁止对已写卡验证芯片执行裸 DELETE"
                    description={
                      <div className="text-xs space-y-1 mt-1">
                        <div>
                          • <Tag color="cyan">L1 轻度草稿/误登记</Tag>：无关联物品、未生成密钥、无实卡核验、无触碰记录 →{' '}
                          <strong>允许受限直接清理</strong>。
                        </div>
                        <div>
                          • <Tag color="orange">L2 生产验证闭环对象</Tag>：已绑定、已生成密钥或已完成双链接核验的测试样卡 →{' '}
                          <strong>严禁直接硬删抹除安全计数基线</strong>，须执行「退出验证服务并解除测试占用」（保留防重放安全历史，释放测试标识）。
                        </div>
                        <div>
                          • <Tag color="green">L3 正式业务对象</Tag>：已承载正式商品或客户认领权益 →{' '}
                          <strong>系统锁死禁止测试删除</strong>，仅允许走日常停用或 D 工作流挂失换新。
                        </div>
                      </div>
                    }
                  />

                  <div className="p-3.5 rounded-lg bg-slate-50 border border-slate-200 flex flex-wrap items-center justify-between gap-3">
                    <div>
                      <Text strong>统计口径治理开关：</Text>
                      <span className="text-xs text-slate-600 ml-2">
                        在「工作台总览 · 有效触碰统计」中自动排除带有「生产验证对象」标识的测试触碰记录
                      </span>
                    </div>
                    <Switch
                      checked={excludeValidationInStats}
                      onChange={onToggleExcludeValidationInStats}
                      checkedChildren="已排除验证测试触碰"
                      unCheckedChildren="包含全部触碰"
                    />
                  </div>

                  <Card size="small" title="1. 芯片生命周期分层诊断与清理台">
                    <Table
                      rowKey="id"
                      size="small"
                      pagination={{ pageSize: 8, showSizeChanger: false }}
                      dataSource={chips}
                      columns={[
                        {
                          title: '芯片 UID',
                          dataIndex: 'chip_uid',
                          width: 195,
                          render: (uid: string, record) => (
                            <Space size={4}>
                              <Button
                                type="link"
                                size="small"
                                style={{ padding: 0, fontWeight: 600 }}
                                onClick={() => onOpenChipDetail(record.id)}
                              >
                                {uid}
                              </Button>
                              {record.is_validation_object && (
                                <Tag color="orange" style={{ fontSize: 11 }}>
                                  验证对象
                                </Tag>
                              )}
                            </Space>
                          ),
                        },
                        {
                          title: '生命周期分层 (B提案)',
                          key: 'level',
                          width: 185,
                          render: (_, record) => {
                            const ev = evaluateChipLifecycleLevel(record, tapEvents);
                            return <Tag color={ev.color}>{ev.label}</Tag>;
                          },
                        },
                        {
                          title: '系统依赖项检查 (绑定 / 密钥 / 核验 / 触碰)',
                          key: 'deps',
                          render: (_, record) => {
                            const ev = evaluateChipLifecycleLevel(record, tapEvents);
                            if (ev.dependencies.length === 0) {
                              return <Text type="secondary">无任何下游依赖（纯登记记录）</Text>;
                            }
                            return (
                              <Space size={4} wrap>
                                {ev.dependencies.map((d, i) => (
                                  <Tag key={i}>{d}</Tag>
                                ))}
                              </Space>
                            );
                          },
                        },
                        {
                          title: '允许的受控处置动作',
                          key: 'action',
                          width: 240,
                          align: 'right',
                          render: (_, record) => {
                            const ev = evaluateChipLifecycleLevel(record, tapEvents);
                            if (ev.canDeleteDirectly) {
                              return (
                                <Button
                                  size="small"
                                  danger
                                  icon={<DeleteOutlined />}
                                  onClick={() =>
                                    openCleanupConfirmModal('l1_chip', record.id, record.chip_uid)
                                  }
                                >
                                  L1 受限直接清理
                                </Button>
                              );
                            }
                            if (ev.canExitValidation) {
                              return (
                                <Button
                                  size="small"
                                  type="primary"
                                  ghost
                                  icon={<StopOutlined />}
                                  onClick={() =>
                                    openCleanupConfirmModal('l2_chip', record.id, record.chip_uid)
                                  }
                                >
                                  L2 退出验证并解绑
                                </Button>
                              );
                            }
                            return (
                              <Tooltip title={ev.reason}>
                                <Tag icon={<LockOutlined />} color="default">
                                  L3 受保护禁止清理
                                </Tag>
                              </Tooltip>
                            );
                          },
                        },
                      ]}
                    />
                  </Card>

                  <Card size="small" title="2. 无依赖草稿物品 (L1) 快速清理台">
                    <Table
                      rowKey="id"
                      size="small"
                      pagination={{ pageSize: 8, showSizeChanger: false }}
                      dataSource={items.filter(
                        (i) => i.bound_chip_id === null || i.is_validation_object
                      )}
                      columns={[
                        {
                          title: '物品编号',
                          dataIndex: 'item_uid',
                          width: 180,
                          render: (uid: string, record) => (
                            <Button
                              type="link"
                              size="small"
                              style={{ padding: 0, fontWeight: 600 }}
                              onClick={() => onOpenItemDetail(record.id)}
                            >
                              {uid}
                            </Button>
                          ),
                        },
                        {
                          title: '项目 / 状态',
                          key: 'status',
                          width: 160,
                          render: (_, r) => (
                            <Space size={4}>
                              <Tag color={r.project === 'fashion' ? 'blue' : 'gold'}>
                                {PROJECT_SHORT_LABELS[r.project]}
                              </Tag>
                              <Tag color={ITEM_STATUS_META[r.status].tagColor}>
                                {ITEM_STATUS_META[r.status].label}
                              </Tag>
                            </Space>
                          ),
                        },
                        {
                          title: '依赖检查',
                          key: 'deps',
                          render: (_, r) => {
                            const tapCnt = tapEvents.filter((e) => e.item_uid === r.item_uid).length;
                            if (r.bound_chip_id === null && tapCnt === 0 && r.status === 'draft') {
                              return (
                                <Tag color="cyan">
                                  L1 · 未绑定芯片、无触碰记录、草稿状态（支持直接清理）
                                </Tag>
                              );
                            }
                            return (
                              <Tag color="orange">
                                存在芯片绑定或触碰历史（若为测试样衣请先在上方执行 L2 芯片退出解绑）
                              </Tag>
                            );
                          },
                        },
                        {
                          title: '操作',
                          key: 'act',
                          width: 180,
                          align: 'right',
                          render: (_, r) => {
                            const tapCnt = tapEvents.filter((e) => e.item_uid === r.item_uid).length;
                            const canClean =
                              r.bound_chip_id === null && tapCnt === 0 && r.status === 'draft';
                            return canClean ? (
                              <Button
                                size="small"
                                danger
                                icon={<DeleteOutlined />}
                                onClick={() =>
                                  openCleanupConfirmModal('l1_item', r.id, r.item_uid)
                                }
                              >
                                L1 清理草稿物品
                              </Button>
                            ) : (
                              <Tag icon={<LockOutlined />}>需先解除绑定依赖</Tag>
                            );
                          },
                        },
                      ]}
                    />
                  </Card>
                </div>
              ),
            },
            {
              key: 'correction',
              label: (
                <Space>
                  <ToolOutlined />
                  <span>C工作流：建档与绑定受控纠错</span>
                </Space>
              ),
              children: (
                <div className="space-y-5 pt-2">
                  <Alert
                    type="warning"
                    showIcon
                    message="C工作流核心原则：常规维护改普通字段，身份属性纠错与误绑定纠错走显式留痕流程"
                    description="芯片批次号 (batch_no) 与物品款式编号 (sku_code) 已在各自详情抽屉开放直接补录修改。本页专用于处理：① 芯片绑错物品后的受控解绑/改绑；② 待绑定芯片预分配项目选错；③ 未绑定草稿物品编号或项目建档纠错。"
                  />

                  <Radio.Group
                    value={corrSubMode}
                    onChange={(e) => setCorrSubMode(e.target.value)}
                    optionType="button"
                    buttonStyle="solid"
                    options={[
                      {
                        value: 'misbind',
                        label: '场景 1：芯片绑错物品（受控解绑 / 改绑）',
                      },
                      {
                        value: 'chip_project',
                        label: '场景 2：待绑定芯片预分配项目纠错',
                      },
                      {
                        value: 'item_identity',
                        label: '场景 3：未启用草稿物品编号/项目纠错',
                      },
                    ]}
                  />

                  {corrSubMode === 'misbind' && (
                    <Card
                      size="small"
                      title="芯片误绑定受控解绑 ／ 改绑（严格区分是否已完成实卡配置）"
                    >
                      <div className="space-y-4">
                        <div>
                          <div className="text-xs font-medium text-slate-600 mb-1">
                            选择需要纠错的已绑定芯片：
                          </div>
                          <Select
                            style={{ width: '100%', maxWidth: 520 }}
                            value={selectedMisboundChipId}
                            onChange={(val) => {
                              setSelectedMisboundChipId(val);
                              setMisbindConfirmAck(false);
                            }}
                            options={chips
                              .filter((c) => c.chip_status === 'bound' && c.item_id !== null)
                              .map((c) => {
                                const tCnt = c.item_uid
                                  ? tapEvents.filter((e) => e.item_uid === c.item_uid).length
                                  : 0;
                                const locked = c.provisioned_at !== null || tCnt > 0;
                                return {
                                  value: c.id,
                                  label: `${c.chip_uid} → 当前绑定 ${c.item_uid} (${
                                    locked
                                      ? `已实卡核验或存在 ${tCnt} 次触碰 [锁死]`
                                      : c.keys_generated
                                        ? '已生密钥但未核验且无触碰 [允许受控纠错]'
                                        : '未生密钥且无触碰 [允许受控纠错]'
                                  })`,
                                };
                              })}
                          />
                        </div>

                        {selectedMisboundChip && (
                          <>
                            <Descriptions
                              size="small"
                              bordered
                              column={2}
                              items={[
                                {
                                  key: 'uid',
                                  label: '芯片 UID',
                                  children: <Text code>{selectedMisboundChip.chip_uid}</Text>,
                                },
                                {
                                  key: 'curItem',
                                  label: '当前误绑物品',
                                  children: <Text code>{selectedMisboundChip.item_uid}</Text>,
                                },
                                {
                                  key: 'keys',
                                  label: '密钥状态',
                                  children: selectedMisboundChip.keys_generated
                                    ? '已生成（因 K1/K2 基于芯片 UID 派生，改绑同项目物品无需重派生）'
                                    : '未生成',
                                },
                                {
                                  key: 'prov',
                                  label: '实卡配置与外部触碰检查',
                                  children: isMisboundChipLockedForCorrection ? (
                                    <Tag color="error">
                                      {selectedMisboundChip.provisioned_at
                                        ? '已核验生效'
                                        : ''}
                                      {selectedMisboundChipTapCount > 0
                                        ? ` · 已产生 ${selectedMisboundChipTapCount} 次有效触碰`
                                        : ''}
                                      （禁止按误绑定解绑，须走 D 工作流）
                                    </Tag>
                                  ) : (
                                    <Tag color="success">
                                      未完成实卡核验且无真实触碰记录（符合 C 工作流误绑定纠错条件）
                                    </Tag>
                                  ),
                                },
                              ]}
                            />

                            {isMisboundChipLockedForCorrection ? (
                              <Alert
                                type="error"
                                showIcon
                                message={`安全边界阻断：该芯片${
                                  selectedMisboundChip.provisioned_at
                                    ? '已完成实卡配置核验'
                                    : ''
                                }${
                                  selectedMisboundChipTapCount > 0
                                    ? `且存在 ${selectedMisboundChipTapCount} 次真实有效触碰记录`
                                    : ''
                                }`}
                                description="根据 C 提案安全规则，已完成实卡配置核验或已产生外部触碰记录的芯片已承载外部防伪与计数状态，不能按“误绑定”直接解绑回退。若需更换物品或载体，请切换到「D工作流：挂失、换新与转售新载体接续」。"
                              />
                            ) : (
                              <div className="p-4 rounded-lg bg-slate-50 border border-slate-200 space-y-3">
                                <div>
                                  <div className="text-xs font-medium text-slate-600 mb-1">
                                    选择纠错方式：
                                  </div>
                                  <Radio.Group
                                    value={misbindActionType}
                                    onChange={(e) => setMisbindActionType(e.target.value)}
                                  >
                                    <Radio value="unbind_to_pending">
                                      解除当前错误绑定，使芯片回到「待绑定 (pending)」，原物品恢复为「未绑定」
                                    </Radio>
                                    <Radio value="rebind_to_target">
                                      一步改绑到另一件未绑定芯片的目标物品
                                    </Radio>
                                  </Radio.Group>
                                </div>

                                {misbindActionType === 'rebind_to_target' && (
                                  <div>
                                    <div className="text-xs font-medium text-slate-600 mb-1">
                                      选择正确的新目标物品（仅列未绑定芯片的物品）：
                                    </div>
                                    <Select
                                      style={{ width: '100%', maxWidth: 460 }}
                                      placeholder="请选择正确的目标物品"
                                      value={misbindTargetItemId}
                                      onChange={(val) => setMisbindTargetItemId(val)}
                                      options={items
                                        .filter((i) => i.bound_chip_id === null && i.status !== 'archived')
                                        .map((i) => ({
                                          value: i.id,
                                          label: `[${PROJECT_SHORT_LABELS[i.project]}] ${i.item_uid} · ${
                                            i.profile?.name || '未填名称'
                                          }`,
                                        }))}
                                    />
                                  </div>
                                )}

                                <div>
                                  <div className="text-xs font-medium text-slate-600 mb-1">
                                    纠错原因说明（必填，记入审计日志）：
                                  </div>
                                  <Input
                                    placeholder="如：仓库配卡员选错顺延序号，将 FASH-2026-000004 误绑至该芯片"
                                    value={misbindReason}
                                    onChange={(e) => setMisbindReason(e.target.value)}
                                  />
                                </div>

                                <Checkbox
                                  checked={misbindConfirmAck}
                                  onChange={(e) => setMisbindConfirmAck(e.target.checked)}
                                >
                                  我已核实该芯片尚未对外正式交付，确认解除其与{' '}
                                  <Text code>{selectedMisboundChip.item_uid}</Text> 的错误关联。
                                </Checkbox>

                                <div>
                                  <Button
                                    type="primary"
                                    disabled={
                                      !misbindConfirmAck ||
                                      !misbindReason.trim() ||
                                      (misbindActionType === 'rebind_to_target' &&
                                        !misbindTargetItemId)
                                    }
                                    onClick={() => {
                                      const res = onUnbindOrRebindMisboundChip(
                                        selectedMisboundChip.id,
                                        misbindActionType,
                                        misbindTargetItemId,
                                        misbindReason.trim()
                                      );
                                      if (res.ok) {
                                        message.success('已完成芯片误绑定受控纠错并写入审计日志');
                                        setMisbindReason('');
                                        setMisbindConfirmAck(false);
                                      } else {
                                        message.error(res.error);
                                      }
                                    }}
                                  >
                                    执行误绑定受控纠错
                                  </Button>
                                </div>
                              </div>
                            )}
                          </>
                        )}
                      </div>
                    </Card>
                  )}

                  {corrSubMode === 'chip_project' && (
                    <Card size="small" title="待绑定芯片预分配项目纠错（仅限 pending 且未绑定物品的芯片）">
                      <div className="space-y-3 max-w-xl">
                        <div>
                          <div className="text-xs font-medium text-slate-600 mb-1">
                            选择待绑定芯片：
                          </div>
                          <Select
                            style={{ width: '100%' }}
                            value={selectedPendingChipId}
                            onChange={(val) => setSelectedPendingChipId(val)}
                            options={chips
                              .filter((c) => c.chip_status === 'pending' && c.item_id === null)
                              .map((c) => ({
                                value: c.id,
                                label: `${c.chip_uid}（当前项目：${
                                  c.project ? PROJECT_SHORT_LABELS[c.project] : '未分配'
                                }）`,
                              }))}
                          />
                        </div>
                        <div>
                          <div className="text-xs font-medium text-slate-600 mb-1">
                            修正后的预分配项目：
                          </div>
                          <Select
                            style={{ width: '100%' }}
                            value={targetChipProject}
                            onChange={(val) => setTargetChipProject(val)}
                            options={[
                              { value: '', label: '清空预分配项目（恢复为未分配，绑定时自动确定）' },
                              { value: 'fashion', label: '服装 (Fashion)' },
                              { value: 'jewelry', label: '饰品 (Jewelry)' },
                            ]}
                          />
                        </div>
                        <div>
                          <div className="text-xs font-medium text-slate-600 mb-1">
                            纠错原因（必填）：
                          </div>
                          <Input
                            placeholder="如：手工登记时误选为饰品，实际为服装批次芯片"
                            value={chipProjReason}
                            onChange={(e) => setChipProjReason(e.target.value)}
                          />
                        </div>
                        <Button
                          type="primary"
                          disabled={!selectedPendingChipId || !chipProjReason.trim()}
                          onClick={() => {
                            if (!selectedPendingChipId) return;
                            const res = onCorrectPendingChipProject(
                              selectedPendingChipId,
                              targetChipProject || null,
                              chipProjReason.trim()
                            );
                            if (res.ok) {
                              message.success('已修正待绑定芯片的预分配项目');
                              setChipProjReason('');
                            } else {
                              message.error(res.error);
                            }
                          }}
                        >
                          确认修正芯片项目
                        </Button>
                      </div>
                    </Card>
                  )}

                  {corrSubMode === 'item_identity' && (
                    <Card
                      size="small"
                      title="未启用且未绑定草稿物品的身份纠错（修正 item_uid 或所属项目）"
                    >
                      <div className="space-y-3 max-w-xl">
                        <Alert
                          type="info"
                          showIcon
                          message="仅允许对「草稿状态、未绑定任何芯片、无有效触碰记录」的物品修正编号或项目；已绑定或已启用物品严禁篡改唯一身份编号。"
                        />
                        <div>
                          <div className="text-xs font-medium text-slate-600 mb-1">
                            选择符合条件的草稿物品：
                          </div>
                          <Select
                            style={{ width: '100%' }}
                            value={selectedDraftItemId}
                            onChange={(val) => {
                              setSelectedDraftItemId(val);
                              const it = items.find((i) => i.id === val);
                              if (it) {
                                setCorrItemProject(it.project);
                                setCorrItemUidInput(it.item_uid);
                              }
                            }}
                            options={items
                              .filter((i) => i.status === 'draft' && i.bound_chip_id === null)
                              .map((i) => ({
                                value: i.id,
                                label: `[${PROJECT_SHORT_LABELS[i.project]}] ${i.item_uid} (${
                                  i.profile?.name || '无名称'
                                })`,
                              }))}
                          />
                        </div>
                        <Row gutter={12}>
                          <Col span={10}>
                            <div className="text-xs font-medium text-slate-600 mb-1">
                              修正后项目：
                            </div>
                            <Select
                              style={{ width: '100%' }}
                              value={corrItemProject}
                              onChange={(val) => {
                                setCorrItemProject(val);
                                setCorrItemUidInput(
                                  val === 'fashion' ? 'FASH-2026-000008' : 'JEW-2026-000003'
                                );
                              }}
                              options={[
                                { value: 'fashion', label: '服装 (Fashion)' },
                                { value: 'jewelry', label: '饰品 (Jewelry)' },
                              ]}
                            />
                          </Col>
                          <Col span={14}>
                            <div className="text-xs font-medium text-slate-600 mb-1">
                              修正后物品编号 (须匹配前缀)：
                            </div>
                            <Input
                              value={corrItemUidInput}
                              onChange={(e) => setCorrItemUidInput(e.target.value)}
                            />
                          </Col>
                        </Row>
                        <div>
                          <div className="text-xs font-medium text-slate-600 mb-1">
                            纠错原因（必填）：
                          </div>
                          <Input
                            placeholder="如：建档时录入错序号，尚未贴标绑卡，现修正编号"
                            value={corrItemReason}
                            onChange={(e) => setCorrItemReason(e.target.value)}
                          />
                        </div>
                        <Button
                          type="primary"
                          disabled={!selectedDraftItemId || !corrItemReason.trim()}
                          onClick={() => {
                            if (!selectedDraftItemId) return;
                            const check = validateItemUid(corrItemProject, corrItemUidInput);
                            if (!check.ok) {
                              message.error(check.error);
                              return;
                            }
                            const res = onCorrectItemIdentity(
                              selectedDraftItemId,
                              corrItemProject,
                              check.item_uid,
                              corrItemReason.trim()
                            );
                            if (res.ok) {
                              message.success(`物品身份已修正为 ${check.item_uid}`);
                              setCorrItemReason('');
                            } else {
                              message.error(res.error);
                            }
                          }}
                        >
                          确认修正草稿物品身份
                        </Button>
                      </div>
                    </Card>
                  )}
                </div>
              ),
            },
            {
              key: 'replacement',
              label: (
                <Space>
                  <SwapOutlined />
                  <span>D工作流：挂失、换新与转售新载体接续</span>
                </Space>
              ),
              children: (
                <div className="space-y-5 pt-2">
                  <Alert
                    type="info"
                    showIcon
                    message="D工作流核心规则：数字物品身份 (item_uid) 与载体芯片生命周期解耦，单活载体切换"
                    description="无论发生「芯片丢失/损坏换新」还是「二手转售寄回平台制作新实体配新芯片」，数字物品编号 item_uid 与商品资料始终保持不变。新芯片激活接续的同一事务内，原芯片立即转为「已退役 (retired)」并失效全部旧短期凭证与 24h 持续查看资格。"
                  />

                  <Row gutter={[16, 16]}>
                    <Col xs={24} lg={10}>
                      <Card
                        size="small"
                        title="第一步：原芯片挂失 / 风险冻结"
                        extra={<Tag color="red">即时阻断旧凭证</Tag>}
                      >
                        <div className="space-y-3">
                          <div className="text-xs text-slate-500">
                            当持有人反馈实体芯片遗失、洗涤损坏，或转售旧实体需冻结时，先将原芯片标记为「已挂失 (lost)」。挂失后旧芯片碰卡立即拒绝，且已签发的浏览器持续查看会话立即失效。
                          </div>
                          <Table
                            rowKey="id"
                            size="small"
                            pagination={false}
                            dataSource={chips.filter(
                              (c) =>
                                (c.chip_status === 'bound' || c.chip_status === 'lost') &&
                                c.item_id !== null
                            )}
                            columns={[
                              {
                                title: '芯片 / 关联物品',
                                key: 'info',
                                render: (_, r) => (
                                  <div>
                                    <div className="font-mono text-xs font-semibold">
                                      {r.chip_uid}
                                    </div>
                                    <div className="text-xs text-slate-500">{r.item_uid}</div>
                                  </div>
                                ),
                              },
                              {
                                title: '状态',
                                dataIndex: 'chip_status',
                                width: 90,
                                render: (st: ChipView['chip_status']) => (
                                  <Tag color={CHIP_STATUS_META[st].tagColor}>
                                    {CHIP_STATUS_META[st].label}
                                  </Tag>
                                ),
                              },
                              {
                                title: '操作',
                                key: 'act',
                                width: 110,
                                align: 'right',
                                render: (_, r) =>
                                  r.chip_status === 'bound' ? (
                                    <Button
                                      size="small"
                                      danger
                                      onClick={() => {
                                        setReportLostModalChipId(r.id);
                                        setReportLostReason('持有人反馈芯片损坏/遗失，申请挂失冻结');
                                      }}
                                    >
                                      标记挂失
                                    </Button>
                                  ) : (
                                    <Button
                                      size="small"
                                      type="link"
                                      onClick={() => {
                                        setSelectedCarrierItemId(r.item_id);
                                      }}
                                    >
                                      去右侧换卡 →
                                    </Button>
                                  ),
                              },
                            ]}
                          />
                        </div>
                      </Card>
                    </Col>

                    <Col xs={24} lg={14}>
                      <Card
                        size="small"
                        title="第二步：新载体芯片正式接续激活（原子切换：新卡生效 + 旧卡永久退役）"
                      >
                        <div className="space-y-4">
                          <Steps
                            size="small"
                            current={!selectedNewChipId ? 0 : !newChipProvisionReady ? 1 : 2}
                            items={[
                              {
                                title: '1. 选择物品与新卡',
                                description: selectedNewChipId ? '已选定待绑定新卡' : '选择接替载体',
                              },
                              {
                                title: '2. 新卡实卡核验准备',
                                description: newChipProvisionReady
                                  ? '已确认密钥与双链接核验'
                                  : '确认新卡配卡就绪',
                              },
                              {
                                title: '3. 正式接续并退役旧卡',
                                description: '原子切换单活载体',
                              },
                            ]}
                          />

                          <div>
                            <div className="text-xs font-medium text-slate-600 mb-1">
                              1. 选择业务接续场景：
                            </div>
                            <Radio.Group
                              value={replacementScenario}
                              onChange={(e) => {
                                setReplacementScenario(e.target.value);
                                setReplacementReason(
                                  e.target.value === 'loss_replacement'
                                    ? '原芯片损坏/挂失，为同一持有人补发新芯片并接续原数字物品身份'
                                    : '二手转售新实体接续：平台制作新实体并配发新芯片，原芯片与旧实体退出防伪授权'
                                );
                              }}
                            >
                              <Radio value="loss_replacement">
                                持有人挂失 / 损坏补换新卡（持有人不变）
                              </Radio>
                              <Radio value="resale_new_carrier">
                                转售新实体接续（新实体配新芯片，旧芯片永久退役）
                              </Radio>
                            </Radio.Group>
                          </div>

                          <Row gutter={12}>
                            <Col xs={24} sm={12}>
                              <div className="text-xs font-medium text-slate-600 mb-1">
                                2. 选择要接续的数字物品 (item_uid 不变)：
                              </div>
                              <Select
                                style={{ width: '100%' }}
                                value={selectedCarrierItemId}
                                onChange={(val) => setSelectedCarrierItemId(val)}
                                options={items
                                  .filter((i) => i.bound_chip_id !== null)
                                  .map((i) => ({
                                    value: i.id,
                                    label: `${i.item_uid}（当前卡：${i.bound_chip_uid} [${
                                      i.bound_chip_status
                                        ? CHIP_STATUS_META[i.bound_chip_status].label
                                        : ''
                                    }]）`,
                                  }))}
                              />
                            </Col>
                            <Col xs={24} sm={12}>
                              <div className="text-xs font-medium text-slate-600 mb-1">
                                3. 选择接替的新芯片（须为待绑定真实 UID）：
                              </div>
                              <Select
                                style={{ width: '100%' }}
                                placeholder="选择待绑定新芯片"
                                value={selectedNewChipId}
                                onChange={(val) => {
                                  setSelectedNewChipId(val);
                                  setNewChipProvisionReady(false);
                                  setReplacementAck(false);
                                }}
                                options={availableNewChipsForReplacement.map((c) => ({
                                  value: c.id,
                                  label: `${c.chip_uid} (${
                                    c.project ? PROJECT_SHORT_LABELS[c.project] : '未分配项目'
                                  })`,
                                }))}
                              />
                            </Col>
                          </Row>

                          {selectedNewChipId && (
                            <div className="p-3 rounded bg-slate-50 border border-slate-200 flex flex-wrap items-center justify-between gap-2">
                              <div className="text-xs">
                                <span className="font-medium text-slate-800">
                                  步骤 2 · 新载体实卡准备与双链接核验状态：
                                </span>
                                <span className="text-slate-600 ml-1">
                                  {newChipProvisionReady
                                    ? '已完成新卡 K0–K4 写入与双链接递增核验，可随时执行正式切换'
                                    : '正式接续前，请先确认新芯片已完成实卡写入与双链接动态核验'}
                                </span>
                              </div>
                              <Switch
                                checked={newChipProvisionReady}
                                onChange={setNewChipProvisionReady}
                                checkedChildren="新卡已核验就绪"
                                unCheckedChildren="标记新卡核验就绪"
                              />
                            </div>
                          )}

                          {selectedCarrierItem && (
                            <div className="p-3 rounded bg-blue-50/70 border border-blue-200 text-xs space-y-1.5">
                              <div className="font-medium text-slate-800">
                                即将执行的单活载体原子切换预览：
                              </div>
                              <div>
                                • 数字物品身份保持不变：<Text code>{selectedCarrierItem.item_uid}</Text>（
                                {selectedCarrierItem.profile?.name || '未填名称'}），载体代数将升至{' '}
                                <strong>第 {(selectedCarrierItem.carrier_generation || 1) + 1} 代</strong>
                              </div>
                              <div>
                                • 原载体芯片 <Text code>{selectedCarrierItem.bound_chip_uid}</Text>{' '}
                                将立即转为 <Tag color="default">已退役 (retired)</Tag>
                                ，永久退出授权且不可普通恢复
                              </div>
                              <div>
                                • 新载体芯片{' '}
                                <Text code>
                                  {chips.find((c) => c.id === selectedNewChipId)?.chip_uid ||
                                    '（请选择）'}
                                </Text>{' '}
                                将正式接替成为该物品唯一有效载体，并同步保存其密钥版本与读取计数基线
                              </div>
                            </div>
                          )}

                          <div>
                            <div className="text-xs font-medium text-slate-600 mb-1">
                              4. 换卡 ／ 转售新实体接续工单备注（必填）：
                            </div>
                            <Input
                              value={replacementReason}
                              onChange={(e) => setReplacementReason(e.target.value)}
                            />
                          </div>

                          <Checkbox
                            checked={replacementAck}
                            disabled={!newChipProvisionReady}
                            onChange={(e) => setReplacementAck(e.target.checked)}
                          >
                            我已核对新旧芯片 UID 与物品编号无误，理解执行正式接续后原芯片将永久退役（retired）且旧查看凭证立即失效。
                          </Checkbox>

                          <div>
                            <Button
                              type="primary"
                              icon={<RetweetOutlined />}
                              disabled={
                                !selectedCarrierItemId ||
                                !selectedNewChipId ||
                                !newChipProvisionReady ||
                                !replacementReason.trim() ||
                                !replacementAck
                              }
                              onClick={() => {
                                if (!selectedCarrierItemId || !selectedNewChipId) return;
                                const res = onExecuteCarrierReplacement({
                                  itemId: selectedCarrierItemId,
                                  newChipId: selectedNewChipId,
                                  scenario: replacementScenario,
                                  reason: replacementReason.trim(),
                                });
                                if (res.ok) {
                                  message.success(
                                    '已完成新载体芯片正式接续！原芯片已转为永久退役 (retired)。'
                                  );
                                  setNewChipProvisionReady(false);
                                  setReplacementAck(false);
                                  const nextAvail = chips.find(
                                    (c) =>
                                      c.id !== selectedNewChipId &&
                                      c.chip_status === 'pending' &&
                                      c.item_id === null
                                  );
                                  setSelectedNewChipId(nextAvail ? nextAvail.id : null);
                                } else {
                                  message.error(res.error);
                                }
                              }}
                            >
                              确认执行新载体正式接续并退役旧卡
                            </Button>
                          </div>
                        </div>
                      </Card>
                    </Col>
                  </Row>
                </div>
              ),
            },
            {
              key: 'audit',
              label: (
                <Space>
                  <AuditOutlined />
                  <span>管理员安全审计日志 ({auditLogs.length})</span>
                </Space>
              ),
              children: (
                <div className="space-y-3 pt-2">
                  <Alert
                    type="info"
                    showIcon
                    message="全链路安全审计：所有芯片登记、首次绑定、密钥生成/受控查看、实卡核验、B清理、C纠错、D换卡接续均自动记录不可篡改日志。"
                  />
                  <Table
                    rowKey="id"
                    size="small"
                    pagination={{ pageSize: 12, showSizeChanger: false }}
                    dataSource={auditLogs}
                    columns={[
                      {
                        title: '时间 (北京时间)',
                        dataIndex: 'timestamp',
                        width: 175,
                        render: (val: string) => (
                          <span className="font-mono text-xs text-slate-500">
                            {new Date(val).toLocaleString('zh-CN', { hour12: false })}
                          </span>
                        ),
                      },
                      {
                        title: '操作人',
                        dataIndex: 'operator',
                        width: 120,
                        render: (op: string) => <Tag color="blue">{op}</Tag>,
                      },
                      {
                        title: '类别',
                        dataIndex: 'category',
                        width: 120,
                        render: (cat: AuditLogEntry['category']) => {
                          const map: Record<AuditLogEntry['category'], { label: string; color: string }> = {
                            chip: { label: '芯片日常', color: 'geekblue' },
                            item: { label: '物品资料', color: 'cyan' },
                            key_provision: { label: '密钥与配卡', color: 'purple' },
                            correction: { label: 'C工作流纠错', color: 'orange' },
                            cleanup: { label: 'B工作流清理', color: 'magenta' },
                            replacement: { label: 'D工作流换卡', color: 'red' },
                            auth: { label: '会话认证', color: 'green' },
                          };
                          return <Tag color={map[cat].color}>{map[cat].label}</Tag>;
                        },
                      },
                      {
                        title: '动作标识',
                        dataIndex: 'action',
                        width: 190,
                        render: (act: string) => <Text code>{act}</Text>,
                      },
                      {
                        title: '操作对象',
                        dataIndex: 'target',
                        width: 230,
                        render: (t: string) => <Text strong>{t}</Text>,
                      },
                      {
                        title: '审计详情与原因记录',
                        dataIndex: 'detail',
                      },
                    ]}
                  />
                </div>
              ),
            },
          ]}
        />
      </Card>

      <Modal
        title="确认将芯片标记为「已挂失 (lost)」"
        open={reportLostModalChipId !== null}
        onCancel={() => setReportLostModalChipId(null)}
        onOk={() => {
          if (!reportLostModalChipId) return;
          const res = onReportChipLost(
            reportLostModalChipId,
            reportLostReason.trim() || '持有人申请挂失'
          );
          if (res.ok) {
            message.warning('芯片已挂失！旧卡碰一碰与已签发持续查看资格已立即失效。');
            setReportLostModalChipId(null);
          } else {
            message.error(res.error);
          }
        }}
        okText="确认挂失并冻结旧凭证"
        okButtonProps={{ danger: true }}
      >
        <div className="space-y-3 pt-2">
          <Alert
            type="warning"
            showIcon
            message="挂失后，该芯片将被立即禁止通过 /tap 验证，且此前已签发的短期查看凭证与 24 小时持续查看 Cookie 立即失效。"
          />
          <div>
            <div className="text-xs font-medium mb-1">挂失原因说明：</div>
            <Input
              value={reportLostReason}
              onChange={(e) => setReportLostReason(e.target.value)}
              placeholder="如：客户反馈干洗后芯片损坏无法感应"
            />
          </div>
        </div>
      </Modal>

      {/* P1-4：B工作流 L1 直接清理 / L2 退出验证独立受控确认 Modal */}
      <Modal
        title={
          cleanupModalState?.kind === 'l2_chip'
            ? `确认执行 L2 生产验证芯片退出与解绑：${cleanupModalState.targetUid}`
            : `确认执行 L1 无依赖记录直接清理：${cleanupModalState?.targetUid || ''}`
        }
        open={cleanupModalState !== null}
        onCancel={() => setCleanupModalState(null)}
        okText={
          cleanupModalState?.kind === 'l2_chip'
            ? '确认退出验证并释放关联'
            : '确认永久清理记录'
        }
        okButtonProps={{
          danger: cleanupModalState?.kind !== 'l2_chip',
          disabled: !cleanupReason.trim() || !cleanupConfirmAck,
        }}
        onOk={() => {
          if (!cleanupModalState || !cleanupReason.trim() || !cleanupConfirmAck) return;
          if (cleanupModalState.kind === 'l1_chip') {
            const res = onDeleteL1Chip(cleanupModalState.targetId, cleanupReason.trim());
            if (res.ok) {
              message.success(`已清理 L1 无依赖芯片 ${cleanupModalState.targetUid}`);
              setCleanupModalState(null);
            } else {
              message.error(res.error);
            }
          } else if (cleanupModalState.kind === 'l2_chip') {
            const res = onExitL2ValidationChip(
              cleanupModalState.targetId,
              cleanupReason.trim()
            );
            if (res.ok) {
              message.success(
                `验证芯片 ${cleanupModalState.targetUid} 已退出验证服务并释放测试关联`
              );
              setCleanupModalState(null);
            } else {
              message.error(res.error);
            }
          } else {
            const res = onDeleteL1Item(cleanupModalState.targetId, cleanupReason.trim());
            if (res.ok) {
              message.success(`已清理 L1 无依赖草稿物品 ${cleanupModalState.targetUid}`);
              setCleanupModalState(null);
            } else {
              message.error(res.error);
            }
          }
        }}
      >
        {cleanupModalState && (
          <div className="space-y-3 pt-2">
            <Alert
              type={cleanupModalState.kind === 'l2_chip' ? 'info' : 'warning'}
              showIcon
              message={
                cleanupModalState.kind === 'l2_chip'
                  ? 'L2 安全退出：将停用并封存该验证芯片的安全计数历史，同时解除对测试物品的占用（不会执行破坏防重放基线的硬删除）。'
                  : 'L1 直接清理：该记录尚无任何绑定、密钥与触碰依赖，清理后将从当前列表中移除且不可撤销。'
              }
            />
            <div>
              <div className="flex items-center justify-between text-xs font-medium mb-1">
                <span>清理 ／ 退出验证原因说明（必填，记入审计日志）：</span>
                <Space size={4}>
                  <Button
                    type="link"
                    size="small"
                    style={{ padding: 0, fontSize: 11 }}
                    onClick={() =>
                      setCleanupReason('上线前生产验证结束，按 B 提案规范清理测试对象')
                    }
                  >
                    填入：生产验证结束清理
                  </Button>
                  <span>·</span>
                  <Button
                    type="link"
                    size="small"
                    style={{ padding: 0, fontSize: 11 }}
                    onClick={() => setCleanupReason('手工建档录入错误，无实卡依赖，执行 L1 清理')}
                  >
                    填入：手工误录清理
                  </Button>
                </Space>
              </div>
              <Input
                placeholder="请填写本次清理或退出验证的具体原因"
                value={cleanupReason}
                onChange={(e) => setCleanupReason(e.target.value)}
              />
            </div>
            <Checkbox
              checked={cleanupConfirmAck}
              onChange={(e) => setCleanupConfirmAck(e.target.checked)}
            >
              我已核对目标编号 <Text code>{cleanupModalState.targetUid}</Text>{' '}
              并非正式在售或已认领商品，确认执行本次操作。
            </Checkbox>
          </div>
        )}
      </Modal>
    </div>
  );
};
