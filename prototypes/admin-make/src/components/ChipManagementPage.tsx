import {usePrototype} from '../data/prototypeStore';
import {readFilters,writeFilters} from '../data/prototypeNavigation';
import React, { useEffect, useMemo, useState } from 'react';
import {
  Alert,
  Badge,
  Button,
  Card,
  Checkbox,
  Col,
  DatePicker,
  Descriptions,
  Divider,
  Drawer,
  Empty,
  Form,
  Input,
  Modal,
  Popconfirm,
  Radio,
  Row,
  Select,
  Space,
  Steps,
  Switch,
  Table,
  Tag,
  Tooltip,
  Typography,
  message,
} from 'antd';
import {
  DeleteOutlined,
  DownOutlined,
  EditOutlined,
  EyeInvisibleOutlined,
  EyeOutlined,
  KeyOutlined,
  LinkOutlined,
  MobileOutlined,
  PauseCircleOutlined,
  PlayCircleOutlined,
  PlusOutlined,
  ReloadOutlined,
  SearchOutlined,
  StopOutlined,
  SwapOutlined,
  UpOutlined,
  WarningOutlined,
} from '@ant-design/icons';
import type { ColumnsType } from 'antd/es/table';
import {
  CHIP_STATUS_META,
  evaluateChipLifecycleLevel,
  ITEM_STATUS_META,
  normalizeAndValidateChipUid,
  PROJECT_SHORT_LABELS,
  REGISTRATION_SOURCE_LABELS,
  validateSunTapLinks,
  type ChipKeys,
  type ChipStatus,
  type ChipView,
  type ItemView,
  type ProjectCode,
  type RegistrationSource,
  type TapEventRecord,
} from '../data/mockBackend';

const { Text } = Typography;
const { RangePicker } = DatePicker;

interface ChipManagementPageProps {
  chips: ChipView[];
  items: ItemView[];
  tapEvents: TapEventRecord[];
  activeChipId: number | null;
  presetFilter?: {
    type: 'all' | 'pending' | 'bound_unprovisioned' | 'lost';
    nonce: number;
  } | null;
  simulateApiError?: boolean;
  onRecoverApiError?: () => void;
  onSelectChipId: (chipId: number | null) => void;
  onOpenItemDetail: (itemId: number) => void;
  onRegisterChip: (payload: {
    chip_uid: string;
    project: ProjectCode | null;
    batch_no: string | null;
    source?: RegistrationSource;
    is_validation_object?: boolean;
  }) => {
 chip: ChipView; is_new: boolean; error?: string };
  onUpdateChipMaintenance: (
    chipId: number,
    payload: {
      batch_no: string | null;
      is_validation_object: boolean;
      validation_note: string | null;
    }
  ) => void;
  onBindChipToItem: (chipId: number, itemId: number) => { ok: boolean; error?: string; chip?: ChipView };
  onGenerateChipKeys: (chipId: number) => { ok: boolean; error?: string };
  onConfirmChipProvisioning: (chipId: number) => { ok: boolean; error?: string };
  onToggleChipTempStatus: (chipId: number, targetStatus: 'disabled' | 'bound' | 'pending') => void;
  onCorrectPendingChipProject: (
    chipId: number,
    newProject: ProjectCode | null,
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
  onDeleteL1Chip: (chipId: number, reason: string) => { ok: boolean; error?: string };
  onExitL2ValidationChip: (chipId: number, reason: string) => { ok: boolean; error?: string };
}

interface ChipFilterState {
  keyword: string;
  project: '' | 'unassigned' | ProjectCode;
  status: '' | ChipStatus;
  batchKeyword: string;
  source: '' | RegistrationSource;
  keyProvisionState: '' | 'no_key' | 'key_only' | 'unprovisioned' | 'provisioned';
  validationScope: '' | 'formal_only' | 'validation_only';
  dateField: 'created_at' | 'provisioned_at';
  dateFrom: string;
  dateTo: string;
}

const INITIAL_FILTERS: ChipFilterState = {
  keyword: '',
  project: '',
  status: '',
  batchKeyword: '',
  source: '',
  keyProvisionState: '',
  validationScope: '',
  dateField: 'created_at',
  dateFrom: '',
  dateTo: '',
};

export const ChipManagementPage: React.FC<ChipManagementPageProps> = ({
  chips,
  items,
  tapEvents,
  activeChipId,
  presetFilter,
  simulateApiError = false,
  onRecoverApiError,
  onSelectChipId,
  onOpenItemDetail,
  onRegisterChip,
  onUpdateChipMaintenance,
  onBindChipToItem,
  onGenerateChipKeys,
  onConfirmChipProvisioning,
  onToggleChipTempStatus,
  onCorrectPendingChipProject,
  onUnbindOrRebindMisboundChip,
  onReportChipLost,
  onExecuteCarrierReplacement,
  onDeleteL1Chip,
  onExitL2ValidationChip,
}) => {
  const proto=usePrototype();
  const closeRegister = () => {if(regUidInput.trim()||regBatchNo.trim()){Modal.confirm({title:'放弃未提交的芯片登记？',content:'本次UID或批次尚未提交，确定关闭吗？',okText:'确认关闭',cancelText:'继续填写',onOk:()=>setRegisterModalOpen(false)});}else setRegisterModalOpen(false);};
  const [filters, setFilters] = useState<ChipFilterState>(()=>readFilters("chips",INITIAL_FILTERS));
  const [appliedFilters, setAppliedFilters] = useState<ChipFilterState>(()=>readFilters("chips",INITIAL_FILTERS));
  const [expandAdvanced, setExpandAdvanced] = useState(false);
  const [currentPage, setCurrentPage] = useState(()=>Number(new URLSearchParams(location.hash.split("?")[1]).get("chipsPage"))||1);
  useEffect(()=>writeFilters("chips",appliedFilters,currentPage),[appliedFilters,currentPage]);

  useEffect(() => {
    if (!presetFilter) return;
    if (presetFilter.type === 'all') {
      setFilters(INITIAL_FILTERS);
      setAppliedFilters(INITIAL_FILTERS);
      setCurrentPage(1);
    } else if (presetFilter.type === 'pending') {
      const next: ChipFilterState = { ...INITIAL_FILTERS, status: 'pending' };
      setFilters(next);
      setAppliedFilters(next);
      setCurrentPage(1);
    } else if (presetFilter.type === 'bound_unprovisioned') {
      const next: ChipFilterState = {
        ...INITIAL_FILTERS,
        status: 'bound',
        keyProvisionState: 'unprovisioned',
      };
      setFilters(next);
      setAppliedFilters(next);
      setExpandAdvanced(true);
      setCurrentPage(1);
    } else if (presetFilter.type === 'lost') {
      const next: ChipFilterState = { ...INITIAL_FILTERS, status: 'lost' };
      setFilters(next);
      setAppliedFilters(next);
      setCurrentPage(1);
    }
  }, [presetFilter]);

  const [recentActionBanner, setRecentActionBanner] = useState<{
    type: 'success' | 'info';
    title: string;
    description: string;
    chip: ChipView;
  } | null>(null);

  const [registerModalOpen, setRegisterModalOpen] = useState(false);
  const [regUidInput, setRegUidInput] = useState('');
  const [regProject, setRegProject] = useState<'' | ProjectCode>('');
  const [regBatchNo, setRegBatchNo] = useState('');
  const [regIsValidation, setRegIsValidation] = useState(false);
  const [regError, setRegError] = useState('');
  const [regConflictChip, setRegConflictChip] = useState<ChipView | null>(null);
  const [dateRangeResetKey, setDateRangeResetKey] = useState(0);

  const [bindModalChipId, setBindModalChipId] = useState<number | null>(null);
  const [bindCandidateProject, setBindCandidateProject] = useState<ProjectCode>('fashion');
  const [bindCandidateKeyword, setBindCandidateKeyword] = useState('');
  const [selectedCandidateId, setSelectedCandidateId] = useState<number | null>(null);
  const [bindConfirmedCheck, setBindConfirmedCheck] = useState(false);
  const [bindError, setBindError] = useState('');

  const [keyModalChipId, setKeyModalChipId] = useState<number | null>(null);
  const [keyViewAck, setKeyViewAck] = useState(false);
  const [revealedKeys, setRevealedKeys] = useState<ChipKeys | null>(null);
  const [tapLink1, setTapLink1] = useState('');
  const [tapLink2, setTapLink2] = useState('');
  const [k0ManualConfirmed, setK0ManualConfirmed] = useState(false);
  const [keyModalError, setKeyModalError] = useState('');
  const [keyModalSuccess, setKeyModalSuccess] = useState('');

  const [drawerBatchInput, setDrawerBatchInput] = useState('');
  const [drawerIsValidation, setDrawerIsValidation] = useState(false);
  const [drawerValidationNote, setDrawerValidationNote] = useState('');

  // 页内直接执行的项目修改、解绑/改绑、挂失、换新接续、删除/退出验证弹窗状态
  const [editProjectModalOpen, setEditProjectModalOpen] = useState(false);
  const [editProjectVal, setEditProjectVal] = useState<'' | ProjectCode>('');
  const [editProjectReason, setEditProjectReason] = useState('');

  const [unbindModalOpen, setUnbindModalOpen] = useState(false);
  const [unbindMode, setUnbindMode] = useState<'unbind_to_pending' | 'rebind_to_target'>(
    'unbind_to_pending'
  );
  const [rebindTargetItemId, setRebindTargetItemId] = useState<number | null>(null);
  const [unbindReason, setUnbindReason] = useState('');

  const [lostModalOpen, setLostModalOpen] = useState(false);
  const [lostReason, setLostReason] = useState('');

  const [replaceModalChipId, setReplaceModalChipId] = useState<number | null>(null);
  const [replaceScenario, setReplaceScenario] = useState<
    'loss_replacement' | 'resale_new_carrier'
  >('loss_replacement');
  const [replaceNewChipId, setReplaceNewChipId] = useState<number | null>(null);
  const [replaceReason, setReplaceReason] = useState('');

  const [cleanupModalKind, setCleanupModalKind] = useState<'delete_l1' | 'exit_l2' | null>(null);
  const [cleanupReason, setCleanupReason] = useState('');

  const activeChip = useMemo(
    () => chips.find((c) => c.id === activeChipId) || null,
    [chips, activeChipId]
  );

  const replaceSourceChip = useMemo(
    () => chips.find((c) => c.id === replaceModalChipId) || null,
    [chips, replaceModalChipId]
  );

  const replaceTargetItem = useMemo(
    () =>
      replaceSourceChip?.item_id
        ? items.find((i) => i.id === replaceSourceChip.item_id) || null
        : null,
    [items, replaceSourceChip]
  );

  const availableReplacementChips = useMemo(() => {
    if (!replaceTargetItem) return [];
    return chips.filter(
      (c) =>
        c.chip_status === 'pending' &&
        c.item_id === null &&
        (c.project === null || c.project === replaceTargetItem.project)
    );
  }, [chips, replaceTargetItem]);

  const activeChipTapCount = useMemo(() => {
    if (!activeChip?.item_uid) return 0;
    return tapEvents.filter((e) => e.item_uid === activeChip.item_uid).length;
  }, [activeChip, tapEvents]);

  const handleOpenReplaceModal = (chip: ChipView) => {
    if(chip.item_id){proto.openWork(chip.item_id,chip.chip_status==='lost'?'loss':'periodic');return;}
    setReplaceModalChipId(chip.id);
    setReplaceScenario(chip.chip_status === 'lost' ? 'loss_replacement' : 'resale_new_carrier');
    setReplaceNewChipId(null);
    setReplaceReason(
      chip.chip_status === 'lost' ? '原芯片损坏/遗失已挂失，启用新芯片接续该商品' : ''
    );
  };

  const bindModalChip = useMemo(
    () => chips.find((c) => c.id === bindModalChipId) || null,
    [chips, bindModalChipId]
  );

  const keyModalChip = useMemo(
    () => chips.find((c) => c.id === keyModalChipId) || null,
    [chips, keyModalChipId]
  );

  useEffect(() => {
    if (activeChip) {
      setDrawerBatchInput(activeChip.batch_no || '');
      setDrawerIsValidation(Boolean(activeChip.is_validation_object));
      setDrawerValidationNote(activeChip.validation_note || '');
    }
  }, [activeChip]);

  // P0-1：计算当前芯片详情抽屉是否存在未保存的维护字段修改
  const drawerDirty = useMemo(() => {
    if (!activeChip) return false;
    const origBatch = activeChip.batch_no || '';
    const origVal = Boolean(activeChip.is_validation_object);
    const origNote = activeChip.validation_note || '';
    const curBatch = drawerBatchInput.trim();
    const curNote = drawerIsValidation ? drawerValidationNote.trim() : '';
    return (
      curBatch !== origBatch ||
      drawerIsValidation !== origVal ||
      (drawerIsValidation && curNote !== origNote)
    );
  }, [activeChip, drawerBatchInput, drawerIsValidation, drawerValidationNote]);

  // P0-1：抽屉关闭、切换另一行芯片或跨页跳转前的未保存拦截保护
  const guardDrawerBeforeAction = (action: () => void) => {
    if (!drawerDirty) {
      action();
      return;
    }
    Modal.confirm({
      title: '放弃芯片详情中未保存的修改？',
      content: `芯片 ${activeChip?.chip_uid} 的批次号或验证标识已修改但尚未点击「保存维护字段」，确定放弃修改并离开吗？`,
      okText: '放弃修改并离开',
      okButtonProps: { danger: true },
      cancelText: '留在当前抽屉',
      onOk: () => action(),
    });
  };

  const handleOpenBindModal = (chip: ChipView) => {
    setBindModalChipId(chip.id);
    setBindCandidateProject(chip.project || 'fashion');
    setBindCandidateKeyword('');
    setSelectedCandidateId(null);
    setBindConfirmedCheck(false);
    setBindError('');
  };

  const handleOpenKeyModal = (chip: ChipView) => {
    setKeyModalChipId(chip.id);
    setKeyViewAck(false);
    setRevealedKeys(null);
    setTapLink1('');
    setTapLink2('');
    setK0ManualConfirmed(false);
    setKeyModalError('');
    setKeyModalSuccess('');
  };

  const getChipKeywordMatches = (chip: ChipView, rawKeyword: string): string[] => {
    const q = rawKeyword.trim().toLowerCase();
    if (!q) return [];
    const qNoColon = q.replace(/:/g, '');
    const uidClean = chip.chip_uid.toLowerCase().replace(/:/g, '');
    const matches: string[] = [];
    if (chip.chip_uid.toLowerCase().includes(q) || uidClean.includes(qNoColon)) {
      matches.push('芯片UID');
    }
    if (chip.item_uid && chip.item_uid.toLowerCase().includes(q)) {
      matches.push('物品编号');
    }
    if (chip.item_id) {
      const linkedItem = items.find((i) => i.id === chip.item_id);
      if (
        linkedItem?.profile?.name &&
        linkedItem.profile.name.toLowerCase().includes(q)
      ) {
        matches.push('物品名称');
      }
    }
    return matches;
  };

  const filteredChips = useMemo(() => {
    return chips.filter((chip) => {
      if (appliedFilters.keyword.trim()) {
        const matches = getChipKeywordMatches(chip, appliedFilters.keyword);
        if (matches.length === 0) return false;
      }
      if (appliedFilters.project === 'unassigned') {
        if (chip.project !== null) return false;
      } else if (appliedFilters.project) {
        if (chip.project !== appliedFilters.project) return false;
      }
      if (appliedFilters.status && chip.chip_status !== appliedFilters.status) {
        return false;
      }
      if (appliedFilters.batchKeyword.trim()) {
        const bq = appliedFilters.batchKeyword.trim().toLowerCase();
        if (!chip.batch_no || !chip.batch_no.toLowerCase().includes(bq)) return false;
      }
      if (appliedFilters.source && chip.registration_source !== appliedFilters.source) {
        return false;
      }
      if (appliedFilters.keyProvisionState === 'no_key' && chip.keys_generated) return false;
      if (
        appliedFilters.keyProvisionState === 'key_only' &&
        (!chip.keys_generated || chip.provisioned_at !== null)
      )
        return false;
      if (appliedFilters.keyProvisionState === 'unprovisioned' && chip.provisioned_at !== null)
        return false;
      if (appliedFilters.keyProvisionState === 'provisioned' && !chip.provisioned_at) return false;

      if (appliedFilters.validationScope === 'formal_only' && chip.is_validation_object) {
        return false;
      }
      if (appliedFilters.validationScope === 'validation_only' && !chip.is_validation_object) {
        return false;
      }
      if (appliedFilters.dateFrom || appliedFilters.dateTo) {
        const rawTime =
          appliedFilters.dateField === 'provisioned_at'
            ? chip.provisioned_at
            : chip.created_at;
        if (!rawTime) return false;
        const dateOnly = rawTime.slice(0, 10);
        if (appliedFilters.dateFrom && dateOnly < appliedFilters.dateFrom) return false;
        if (appliedFilters.dateTo && dateOnly > appliedFilters.dateTo) return false;
      }
      return true;
    });
  }, [chips, items, appliedFilters]);

  const filtersDirty = JSON.stringify(filters) !== JSON.stringify(appliedFilters);

  const handleApplyFilters = () => {
    setAppliedFilters({ ...filters });
    setCurrentPage(1);
  };

  const handleResetFilters = () => {
    setFilters(INITIAL_FILTERS);
    setAppliedFilters(INITIAL_FILTERS);
    setDateRangeResetKey((k) => k + 1);
    setCurrentPage(1);
  };

  const handleSubmitRegister = (keepOpenForNext: boolean) => {
    setRegError('');
    setRegConflictChip(null);
    const validated = normalizeAndValidateChipUid(regUidInput);
    if (!validated.ok) {
      setRegError(validated.error);
      return;
    }
    const batchTrimmed = regBatchNo.trim() || null;
    if (batchTrimmed && [...batchTrimmed].length > 64) {
      return;
    }
    const res = onRegisterChip({
      chip_uid: validated.uid,
      project: regProject || null,
      batch_no: batchTrimmed,
      source: 'manual',
      is_validation_object: regIsValidation,
    });
    if (res.error) {
      setRegError(res.error);
      if (res.chip) {
        setRegConflictChip(res.chip);
      }
      return;
    }

    setRecentActionBanner({
      type: res.is_new ? 'success' : 'info',
      title: res.is_new
        ? `芯片登记成功：${res.chip.chip_uid}`
        : `该 UID 已登记：${res.chip.chip_uid}（保留原记录，未重复覆盖）`,
      description: res.is_new
        ? `状态为「待绑定」${
            res.chip.project
              ? `，所属项目：${PROJECT_SHORT_LABELS[res.chip.project]}`
              : '，项目暂未分配（首次绑定时按目标物品确定）'
          }。当前列表筛选条件已为您保留。`
        : '根据幂等去重规则，原记录的项目、批次、首次来源和绑定状态均保持不变。',
      chip: res.chip,
    });

    setRegUidInput('');
    setRegBatchNo('');
    if (!keepOpenForNext) {
      setRegBatchNo('');
      setRegisterModalOpen(false);
    } else {
      message.success(`已登记 ${res.chip.chip_uid}，可继续输入下一枚芯片 UID`);
    }
  };

  const handleSimulateNfcCoolScan = () => {
    const randomHex = () =>
      Math.floor(Math.random() * 256)
        .toString(16)
        .padStart(2, '0')
        .toUpperCase();
    const uid = `04:${randomHex()}:${randomHex()}:${randomHex()}:80:00`;
    const res = onRegisterChip({
      chip_uid: uid,
      project: null,
      batch_no: null,
      source: 'nfc_cool',
    });
    setRecentActionBanner({
      type: 'success',
      title: `收到手机 NFC.cool 扫码回调：${res.chip.chip_uid}`,
      description:
        '手机批量扫码自动登记为「未分配项目、无批次号、待绑定」。您可以直接点击下方「查看详情与维护批次」或「立即绑定物品」。',
      chip: res.chip,
    });
  };

  const candidateItems = useMemo(() => {
    if (!bindModalChip) return [];
    const targetProj = bindModalChip.project || bindCandidateProject;
    const kw = bindCandidateKeyword.trim().toLowerCase();
    return items.filter((item) => {
      if (item.project !== targetProj) return false;
      if (item.bound_chip_id !== null) return false;
      if (kw) {
        const uidMatch = item.item_uid.toLowerCase().includes(kw);
        const skuMatch = item.sku_code ? item.sku_code.toLowerCase().includes(kw) : false;
        const nameMatch =
          item.profile && typeof item.profile.name === 'string'
            ? item.profile.name.toLowerCase().includes(kw)
            : false;
        if (!uidMatch && !skuMatch && !nameMatch) return false;
      }
      return true;
    });
  }, [items, bindModalChip, bindCandidateProject, bindCandidateKeyword]);

  const selectedCandidateItem = useMemo(
    () => candidateItems.find((i) => i.id === selectedCandidateId) || null,
    [candidateItems, selectedCandidateId]
  );

  const handleConfirmBind = () => {
    if (!bindModalChip || !selectedCandidateItem || !bindConfirmedCheck) return;
    const res = onBindChipToItem(bindModalChip.id, selectedCandidateItem.id);
    if (!res.ok) {
      setBindError(res.error || '绑定未完成');
      return;
    }
    setBindModalChipId(null);
    if (res.chip) {
      setRecentActionBanner({
        type: 'success',
        title: `首次绑定成功：${res.chip.chip_uid} → ${res.chip.item_uid}`,
        description:
          '已建立芯片与数字物品唯一关联。绑定不等于写卡完成，下一步可生成芯片密钥并完成 NFC.cool 实卡配置核验。',
        chip: res.chip,
      });
    }
  };

  const handleRevealKeys = () => {
    if (!keyModalChip || !keyViewAck) return;
    const cleanHex = keyModalChip.chip_uid.replace(/:/g, '');
    setRevealedKeys({
      chip_uid: keyModalChip.chip_uid,
      key_version: keyModalChip.key_version || 'v1',
      keys: {
        K0: '演示占位值，不是真实密钥',
        K1: '演示占位值，不是真实密钥',
        K2: '演示占位值，不是真实密钥',
        K3: '演示占位值，不是真实密钥',
        K4: '演示占位值，不是真实密钥',
      },
      sun_url_template:
        'https://nfc.bumbum.cc/tap?picc_data=00000000000000000000000000000000&cmac=0000000000000000',
    });
  };

  const handleFillDemoTapLinks = () => {
    if (!keyModalChip) return;
    const seed = keyModalChip.id.toString(16).padStart(4, '0').toUpperCase();
    setTapLink1(
      `https://nfc.bumbum.cc/tap?picc_data=FDE4AFA99B5C820A2C1BB0F1${seed}0001&cmac=C48B89C17A23${seed}`
    );
    setTapLink2(
      `https://nfc.bumbum.cc/tap?picc_data=8A31BC74E209415FD062A98C${seed}0002&cmac=91E04D72B53C${seed}`
    );
    setKeyModalError('');
  };

  const handleSubmitProvisioning = () => {
    if (!keyModalChip) return;
    setKeyModalError('');
    setKeyModalSuccess('');
    const check = validateSunTapLinks(tapLink1, tapLink2);
    if (!check.ok) {
      setKeyModalError(check.error || '触碰链接校验未通过');
      return;
    }
    if (!k0ManualConfirmed) {
      setKeyModalError('请勾选确认已人工核对新 K0 可以认证且文件权限符合手册。');
      return;
    }
    const res = onConfirmChipProvisioning(keyModalChip.id);
    if (!res.ok) {
      setKeyModalError(res.error || '配置核验失败');
      return;
    }
    setRevealedKeys(null);
    setTapLink1('');
    setTapLink2('');
    setKeyModalSuccess('实卡配置核验通过！已保存 provisioned_at 完成时间及 SDM 计数基线。');
  };

  const columns: ColumnsType<ChipView> = [
    {
      title: '芯片 UID',
      dataIndex: 'chip_uid',
      key: 'chip_uid',
      width: 175,
      fixed: 'left',
      render: (uid: string, record) => {
        const kwMatches = getChipKeywordMatches(record, appliedFilters.keyword);
        return (
          <div>
            <Space size={4}>
              <Button
                type="link"
                style={{
                  padding: 0,
                  fontWeight: 600,
                  fontSize: 13,
                }}
                onClick={() => {
                  if (record.id === activeChipId) return;
                  guardDrawerBeforeAction(() => onSelectChipId(record.id));
                }}
              >
                {uid}
              </Button>
              <Text copyable={{ text: uid, tooltips: ['复制 UID', '已复制'] }} />
            </Space>
            <div className="mt-0.5 flex flex-wrap gap-1">
              {record.is_validation_object && (
                <Tag color="orange" style={{ fontSize: 11, lineHeight: '16px', margin: 0 }}>
                  生产验证对象
                </Tag>
              )}
              {kwMatches.length > 0 && (
                <Tag color="geekblue" style={{ fontSize: 10, lineHeight: '16px', margin: 0 }}>
                  命中: {kwMatches.join('/')}
                </Tag>
              )}
            </div>
          </div>
        );
      },
    },
    {
      title: '所属项目',
      dataIndex: 'project',
      key: 'project',
      width: 86,
      render: (project: ProjectCode | null) =>
        project ? (
          <Tag color={project === 'fashion' ? 'blue' : 'gold'}>{PROJECT_SHORT_LABELS[project]}</Tag>
        ) : (
          <Tooltip title="绑定目标物品时将自动按物品确定所属项目">
            <Tag color="default">未分配</Tag>
          </Tooltip>
        ),
    },
    {
      title: '芯片状态',
      dataIndex: 'chip_status',
      key: 'chip_status',
      width: 96,
      render: (status: ChipStatus) => {
        const meta = CHIP_STATUS_META[status];
        return (
          <Tooltip title={meta.desc}>
            <Badge status={meta.badge} text={<Tag color={meta.tagColor}>{meta.label}</Tag>} />
          </Tooltip>
        );
      },
    },
    {
      title: '关联数字物品',
      dataIndex: 'item_uid',
      key: 'item_uid',
      width: 185,
      render: (itemUid: string | null, record) => {
        if (!itemUid || !record.item_id) {
          return <Text type="secondary">未关联物品</Text>;
        }
        const linkedItem = items.find((i) => i.id === record.item_id);
        return (
          <div>
            <Button
              type="link"
              size="small"
              icon={<LinkOutlined />}
              style={{
                padding: 0,
              }}
              onClick={() => guardDrawerBeforeAction(() => onOpenItemDetail(record.item_id!))}
            >
              {itemUid}
            </Button>
            {linkedItem?.profile?.name && (
              <div className="text-xs text-slate-500 truncate max-w-[180px]">
                {linkedItem.profile.name}
              </div>
            )}
          </div>
        );
      },
    },
    {
      title: '批次号',
      dataIndex: 'batch_no',
      key: 'batch_no',
      width: 140,
      render: (batchNo: string | null, record) =>
        batchNo ? (
          <Space size={4}>
            <Text code>{batchNo}</Text>
            <Tooltip title="点击在详情中修改批次">
              <Button
                type="text"
                size="small"
                icon={<EditOutlined />}
                onClick={() => {
                  if (record.id === activeChipId) return;
                  guardDrawerBeforeAction(() => onSelectChipId(record.id));
                }}
              />
            </Tooltip>
          </Space>
        ) : (
          <Button
            type="link"
            size="small"
            style={{ padding: 0, fontSize: 12 }}
            onClick={() => {
              if (record.id === activeChipId) return;
              guardDrawerBeforeAction(() => onSelectChipId(record.id));
            }}
          >
            + 补录批次
          </Button>
        ),
    },
    {
      title: '配卡进度',
      key: 'provisioning',
      width: 152,
      render: (_, record) => (
        <Space size={4} wrap>
          <Tag color={record.keys_generated ? 'processing' : 'default'}>
            {record.keys_generated ? '密钥已生' : '密钥未生'}
          </Tag>
          <Tag color={record.provisioned_at ? 'success' : 'default'}>
            {record.provisioned_at ? '配置已核验' : '未核验'}
          </Tag>
        </Space>
      ),
    },
    {
      title: '登记来源',
      dataIndex: 'registration_source',
      key: 'registration_source',
      width: 138,
      render: (src: RegistrationSource) => {
        const info = REGISTRATION_SOURCE_LABELS[src];
        return (
          <Tooltip title={info.tip}>
            <Tag color={info.color}>{info.label}</Tag>
          </Tooltip>
        );
      },
    },
    {
      title: '登记时间',
      dataIndex: 'created_at',
      key: 'created_at',
      width: 148,
      render: (val: string) => (
        <Text type="secondary" style={{ fontSize: 12 }}>
          {new Date(val).toLocaleString('zh-CN', { hour12: false })}
        </Text>
      ),
    },
    {
      title: '操作',
      key: 'actions',
      width: 120,
      fixed: 'right',
      render: (_, record) => (
        <Space size={6} wrap>
          {record.chip_status === 'pending' && record.item_id === null && (
            <Button
              size="small"
              type="primary"
              ghost
              icon={<LinkOutlined />}
              onClick={() => handleOpenBindModal(record)}
            >
              绑定物品
            </Button>
          )}
          {record.chip_status === 'bound' && record.item_id !== null && (
            <Button
              size="small"
              type={record.provisioned_at ? 'default' : 'primary'}
              ghost={!record.provisioned_at}
              icon={<KeyOutlined />}
              onClick={() => handleOpenKeyModal(record)}
            >
              {record.provisioned_at ? '密钥/已核验' : '密钥与配卡'}
            </Button>
          )}
          {record.chip_status === 'lost' && (
            <Button
              size="small"
              danger
              onClick={() => handleOpenReplaceModal(record)}
            >
              查看物品换新权益
            </Button>
          )}
          {(record.chip_status === 'disabled' || record.chip_status === 'retired') && (
            <Text type="secondary" style={{ fontSize: 12 }}>
              —
            </Text>
          )}
        </Space>
      ),
    },
  ];

  const activeChipLifecycle = useMemo(
    () => (activeChip ? evaluateChipLifecycleLevel(activeChip, tapEvents) : null),
    [activeChip, tapEvents]
  );

  const currentStepInKeyModal = useMemo(() => {
    if (!keyModalChip) return 0;
    if (!keyModalChip.keys_generated) return 0;
    if (!keyModalChip.provisioned_at) return 1;
    return 2;
  }, [keyModalChip]);

  return (
    <div className="space-y-4">
      {simulateApiError && (
        <Alert
          type="error"
          showIcon
          icon={<WarningOutlined />}
          message="芯片库存列表读取失败 (502 Bad Gateway)"
          description="未能连接芯片管理服务接口，当前展示为本地缓存快照，请点击重试恢复。"
          action={
            <Button size="small" type="primary" danger onClick={onRecoverApiError}>
              立即重试
            </Button>
          }
        />
      )}

      {recentActionBanner && (
        <Alert
          type={recentActionBanner.type}
          showIcon
          closable
          onClose={() => setRecentActionBanner(null)}
          message={<Text strong>{recentActionBanner.title}</Text>}
          description={
            <div className="mt-1 flex flex-wrap items-center justify-between gap-3">
              <span>{recentActionBanner.description}</span>
              <Space wrap>
                <Button
                  size="small"
                  type="primary"
                  onClick={() =>
                    guardDrawerBeforeAction(() => onSelectChipId(recentActionBanner.chip.id))
                  }
                >
                  查看详情与维护批次
                </Button>
                {recentActionBanner.chip.chip_status === 'pending' &&
                  recentActionBanner.chip.item_id === null && (
                    <Button
                      size="small"
                      icon={<LinkOutlined />}
                      onClick={() => handleOpenBindModal(recentActionBanner.chip)}
                    >
                      立即绑定物品
                    </Button>
                  )}
                {recentActionBanner.chip.chip_status === 'bound' &&
                  !recentActionBanner.chip.provisioned_at && (
                    <Button
                      size="small"
                      icon={<KeyOutlined />}
                      onClick={() => handleOpenKeyModal(recentActionBanner.chip)}
                    >
                      继续生成密钥与配卡核验
                    </Button>
                  )}
                <Button
                  size="small"
                  onClick={() => {
                    setRegError('');
                    setRegisterModalOpen(true);
                  }}
                >
                  继续登记下一枚
                </Button>
              </Space>
            </div>
          }
        />
      )}

      <Card size="small" styles={{ body: { padding: '16px 20px' } }}>
        <Row gutter={[12, 12]} align="bottom">
          <Col xs={24} md={8} lg={7}>
            <div className="text-xs font-medium text-slate-600 mb-1">关键词</div>
            <Input
              allowClear
              placeholder="搜索芯片 UID、物品编号或物品名称"
              value={filters.keyword}
              onChange={(e) => setFilters({ ...filters, keyword: e.target.value })}
              onPressEnter={handleApplyFilters}
            />
          </Col>
          <Col xs={12} md={5} lg={4}>
            <div className="text-xs font-medium text-slate-600 mb-1">所属项目</div>
            <Select
              style={{ width: '100%' }}
              value={filters.project}
              onChange={(val) => setFilters({ ...filters, project: val })}
              options={[
                { value: '', label: '全部项目' },
                { value: 'unassigned', label: '未分配' },
                { value: 'fashion', label: '服装' },
                { value: 'jewelry', label: '饰品' },
              ]}
            />
          </Col>
          <Col xs={12} md={5} lg={4}>
            <div className="text-xs font-medium text-slate-600 mb-1">芯片状态</div>
            <Select
              style={{ width: '100%' }}
              value={filters.status}
              onChange={(val) => setFilters({ ...filters, status: val })}
              options={[
                { value: '', label: '全部状态' },
                { value: 'pending', label: '待绑定' },
                { value: 'bound', label: '已绑定' },
                { value: 'disabled', label: '已停用' },
                { value: 'lost', label: '已挂失' },
                { value: 'retired', label: '已退役' },
              ]}
            />
          </Col>
          <Col xs={24} md={6} lg={9}>
            <Space wrap>
              <Button type="primary" icon={<SearchOutlined />} onClick={handleApplyFilters}>
                查询
              </Button>
              <Button icon={<ReloadOutlined />} onClick={handleResetFilters}>
                重置
              </Button>
              <Button
                type="link"
                icon={expandAdvanced ? <UpOutlined /> : <DownOutlined />}
                onClick={() => setExpandAdvanced(!expandAdvanced)}
              >
                {expandAdvanced ? '收起筛选' : '更多筛选'}
              </Button>
            </Space>
          </Col>
        </Row>

        {expandAdvanced && (
          <div className="mt-3 pt-3 border-t border-slate-100 space-y-3">
            <Row gutter={[12, 12]}>
              <Col xs={24} sm={6}>
                <div className="text-xs font-medium text-slate-600 mb-1">批次号</div>
                <Input
                  allowClear
                  placeholder="输入批次号如 HZ-202610"
                  value={filters.batchKeyword}
                  onChange={(e) => setFilters({ ...filters, batchKeyword: e.target.value })}
                  onPressEnter={handleApplyFilters}
                />
              </Col>
              <Col xs={24} sm={6}>
                <div className="text-xs font-medium text-slate-600 mb-1">登记来源</div>
                <Select
                  style={{ width: '100%' }}
                  value={filters.source}
                  onChange={(val) => setFilters({ ...filters, source: val })}
                  options={[
                    { value: '', label: '全部来源' },
                    { value: 'nfc_cool', label: '手机扫描 (NFC.cool)' },
                    { value: 'manual', label: '网页手工登记' },
                    { value: 'unknown', label: '历史未知' },
                  ]}
                />
              </Col>
              <Col xs={24} sm={6}>
                <div className="text-xs font-medium text-slate-600 mb-1">配卡进度</div>
                <Select
                  style={{ width: '100%' }}
                  value={filters.keyProvisionState}
                  onChange={(val) => {
                    const isUnprovisioned =
                      val === 'unprovisioned' || val === 'no_key' || val === 'key_only';
                    setFilters({
                      ...filters,
                      keyProvisionState: val,
                      dateField:
                        isUnprovisioned && filters.dateField === 'provisioned_at'
                          ? 'created_at'
                          : filters.dateField,
                    });
                  }}
                  options={[
                    { value: '', label: '全部配卡进度' },
                    { value: 'unprovisioned', label: '待完成实卡核验（含未生密钥/待核验）' },
                    { value: 'no_key', label: '未生成密钥' },
                    { value: 'key_only', label: '已生成密钥 · 待核验' },
                    { value: 'provisioned', label: '已完成实卡配置核验' },
                  ]}
                />
              </Col>
              <Col xs={24} sm={6}>
                <div className="text-xs font-medium text-slate-600 mb-1">数据性质</div>
                <Select
                  style={{ width: '100%' }}
                  value={filters.validationScope}
                  onChange={(val) => setFilters({ ...filters, validationScope: val })}
                  options={[
                    { value: '', label: '全部记录' },
                    { value: 'formal_only', label: '仅正式业务芯片' },
                    { value: 'validation_only', label: '仅生产验证测试对象' },
                  ]}
                />
              </Col>
            </Row>

            <Row gutter={[12, 12]} align="bottom">
              <Col xs={24} sm={6}>
                <div className="text-xs font-medium text-slate-600 mb-1">日期类型</div>
                <Select
                  style={{ width: '100%' }}
                  value={filters.dateField}
                  onChange={(val) => setFilters({ ...filters, dateField: val })}
                  options={[
                    { value: 'created_at', label: '登记日期' },
                    {
                      value: 'provisioned_at',
                      label:
                        filters.keyProvisionState === 'unprovisioned' ||
                        filters.keyProvisionState === 'no_key' ||
                        filters.keyProvisionState === 'key_only'
                          ? '实卡核验日期（待核验芯片无此日期）'
                          : '实卡核验日期',
                      disabled:
                        filters.keyProvisionState === 'unprovisioned' ||
                        filters.keyProvisionState === 'no_key' ||
                        filters.keyProvisionState === 'key_only',
                    },
                  ]}
                />
              </Col>
              <Col xs={24} sm={10}>
                <div className="text-xs font-medium text-slate-600 mb-1">日期范围</div>
                <RangePicker
                  key={dateRangeResetKey}
                  style={{ width: '100%' }}
                  onChange={(_, dateStrings) => {
                    const [start, end] = Array.isArray(dateStrings) ? dateStrings : ['', ''];
                    setFilters({
                      ...filters,
                      dateFrom: start || '',
                      dateTo: end || '',
                    });
                  }}
                />
              </Col>
            </Row>
          </div>
        )}

        {filtersDirty && (
          <Alert
            className="mt-3"
            type="info"
            showIcon
            message="筛选条件已更改，点击「查询芯片」或按回车后按新条件过滤列表。"
          />
        )}

        {!expandAdvanced &&
          (appliedFilters.batchKeyword ||
            appliedFilters.source ||
            appliedFilters.keyProvisionState ||
            appliedFilters.validationScope ||
            appliedFilters.dateFrom ||
            appliedFilters.dateTo) && (
            <div className="mt-2.5 pt-2 border-t border-slate-100 flex flex-wrap items-center gap-1.5 text-xs text-slate-500">
              <span>已生效高级筛选（收起后仍保留）：</span>
              {appliedFilters.batchKeyword && (
                <Tag color="blue">批次含: {appliedFilters.batchKeyword}</Tag>
              )}
              {appliedFilters.source && (
                <Tag color="blue">
                  来源: {REGISTRATION_SOURCE_LABELS[appliedFilters.source].label}
                </Tag>
              )}
              {appliedFilters.keyProvisionState && (
                <Tag color="blue">配卡进度: {appliedFilters.keyProvisionState}</Tag>
              )}
              {appliedFilters.validationScope && (
                <Tag color="blue">
                  性质: {appliedFilters.validationScope === 'formal_only' ? '仅正式' : '仅验证'}
                </Tag>
              )}
              {(appliedFilters.dateFrom || appliedFilters.dateTo) && (
                <Tag color="blue">
                  {appliedFilters.dateField === 'provisioned_at' ? '核验日期' : '登记日期'}:{' '}
                  {appliedFilters.dateFrom || '不限'} ~ {appliedFilters.dateTo || '不限'}
                </Tag>
              )}
            </div>
          )}
      </Card>

      <Card
        size="small"
        title={
          <Space>
            <span>芯片列表</span>
            <Tag color="blue">共 {filteredChips.length} 枚</Tag>
          </Space>
        }
        extra={
          <Space size={12} wrap>
            <div className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded bg-purple-50 border border-dashed border-purple-200">
              <Tag color="purple" style={{ margin: 0, fontSize: 11 }}>
                原型演示
              </Tag>
              <Tooltip title="模拟单台手机使用 NFC.cool 批量读卡并通过 HTTPS Basic Auth 自动回调入库">
                <Button
                  size="small"
                  type="link"
                  icon={<MobileOutlined />}
                  style={{ padding: 0, color: '#7e22ce', fontSize: 12 }}
                  onClick={()=>Modal.info({title:'手机扫描登记',content:'正式版本沿用现有手机登记能力。当前原型不连接NFC.cool，不生成假回调记录。'})}
                >
                  查看手机扫描登记说明
                </Button>
              </Tooltip>
            </div>
            <Button
              size="small"
              type="primary"
              icon={<PlusOutlined />}
              onClick={() => {
                setRegError('');
                setRegisterModalOpen(true);
              }}
            >
              手工登记芯片
            </Button>
          </Space>
        }
      >
        <Table
          rowKey="id"
          size="middle"
          columns={columns}
          dataSource={filteredChips}
          scroll={{ x: 1020 }}
          pagination={{
            current: currentPage,
            pageSize: 20,
            total: filteredChips.length,
            showSizeChanger: false,
            onChange: (p) => setCurrentPage(p),
            showTotal: (total) => `共 ${total} 枚芯片（每页固定 20 条）`,
          }}
          locale={{
            emptyText: (
              <Empty
                image={Empty.PRESENTED_IMAGE_SIMPLE}
                description="没有符合当前筛选条件的芯片记录"
              >
                <Space>
                  <Button size="small" onClick={handleResetFilters}>
                    清空筛选条件
                  </Button>
                  <Button
                    size="small"
                    type="primary"
                    onClick={() => setRegisterModalOpen(true)}
                  >
                    登记新芯片
                  </Button>
                </Space>
              </Empty>
            ),
          }}
        />
      </Card>

      <Modal
        title="手工登记芯片"
        open={registerModalOpen}
        onCancel={closeRegister}
        footer={[
          <Button key="cancel" onClick={closeRegister}>
            取消
          </Button>,
          <Button key="continue" onClick={() => handleSubmitRegister(true)}>
            登记并继续下一枚
          </Button>,
          <Button key="submit" type="primary" onClick={() => handleSubmitRegister(false)}>
            确认登记
          </Button>,
        ]}
        width={520}
      >
        <Form layout="vertical" style={{ marginTop: 12 }}>
          <Form.Item
            label="芯片 UID"
            required
            extra={
              <Button
                type="link"
                size="small"
                style={{ padding: 0 }}
                onClick={() => {
                  const hex = Math.floor(16 + Math.random() * 239)
                    .toString(16)
                    .toUpperCase();
                  setRegUidInput(`04:A2:7F:1B:5E:80:${hex}`);
                  setRegError('');
                }}
              >
                填入示例 UID
              </Button>
            }
            style={{ marginBottom: 16 }}
          >
            <Input
              allowClear
              placeholder="如 04:A2:7F:1B:5E:80:18 或 04a27f1b5e8018"
              value={regUidInput}
              onChange={(e) => {
                setRegUidInput(e.target.value);
                setRegError('');
              }}
            />
          </Form.Item>

          <Row gutter={12}>
            <Col span={12}>
              <Form.Item label="所属项目" style={{ marginBottom: 16 }}>
                <Select
                  style={{ width: '100%' }}
                  value={regProject}
                  onChange={(val) => setRegProject(val)}
                  options={[
                    { value: '', label: '暂不分配' },
                    { value: 'fashion', label: '服装' },
                    { value: 'jewelry', label: '饰品' },
                  ]}
                />
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item
                label="批次号"
                validateStatus={[...regBatchNo.trim()].length > 64 ? 'error' : undefined}
                help={
                  [...regBatchNo.trim()].length > 64
                    ? `最多 64 个字符（当前 ${[...regBatchNo.trim()].length}/64）`
                    : undefined
                }
                style={{ marginBottom: 16 }}
              >
                <Input
                  allowClear
                  placeholder="选填，如 HZ-202610-F03"
                  value={regBatchNo}
                  onChange={(e) => setRegBatchNo(e.target.value)}
                />
              </Form.Item>
            </Col>
          </Row>

          <Form.Item label="生产验证测试对象" style={{ marginBottom: regError || regConflictChip ? 16 : 0 }}>
            <Space>
              <Switch disabled checked={regIsValidation} onChange={setRegIsValidation} />
              <Text type="secondary" style={{ fontSize: 12 }}>
                用于上线验证并在验证后可集中退出清理
              </Text>
            </Space>
          </Form.Item>

          {regError && <Alert type="error" showIcon message={regError} />}
          {regConflictChip && (
            <div className="flex items-center justify-between p-2.5 rounded bg-amber-50 border border-amber-200 text-xs mt-3">
              <span>
                已存在原记录：<Text code>{regConflictChip.chip_uid}</Text>（原项目：
                {regConflictChip.project ? PROJECT_SHORT_LABELS[regConflictChip.project] : '未分配'}
                ）
              </span>
              <Button
                size="small"
                type="primary"
                ghost
                onClick={() => {
                  setRegisterModalOpen(false);
                  setRegConflictChip(null);
                  guardDrawerBeforeAction(() => onSelectChipId(regConflictChip.id));
                }}
              >
                查看确切原记录 →
              </Button>
            </div>
          )}
        </Form>
      </Modal>

      <Modal
        title="首次绑定数字物品"
        open={bindModalChip !== null}
        onCancel={() => {
          if (selectedCandidateId !== null) {
            Modal.confirm({
              title: '放弃本次绑定选择？',
              content: '已选择候选数字物品但尚未提交确认，确定关闭弹窗吗？',
              okText: '确认关闭',
              cancelText: '返回继续',
              onOk: () => setBindModalChipId(null),
            });
            return;
          }
          setBindModalChipId(null);
        }}
        width={780}
        footer={[
          <Button key="cancel" onClick={() => setBindModalChipId(null)}>
            取消
          </Button>,
          <Button
            key="submit"
            type="primary"
            disabled={!selectedCandidateItem || !bindConfirmedCheck}
            onClick={handleConfirmBind}
          >
            确认首次绑定
          </Button>,
        ]}
      >
        {bindModalChip && (
          <div className="space-y-4">
            <Descriptions
              size="small"
              bordered
              column={2}
              items={[
                {
                  key: 'uid',
                  label: '目标芯片 UID',
                  children: <Text code>{bindModalChip.chip_uid}</Text>,
                },
                {
                  key: 'proj',
                  label: '当前芯片项目',
                  children: bindModalChip.project ? (
                    <Tag color={bindModalChip.project === 'fashion' ? 'blue' : 'gold'}>
                      {PROJECT_SHORT_LABELS[bindModalChip.project]}（仅列同项目候选）
                    </Tag>
                  ) : (
                    <Tag color="processing">未分配（绑定后将按所选物品确定项目）</Tag>
                  ),
                },
                {
                  key: 'batch',
                  label: '芯片批次',
                  children: bindModalChip.batch_no || '未填写',
                },
                {
                  key: 'status',
                  label: '当前状态',
                  children: <Tag color="blue">待绑定</Tag>,
                },
              ]}
            />

            <div className="flex flex-wrap items-center justify-between gap-3 bg-slate-50 p-3 rounded border border-slate-200">
              <Space wrap>
                <span className="text-xs font-medium text-slate-600">候选项目：</span>
                <Select
                  style={{ width: 150 }}
                  disabled={bindModalChip.project !== null}
                  value={bindModalChip.project || bindCandidateProject}
                  onChange={(val) => {
                    setBindCandidateProject(val);
                    setSelectedCandidateId(null);
                    setBindConfirmedCheck(false);
                  }}
                  options={[
                    { value: 'fashion', label: '服装 (Fashion)' },
                    { value: 'jewelry', label: '饰品 (Jewelry)' },
                  ]}
                />
                <Input
                  allowClear
                  style={{ width: 260 }}
                  placeholder="搜索物品编号、款式编号或名称"
                  value={bindCandidateKeyword}
                  onChange={(e) => {
                    setBindCandidateKeyword(e.target.value);
                    setSelectedCandidateId(null);
                    setBindConfirmedCheck(false);
                  }}
                />
              </Space>
              <Text type="secondary" style={{ fontSize: 12 }}>
                已自动过滤掉已被其他芯片占用的物品（共 {candidateItems.length} 件可绑定）
              </Text>
            </div>

            <Table
              rowKey="id"
              size="small"
              pagination={{ pageSize: 5, showSizeChanger: false }}
              dataSource={candidateItems}
              onRow={(record) => ({
                onClick: () => {
                  if (record.status === 'archived') return;
                  setSelectedCandidateId(record.id);
                  setBindConfirmedCheck(false);
                  setBindError('');
                },
                style: {
                  cursor: record.status === 'archived' ? 'not-allowed' : 'pointer',
                  background: selectedCandidateId === record.id ? '#eff6ff' : undefined,
                },
              })}
              columns={[
                {
                  title: '选择',
                  key: 'select',
                  width: 65,
                  render: (_, record) => (
                    <Radio
                      checked={selectedCandidateId === record.id}
                      disabled={record.status === 'archived'}
                      aria-label={`选择物品 ${record.item_uid}`}
                      onChange={() => {
                        if (record.status === 'archived') return;
                        setSelectedCandidateId(record.id);
                        setBindConfirmedCheck(false);
                        setBindError('');
                      }}
                    />
                  ),
                },
                {
                  title: '物品编号',
                  dataIndex: 'item_uid',
                  width: 170,
                  render: (val: string) => <Text code>{val}</Text>,
                },
                {
                  title: '名称',
                  key: 'name',
                  render: (_, record) =>
                    record.profile?.name ? (
                      <Text>{record.profile.name}</Text>
                    ) : (
                      <Tag color="default">未填写名称（允许先绑定）</Tag>
                    ),
                },
                {
                  title: '款式编号',
                  dataIndex: 'sku_code',
                  width: 160,
                  render: (val: string | null) => val || '—',
                },
                {
                  title: '状态',
                  dataIndex: 'status',
                  width: 90,
                  render: (st: ItemView['status']) => (
                    <Tag color={ITEM_STATUS_META[st].tagColor}>{ITEM_STATUS_META[st].label}</Tag>
                  ),
                },
              ]}
              locale={{
                emptyText: (
                  <Empty
                    image={Empty.PRESENTED_IMAGE_SIMPLE}
                    description="当前项目下没有未被芯片占用的可绑定物品"
                  />
                ),
              }}
            />

            {selectedCandidateItem && (
              <div className="p-3.5 rounded-lg bg-blue-50/70 border border-blue-200 space-y-2">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <Text strong>
                    即将建立绑定映射：<Text code>{bindModalChip.chip_uid}</Text> →{' '}
                    <Tag color="blue">{PROJECT_SHORT_LABELS[selectedCandidateItem.project]}</Tag>
                    <Text code>{selectedCandidateItem.item_uid}</Text>
                  </Text>
                  {bindModalChip.project === null && (
                    <Tag color="geekblue">
                      芯片项目将确定为：{PROJECT_SHORT_LABELS[selectedCandidateItem.project]}
                    </Tag>
                  )}
                </div>
                <Checkbox
                  checked={bindConfirmedCheck}
                  onChange={(e) => setBindConfirmedCheck(e.target.checked)}
                >
                  我已核对芯片 UID 与目标物品编号无误；理解绑定仅建立关联，不自动写卡或生成密钥，误绑定需走 C 专用纠错流程。
                </Checkbox>
              </div>
            )}

            {bindError && <Alert type="error" showIcon message={bindError} />}
          </div>
        )}
      </Modal>

      <Modal
        title="芯片密钥生成、受控查看与实卡配置核验"
        open={keyModalChip !== null}
        onCancel={() => {
          if (tapLink1 || tapLink2) {
            Modal.confirm({
              title: '放弃未提交的触碰链接核验？',
              content: '当前已填写实卡触碰链接但尚未提交核验，确定关闭窗口吗？',
              okText: '确认关闭',
              cancelText: '继续核验',
              onOk: () => {
                setRevealedKeys(null);
                setKeyModalChipId(null);
              },
            });
            return;
          }
          setRevealedKeys(null);
          setKeyModalChipId(null);
        }}
        width={760}
        footer={[
          <Button
            key="close"
            onClick={() => {
              setRevealedKeys(null);
              setKeyModalChipId(null);
            }}
          >
            关闭窗口
          </Button>,
        ]}
      >
        {keyModalChip && (
          <div className="space-y-5 pt-2">
            <div className="flex flex-wrap items-center justify-between gap-2 bg-slate-50 p-3 rounded border border-slate-200">
              <Space split={<Divider type="vertical" />} wrap>
                <span>
                  芯片：<Text code>{keyModalChip.chip_uid}</Text>
                </span>
                <span>
                  关联物品：<Text code>{keyModalChip.item_uid}</Text>
                </span>
                <span>
                  项目：
                  {keyModalChip.project ? PROJECT_SHORT_LABELS[keyModalChip.project] : '未分配'}
                </span>
              </Space>
              <Space>
                <Tag color={keyModalChip.keys_generated ? 'blue' : 'default'}>
                  {keyModalChip.keys_generated ? '密钥已生成 (v1)' : '密钥未生成'}
                </Tag>
                <Tag color={keyModalChip.provisioned_at ? 'success' : 'warning'}>
                  {keyModalChip.provisioned_at ? '实卡配置已核验' : '实卡配置未核验'}
                </Tag>
              </Space>
            </div>

            <Steps
              size="small"
              current={currentStepInKeyModal}
              items={[
                {
                  title: '1. 生成芯片密钥',
                  description: keyModalChip.keys_generated ? '已加密保存 K0–K4' : '派生并加密存库',
                },
                {
                  title: '2. 受控查看与工具配卡',
                  description: keyModalChip.provisioned_at
                    ? '已完成实卡写入'
                    : revealedKeys
                      ? '明文密钥展示中'
                      : '二次确认查看并写入实卡',
                },
                {
                  title: '3. 双链接动态读数核验',
                  description: keyModalChip.provisioned_at ? '已完成核验与基线' : '提交两次触碰链接',
                },
              ]}
            />

            {keyModalSuccess && <Alert type="success" showIcon message={keyModalSuccess} />}
            {keyModalError && <Alert type="error" showIcon message={keyModalError} />}

            <Card size="small" title="第一步 & 第二步：生成密钥与受控明文查看">
              <div className="space-y-3">
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <div>
                    <Text strong>1. 生成并保存芯片密钥</Text>
                    <div className="text-xs text-slate-500">
                      生成密钥仅在后端派生并信封加密保存，不会自动写入物理卡片；已有密钥禁止覆盖。
                    </div>
                  </div>
                  <Button
                    type="primary"
                    disabled={keyModalChip.keys_generated}
                    onClick={() => {
                      const res = onGenerateChipKeys(keyModalChip.id);
                      if (res.ok) {
                        setKeyModalSuccess(
                          '芯片密钥已生成并加密保存，请勾选下方确认后查看密钥并按手册配卡。'
                        );
                      } else {
                        setKeyModalError(res.error || '生成失败');
                      }
                    }}
                  >
                    {keyModalChip.keys_generated ? '密钥已生成 (不可覆盖)' : '生成芯片密钥'}
                  </Button>
                </div>

                <Divider style={{ margin: '10px 0' }} />

                <div className="space-y-2">
                  <Checkbox
                    checked={keyViewAck}
                    disabled={!keyModalChip.keys_generated}
                    onChange={(e) => setKeyViewAck(e.target.checked)}
                  >
                    <Text strong>我确认查看密钥：</Text>
                    理解其中 <Text code>K1</Text> 是同版本跨项目全局共享秘密（影响所有项目的同版本芯片），明文仅用于本次配卡，关闭弹窗后立即清除。
                  </Checkbox>
                  <div>
                    {!revealedKeys ? (
                      <Button
                        icon={<EyeOutlined />}
                        disabled={!keyModalChip.keys_generated || !keyViewAck}
                        onClick={handleRevealKeys}
                      >
                        受控查看 K0–K4 密钥与 SUN 模板
                      </Button>
                    ) : (
                      <Button
                        danger
                        icon={<EyeInvisibleOutlined />}
                        onClick={() => setRevealedKeys(null)}
                      >
                        隐藏并清除明文密钥
                      </Button>
                    )}
                  </div>
                </div>

                {revealedKeys && (
                  <div className="p-3 rounded-lg bg-slate-900 text-slate-100 space-y-2 font-mono text-xs">
                    <div className="flex items-center justify-between text-amber-300 font-sans">
                      <span>
                        安全提示：本次查看已记录管理员审计日志（含时间与访问指纹），Cache-Control: no-store
                      </span>
                      <span>版本：{revealedKeys.key_version}</span>
                    </div>
                    {Object.entries(revealedKeys.keys).map(([kName, kVal]) => (
                      <div
                        key={kName}
                        className="flex items-center justify-between bg-slate-800 px-3 py-1.5 rounded"
                      >
                        <span>
                          <strong className="text-blue-300 mr-2">{kName}</strong>
                          {kName === 'K1' && (
                            <Tag color="red" style={{ fontSize: 10 }}>
                              全局共享 SDM Meta Read
                            </Tag>
                          )}
                          {kName === 'K2' && (
                            <Tag color="cyan" style={{ fontSize: 10 }}>
                              单卡独立 SDM File Read MAC
                            </Tag>
                          )}
                        </span>
                        <Space>
                          <span className="tracking-wider select-all">{kVal}</span>
                          <Text copyable={{ text: kVal }} style={{ color: '#93c5fd' }} />
                        </Space>
                      </div>
                    ))}
                    <div className="pt-1 text-slate-300 font-sans">
                      固定 NDEF URL 模板：
                      <code className="text-emerald-300 ml-1">
                        https://nfc.bumbum.cc/tap?picc_data=...&cmac=...
                      </code>
                    </div>
                  </div>
                )}
              </div>
            </Card>

            <Card
              size="small"
              title="第三步：实卡配置后双链接动态读数核验"
              extra={
                !keyModalChip.provisioned_at &&
                keyModalChip.keys_generated && (
                  <div className="inline-flex items-center gap-1 px-2 py-0.5 rounded bg-purple-50 border border-dashed border-purple-200">
                    <Tag color="purple" style={{ margin: 0, fontSize: 10 }}>
                      演示
                    </Tag>
                    <Button
                      type="link"
                      size="small"
                      style={{ padding: 0, color: '#7e22ce', fontSize: 12 }}
                      onClick={handleFillDemoTapLinks}
                    >
                      填入两条递增测试触碰链接
                    </Button>
                  </div>
                )
              }
            >
              {keyModalChip.provisioned_at ? (
                <Alert
                  type="success"
                  showIcon
                  message={`已完成实卡配置核验（核验时间：${new Date(
                    keyModalChip.provisioned_at
                  ).toLocaleString('zh-CN', { hour12: false })}）`}
                  description="该芯片已通过双链接防伪验签与计数器递增检查，已保存读取计数基线；不允许重复重置配置。"
                />
              ) : (
                <div className="space-y-3">
                  <div className="text-xs text-slate-500">
                    按手册使用工具完成配卡后，用手机先后触碰卡片两次，复制浏览器打开的两条完整链接（须包含
                    <code className="mx-1">picc_data</code>与<code className="mx-1">cmac</code>
                    ，且第 2 条计数大于第 1 条）。
                  </div>
                  <div>
                    <div className="text-xs font-medium mb-1">第 1 条真实触碰链接</div>
                    <Input
                      disabled={!keyModalChip.keys_generated}
                      placeholder="https://nfc.bumbum.cc/tap?picc_data=...&cmac=..."
                      value={tapLink1}
                      onChange={(e) => {
                        setRevealedKeys(null);
                        setTapLink1(e.target.value);
                      }}
                    />
                  </div>
                  <div>
                    <div className="text-xs font-medium mb-1">第 2 条真实触碰链接（计数须递增）</div>
                    <Input
                      disabled={!keyModalChip.keys_generated}
                      placeholder="https://nfc.bumbum.cc/tap?picc_data=...&cmac=..."
                      value={tapLink2}
                      onChange={(e) => {
                        setRevealedKeys(null);
                        setTapLink2(e.target.value);
                      }}
                    />
                  </div>
                  <Checkbox
                    disabled={!keyModalChip.keys_generated}
                    checked={k0ManualConfirmed}
                    onChange={(e) => setK0ManualConfirmed(e.target.checked)}
                  >
                    我已人工核对新 K0 可以认证且卡片文件权限符合操作手册（SUN 验签不替代此项人工权限检查）。
                  </Checkbox>
                  <div>
                    <Button
                      type="primary"
                      disabled={
                        !keyModalChip.keys_generated ||
                        !tapLink1 ||
                        !tapLink2 ||
                        !k0ManualConfirmed
                      }
                      onClick={handleSubmitProvisioning}
                    >
                      提交双链接并确认配置核验
                    </Button>
                  </div>
                </div>
              )}
            </Card>
          </div>
        )}
      </Modal>

      <Drawer
        title={
          activeChip ? (
            <Space>
              <span>芯片详情</span>
              <Text code>{activeChip.chip_uid}</Text>
              <Tag color={CHIP_STATUS_META[activeChip.chip_status].tagColor}>
                {CHIP_STATUS_META[activeChip.chip_status].label}
              </Tag>
              {drawerDirty && <Tag color="warning">有未保存修改</Tag>}
            </Space>
          ) : (
            '芯片详情'
          )
        }
        width={640}
        open={activeChip !== null}
        onClose={() => guardDrawerBeforeAction(() => onSelectChipId(null))}
      >
        {activeChip && activeChipLifecycle && (
          <div className="space-y-5">
            <Card
              size="small"
              title="基本信息"
            >
              <Descriptions
                size="small"
                bordered
                column={1}
                items={[
                  {
                    key: 'uid',
                    label: '芯片 UID',
                    children: (
                      <Text code copyable={{ text: activeChip.chip_uid }}>
                        {activeChip.chip_uid}
                      </Text>
                    ),
                  },
                  {
                    key: 'source',
                    label: '登记来源',
                    children: (
                      <Tag color={REGISTRATION_SOURCE_LABELS[activeChip.registration_source].color}>
                        {REGISTRATION_SOURCE_LABELS[activeChip.registration_source].label}
                      </Tag>
                    ),
                  },
                  {
                    key: 'project',
                    label: '所属项目',
                    children: (
                      <div className="flex items-center justify-between">
                        {activeChip.project ? (
                          <Tag color={activeChip.project === 'fashion' ? 'blue' : 'gold'}>
                            {PROJECT_SHORT_LABELS[activeChip.project]}
                          </Tag>
                        ) : (
                          <Tag>未分配</Tag>
                        )}
                        {activeChip.chip_status === 'pending' && activeChip.item_id === null && (
                          <Button
                            type="link"
                            size="small"
                            style={{ padding: 0 }}
                            onClick={() => {
                              setEditProjectVal(activeChip.project || '');
                              setEditProjectReason('');
                              setEditProjectModalOpen(true);
                            }}
                          >
                            修改预分配项目
                          </Button>
                        )}
                      </div>
                    ),
                  },
                  {
                    key: 'time',
                    label: '时间记录',
                    children: (
                      <span className="text-xs font-mono text-slate-600">
                        登记：{new Date(activeChip.created_at).toLocaleString('zh-CN', { hour12: false })}
                        <Divider type="vertical" />
                        更新：{new Date(activeChip.updated_at).toLocaleString('zh-CN', { hour12: false })}
                      </span>
                    ),
                  },
                ]}
              />
            </Card>

            <Card size="small" title="日常维护">
              <Form layout="vertical">
                <Row gutter={16}>
                  <Col xs={24} sm={16}>
                    <Form.Item
                      label="批次号"
                      validateStatus={[...drawerBatchInput.trim()].length > 64 ? 'error' : undefined}
                      help={
                        [...drawerBatchInput.trim()].length > 64
                          ? `最多 64 个字符（当前 ${[...drawerBatchInput.trim()].length}/64）`
                          : undefined
                      }
                      style={{ marginBottom: 16 }}
                    >
                      <Input
                        allowClear
                        placeholder="如 HZ-202610-F01"
                        value={drawerBatchInput}
                        onChange={(e) => setDrawerBatchInput(e.target.value)}
                      />
                    </Form.Item>
                  </Col>
                  <Col xs={24} sm={8}>
                    <Form.Item label="生产验证对象" style={{ marginBottom: 16 }}>
                      <Switch
                        disabled checked={drawerIsValidation}
                        checkedChildren="是"
                        unCheckedChildren="否"
                        onChange={(checked) => setDrawerIsValidation(checked)}
                      />
                    </Form.Item>
                  </Col>
                </Row>

                {drawerIsValidation && (
                  <Form.Item label="验证用途备注" style={{ marginBottom: 16 }}>
                    <Input
                      allowClear
                      placeholder="选填，如：杭州公网入口切换首轮实卡验证"
                      disabled value={drawerValidationNote}
                      onChange={(e) => setDrawerValidationNote(e.target.value)}
                    />
                  </Form.Item>
                )}

                <Space>
                  <Button
                    type="primary"
                    disabled={!drawerDirty || [...drawerBatchInput.trim()].length > 64}
                    onClick={() => {
                      onUpdateChipMaintenance(activeChip.id, {
                        batch_no: drawerBatchInput.trim() || null,
                        is_validation_object: drawerIsValidation,
                        validation_note: drawerIsValidation
                          ? drawerValidationNote.trim() || null
                          : null,
                      });
                      message.success(`已保存芯片 ${activeChip.chip_uid} 的维护信息`);
                    }}
                  >
                    保存设置
                  </Button>
                  {drawerDirty && (
                    <Button
                      onClick={() => {
                        setDrawerBatchInput(activeChip.batch_no || '');
                        setDrawerIsValidation(Boolean(activeChip.is_validation_object));
                        setDrawerValidationNote(activeChip.validation_note || '');
                      }}
                    >
                      还原修改
                    </Button>
                  )}
                </Space>
              </Form>
            </Card>

            <Card size="small" title="关联物品与配卡状态">
              <div className="space-y-4">
                <div className="p-3 rounded border border-slate-200 bg-slate-50/60 flex flex-wrap items-center justify-between gap-3">
                  <div>
                    <div className="text-xs text-slate-500">当前关联数字物品</div>
                    {activeChip.item_id && activeChip.item_uid ? (
                      <div className="mt-1">
                        <Space>
                          <Text strong code style={{ fontSize: 14 }}>
                            {activeChip.item_uid}
                          </Text>
                          <Button
                            type="link"
                            size="small"
                            icon={<LinkOutlined />}
                            style={{ padding: 0 }}
                            onClick={() =>
                              guardDrawerBeforeAction(() => onOpenItemDetail(activeChip.item_id!))
                            }
                          >
                            查看物品详情 →
                          </Button>
                        </Space>
                      </div>
                    ) : (
                      <div className="mt-1 text-sm font-medium text-slate-700">
                        尚未关联任何数字物品
                      </div>
                    )}
                  </div>

                  {activeChip.chip_status === 'pending' && activeChip.item_id === null && (
                    <Button
                      type="primary"
                      icon={<LinkOutlined />}
                      onClick={() => handleOpenBindModal(activeChip)}
                    >
                      绑定物品
                    </Button>
                  )}

                  {activeChip.item_id !== null &&
                    activeChip.chip_status !== 'retired' &&
                    (!activeChip.provisioned_at && activeChipTapCount === 0 ? (
                      <Button
                        size="small"
                        onClick={() => {
                          setUnbindMode('unbind_to_pending');
                          setRebindTargetItemId(null);
                          setUnbindReason('');
                          setUnbindModalOpen(true);
                        }}
                      >
                        解绑 / 改绑物品
                      </Button>
                    ) : (
                      <Button
                        size="small"
                        icon={<SwapOutlined />}
                        onClick={() => handleOpenReplaceModal(activeChip)}
                      >
                        查看物品换新权益
                      </Button>
                    ))}
                </div>

                <div className="p-3 rounded border border-slate-200 bg-slate-50/60 flex flex-wrap items-center justify-between gap-3">
                  <div>
                    <div className="text-xs text-slate-500">密钥生成与实卡 SUN 动态配置核验</div>
                    <div className="mt-1">
                      <Space>
                        <Tag color={activeChip.keys_generated ? 'blue' : 'default'}>
                          {activeChip.keys_generated ? 'K0–K4 密钥已生成' : '密钥未生成'}
                        </Tag>
                        <Tag color={activeChip.provisioned_at ? 'success' : 'warning'}>
                          {activeChip.provisioned_at
                            ? `配置已核验 (${new Date(activeChip.provisioned_at).toLocaleDateString('zh-CN')})`
                            : '实卡配置未核验'}
                        </Tag>
                      </Space>
                    </div>
                  </div>
                  {activeChip.item_id !== null && activeChip.chip_status === 'bound' && (
                    <Button
                      icon={<KeyOutlined />}
                      type={activeChip.provisioned_at ? 'default' : 'primary'}
                      onClick={() => handleOpenKeyModal(activeChip)}
                    >
                      {activeChip.provisioned_at ? '查看密钥/核验状态' : '生成密钥与配置核验'}
                    </Button>
                  )}
                </div>
              </div>
            </Card>

            <Card size="small" title="状态与芯片管理">
              <div className="space-y-3">
                <div className="flex items-center justify-between p-3 rounded border border-slate-200">
                  <div>
                    <div className="text-sm font-medium">临时停用 ／ 恢复服务</div>
                    <div className="text-xs text-slate-500">
                      停用后暂停该芯片碰卡验证，保留物品绑定关系。
                    </div>
                  </div>
                  {activeChip.chip_status === 'bound' || activeChip.chip_status === 'pending' ? (
                    <Popconfirm
                      title="确认临时停用该芯片服务？"
                      description="停用后用户碰卡将被阻断，原有关联关系保留。"
                      onConfirm={() => {
                        onToggleChipTempStatus(activeChip.id, 'disabled');
                        message.warning(`芯片 ${activeChip.chip_uid} 已临时停用`);
                      }}
                    >
                      <Button danger size="small" icon={<PauseCircleOutlined />}>
                        临时停用芯片
                      </Button>
                    </Popconfirm>
                  ) : activeChip.chip_status === 'disabled' ? (
                    <Button
                      type="primary"
                      size="small"
                      icon={<PlayCircleOutlined />}
                      onClick={() => {
                        const target = activeChip.item_id ? 'bound' : 'pending';
                        onToggleChipTempStatus(activeChip.id, target);
                        message.success(
                          `芯片已恢复为「${target === 'bound' ? '已绑定' : '待绑定'}」状态`
                        );
                      }}
                    >
                      恢复芯片服务
                    </Button>
                  ) : (
                    <Tag color="default">当前状态不支持普通停用/恢复</Tag>
                  )}
                </div>

                {activeChip.item_id !== null &&
                  (activeChip.chip_status === 'bound' || activeChip.chip_status === 'lost') && (
                    <div className="flex items-center justify-between p-3 rounded border border-slate-200">
                      <div>
                        <div className="text-sm font-medium">芯片挂失与物品换新</div>
                        <div className="text-xs text-slate-500">
                          原芯片损坏或遗失时可挂失冻结旧凭证，并启用新芯片接续原商品档案。
                        </div>
                      </div>
                      <Space size={8}>
                        {activeChip.chip_status === 'bound' && (
                          <Button
                            size="small"
                            danger
                            onClick={() => {
                              setLostReason('');
                              setLostModalOpen(true);
                            }}
                          >
                            挂失芯片
                          </Button>
                        )}
                        <Button
                          size="small"
                          type={activeChip.chip_status === 'lost' ? 'primary' : 'default'}
                          icon={<SwapOutlined />}
                          onClick={() => handleOpenReplaceModal(activeChip)}
                        >
                          查看物品换新权益
                        </Button>
                      </Space>
                    </div>
                  )}

                {(activeChipLifecycle.canDeleteDirectly ||
                  activeChipLifecycle.canExitValidation) && (
                  <div className="flex items-center justify-between p-3 rounded border border-slate-200">
                    <div>
                      <div className="text-sm font-medium">
                        {activeChipLifecycle.canDeleteDirectly
                          ? '删除无关联芯片'
                          : '退出验证测试并释放关联'}
                      </div>
                      <div className="text-xs text-slate-500">
                        {activeChipLifecycle.canDeleteDirectly
                          ? '该芯片未关联物品、未生成密钥且无触碰记录，可直接删除。'
                          : '该生产验证样卡已完成测试，可退出验证服务并释放测试物品关联。'}
                      </div>
                    </div>
                    {activeChipLifecycle.canDeleteDirectly ? (
                      <Button
                        size="small"
                        danger
                        icon={<DeleteOutlined />}
                        onClick={() => {
                          setCleanupReason('');
                          setCleanupModalKind('delete_l1');
                        }}
                      >
                        删除芯片
                      </Button>
                    ) : (
                      <Button
                        size="small"
                        icon={<StopOutlined />}
                        onClick={() => {
                          setCleanupReason('');
                          setCleanupModalKind('exit_l2');
                        }}
                      >
                        退出验证并释放
                      </Button>
                    )}
                  </div>
                )}
              </div>
            </Card>
          </div>
        )}
      </Drawer>

      {/* 1. 修改待绑定芯片预分配项目弹窗 */}
      <Modal
        title="修改预分配项目"
        open={editProjectModalOpen && activeChip !== null}
        onCancel={() => setEditProjectModalOpen(false)}
        okText="确认修改"
        okButtonProps={{ disabled: !editProjectReason.trim() }}
        onOk={() => {
          if (!activeChip) return;
          const res = onCorrectPendingChipProject(
            activeChip.id,
            editProjectVal || null,
            editProjectReason.trim()
          );
          if (res.ok) {
            message.success('已修改芯片预分配项目');
            setEditProjectModalOpen(false);
          } else {
            message.error(res.error || '修改失败');
          }
        }}
        width={460}
      >
        <Form layout="vertical" style={{ marginTop: 12 }}>
          <Form.Item label="目标预分配项目" style={{ marginBottom: 16 }}>
            <Select
              style={{ width: '100%' }}
              value={editProjectVal}
              onChange={(val) => setEditProjectVal(val)}
              options={[
                { value: '', label: '未分配（绑定物品时自动确定）' },
                { value: 'fashion', label: '服装' },
                { value: 'jewelry', label: '饰品' },
              ]}
            />
          </Form.Item>
          <Form.Item label="修改原因" required style={{ marginBottom: 0 }}>
            <Input
              allowClear
              placeholder="如：登记时误选项目"
              value={editProjectReason}
              onChange={(e) => setEditProjectReason(e.target.value)}
            />
          </Form.Item>
        </Form>
      </Modal>

      {/* 2. 未核验芯片解绑 / 改绑弹窗 */}
      <Modal
        title="解绑 ／ 改绑数字物品"
        open={unbindModalOpen && activeChip !== null}
        onCancel={() => setUnbindModalOpen(false)}
        okText="确认执行"
        okButtonProps={{
          disabled:
            !unbindReason.trim() ||
            (unbindMode === 'rebind_to_target' && !rebindTargetItemId),
        }}
        onOk={() => {
          if (!activeChip) return;
          const res = onUnbindOrRebindMisboundChip(
            activeChip.id,
            unbindMode,
            rebindTargetItemId,
            unbindReason.trim()
          );
          if (res.ok) {
            message.success(
              unbindMode === 'unbind_to_pending'
                ? '已解除绑定，芯片恢复为待绑定状态'
                : '已改绑至新目标物品'
            );
            setUnbindModalOpen(false);
          } else {
            message.error(res.error || '操作失败');
          }
        }}
        width={520}
      >
        <Form layout="vertical" style={{ marginTop: 12 }}>
          <Form.Item label="处理方式" style={{ marginBottom: 16 }}>
            <Radio.Group
              value={unbindMode}
              onChange={(e) => setUnbindMode(e.target.value)}
            >
              <Space direction="vertical">
                <Radio value="unbind_to_pending">
                  解除绑定（芯片回到「待绑定」，原物品恢复为「未绑定」）
                </Radio>
                <Radio value="rebind_to_target">直接改绑到另一件未绑定芯片的物品</Radio>
              </Space>
            </Radio.Group>
          </Form.Item>

          {unbindMode === 'rebind_to_target' && (
            <Form.Item label="选择新目标物品" required style={{ marginBottom: 16 }}>
              <Select
                style={{ width: '100%' }}
                placeholder="请选择未绑定芯片的目标物品"
                value={rebindTargetItemId}
                onChange={(val) => setRebindTargetItemId(val)}
                options={items
                  .filter((i) => i.bound_chip_id === null && i.status !== 'archived')
                  .map((i) => ({
                    value: i.id,
                    label: `[${PROJECT_SHORT_LABELS[i.project]}] ${i.item_uid} · ${
                      i.profile?.name || '未填名称'
                    }`,
                  }))}
              />
            </Form.Item>
          )}

          <Form.Item label="原因说明" required style={{ marginBottom: 0 }}>
            <Input
              allowClear
              placeholder="如：配卡前发现选错顺延物品编号"
              value={unbindReason}
              onChange={(e) => setUnbindReason(e.target.value)}
            />
          </Form.Item>
        </Form>
      </Modal>

      {/* 3. 芯片挂失弹窗 */}
      <Modal
        title="挂失芯片"
        open={lostModalOpen && activeChip !== null}
        onCancel={() => setLostModalOpen(false)}
        okText="确认挂失"
        okButtonProps={{ danger: true, disabled: !lostReason.trim() }}
        onOk={() => {
          if (!activeChip) return;
          const res = onReportChipLost(activeChip.id, lostReason.trim());
          if (res.ok) {
            message.warning(`芯片 ${activeChip.chip_uid} 已标记挂失`);
            setLostModalOpen(false);
          } else {
            message.error(res.error || '挂失失败');
          }
        }}
        width={460}
      >
        <Form layout="vertical" style={{ marginTop: 12 }}>
          <Form.Item style={{ marginBottom: 16 }}>
            <Alert
              type="warning"
              showIcon
              message={`挂失后将立即阻断芯片 ${activeChip?.chip_uid} 的碰卡验证与持续查看会话，原物品档案与持有人权益保留，可随时绑定新芯片接续。`}
            />
          </Form.Item>
          <Form.Item label="挂失原因" required style={{ marginBottom: 0 }}>
            <Input
              allowClear
              placeholder="如：客户反馈干洗后芯片损坏无法感应"
              value={lostReason}
              onChange={(e) => setLostReason(e.target.value)}
            />
          </Form.Item>
        </Form>
      </Modal>

      {/* 4. 查看物品换新权益（挂失换新 / 转售换卡）弹窗 */}
      <Modal
        title={
          replaceSourceChip
            ? `查看物品换新权益 · 接续物品 ${replaceSourceChip.item_uid}`
            : '查看物品换新权益'
        }
        open={replaceSourceChip !== null}
        onCancel={() => setReplaceModalChipId(null)}
        okText="确认换卡并退役旧卡"
        okButtonProps={{ disabled: !replaceNewChipId || !replaceReason.trim() }}
        onOk={() => {
          if (!replaceTargetItem || !replaceNewChipId) return;
          const res = onExecuteCarrierReplacement({
            itemId: replaceTargetItem.id,
            newChipId: replaceNewChipId,
            scenario: replaceScenario,
            reason: replaceReason.trim(),
          });
          if (res.ok) {
            message.success(`已完成换卡接续，原芯片 ${replaceSourceChip?.chip_uid} 已退役`);
            setReplaceModalChipId(null);
          } else {
            message.error(res.error || '换卡失败');
          }
        }}
        width={540}
      >
        {replaceSourceChip && (
          <Form layout="vertical" style={{ marginTop: 12 }}>
            <Form.Item label="换卡场景" style={{ marginBottom: 16 }}>
              <Radio.Group
                value={replaceScenario}
                onChange={(e) => setReplaceScenario(e.target.value)}
              >
                <Radio value="loss_replacement">损坏/遗失补卡（保持原持有人权益）</Radio>
                <Radio value="resale_new_carrier">官方回收转售换新卡</Radio>
              </Radio.Group>
            </Form.Item>

            <Form.Item label="选择接续的待绑定新芯片" required style={{ marginBottom: 16 }}>
              <Select
                style={{ width: '100%' }}
                placeholder="请选择一枚待绑定芯片"
                value={replaceNewChipId}
                onChange={(val) => setReplaceNewChipId(val)}
                options={availableReplacementChips.map((c) => ({
                  value: c.id,
                  label: `${c.chip_uid}（${
                    c.project ? PROJECT_SHORT_LABELS[c.project] : '未分配项目'
                  }${c.batch_no ? ` · 批次 ${c.batch_no}` : ''}）`,
                }))}
              />
            </Form.Item>

            <Form.Item label="换卡原因" required style={{ marginBottom: 0 }}>
              <Input
                allowClear
                placeholder="请填写换卡原因"
                value={replaceReason}
                onChange={(e) => setReplaceReason(e.target.value)}
              />
            </Form.Item>
          </Form>
        )}
      </Modal>

      {/* 5. 删除无关联芯片 / 退出验证芯片弹窗 */}
      <Modal
        title={cleanupModalKind === 'delete_l1' ? '删除芯片' : '退出验证测试并释放关联'}
        open={cleanupModalKind !== null && activeChip !== null}
        onCancel={() => setCleanupModalKind(null)}
        okText={cleanupModalKind === 'delete_l1' ? '确认删除' : '确认退出验证'}
        okButtonProps={{
          danger: cleanupModalKind === 'delete_l1',
          disabled: !cleanupReason.trim(),
        }}
        onOk={() => {
          if (!activeChip || !cleanupModalKind) return;
          if (cleanupModalKind === 'delete_l1') {
            const res = onDeleteL1Chip(activeChip.id, cleanupReason.trim());
            if (res.ok) {
              message.success(`已删除芯片 ${activeChip.chip_uid}`);
              setCleanupModalKind(null);
              onSelectChipId(null);
            } else {
              message.error(res.error || '删除失败');
            }
          } else {
            const res = onExitL2ValidationChip(activeChip.id, cleanupReason.trim());
            if (res.ok) {
              message.success(`芯片 ${activeChip.chip_uid} 已退出验证并释放测试物品`);
              setCleanupModalKind(null);
            } else {
              message.error(res.error || '操作失败');
            }
          }
        }}
        width={460}
      >
        <Form layout="vertical" style={{ marginTop: 12 }}>
          <Form.Item label="原因说明" required style={{ marginBottom: 0 }}>
            <Input
              allowClear
              placeholder={
                cleanupModalKind === 'delete_l1'
                  ? '如：手工录入测试 UID，确认无实卡依赖后清理'
                  : '如：线上验证完毕，退出验证样卡并释放测试商品'
              }
              value={cleanupReason}
              onChange={(e) => setCleanupReason(e.target.value)}
            />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
};
