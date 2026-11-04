import React, { createContext, useContext, useEffect, useRef, useState } from 'react';
import type { Dispatch, SetStateAction } from 'react';
import { Modal, message } from 'antd';
import { INITIAL_ITEMS, INITIAL_CHIPS, INITIAL_AUDIT_LOGS } from './mockBackend';
import type { ItemView, ChipView, AuditLogEntry } from './mockBackend';

export const DEMO_YEAR = 2026;
export const DEMO_USERS = [
  { value: 'DEMO-OWNER-A', label: '持有人甲 · 演示账户' },
  { value: 'DEMO-OWNER-B', label: '持有人乙 · 演示账户' },
  { value: 'DEMO-OWNER-C', label: '持有人丙 · 演示账户' },
];
export const userName = (id?: string | null) => DEMO_USERS.find(u => u.value === id)?.label || (id ? '演示持有人' : '未绑定所有人');
export const now = () => new Date().toISOString();
export const timeText = (v?: string | null) => v ? new Date(v).toLocaleString('zh-CN', { timeZone: 'Asia/Shanghai', hour12: false }) : '未记录';
export const mockPicture = 'data:image/svg+xml;charset=utf-8,' + encodeURIComponent('<svg xmlns="http://www.w3.org/2000/svg" width="520" height="480" viewBox="0 0 520 480"><rect width="520" height="480" fill="#f3f5f8"/><path d="M175 85 126 112 55 196 126 247 157 208 157 403 363 403 363 208 394 247 465 196 394 112 345 85 Q260 148 175 85Z" fill="#232b38"/><path d="M215 101 Q260 157 305 101" fill="none" stroke="#828c9b" stroke-width="10"/><text x="260" y="270" text-anchor="middle" fill="#d4dbe5" font-family="sans-serif" font-size="24">BUMBUM</text></svg>');
export interface EntityRecord { id: string; delivery: number; size: string; color: string; chipId: number | null; chipUid: string | null; activatedAt: string | null; exitedAt?: string; reason?: string; }
export interface Identity { series: string | null; edition: string | null; total: number | null; firstOwnerAt: string | null; ownerId: string | null; used: number; quotaReview?: boolean; entities: EntityRecord[]; ownership: { ownerId: string; from: string; to?: string; workId?: string }[]; }
export type WorkKind = 'periodic' | 'loss' | 'resale';
export interface Work {
  id: string; itemId: number; kind: WorkKind; step: number; status: 'processing' | 'shipped' | 'received' | 'completed' | 'cancelled';
  ownerId: string; recipientId: string; size: string; color: string; evidence: string; note: string;
  candidateChipId?: number; preparationRef?: string; dispatchNote?: string; tracking?: string; shippedAt?: string; receivedAt?: string; deliveryEvidence?: string;
  createdAt: string; history: { time: string; text: string }[];
}
interface Data { items: ItemView[]; chips: ChipView[]; auditLogs: AuditLogEntry[]; identities: Record<number, Identity>; works: Work[]; }
type Setter<T> = Dispatch<SetStateAction<T>>;
interface Store extends Data {
  setItems: Setter<ItemView[]>; setChips: Setter<ChipView[]>; setAuditLogs: Setter<AuditLogEntry[]>;
  editItemId: number | null; setEditItemId: Setter<number | null>; issuanceItemId: number | null; setIssuanceItemId: Setter<number | null>;
  activeWorkId: string | null; activeDraft: {itemId:number;kind:WorkKind} | null; openWork: (itemId:number,kind:WorkKind) => void; resumeWork: (id:string)=>void; closeWork:()=>void;
  identity: (item:ItemView)=>Identity; createWork:(data:Omit<Work,'id'|'step'|'status'|'createdAt'|'history'>)=>Work;
  updateWork:(id:string,patch:Partial<Work>,text:string)=>void; completeWork:(id:string,evidence?:string)=>{ok:boolean;error?:string};
  reportLost:(chipId:number,evidence:string)=>void; audit:(category:AuditLogEntry['category'],action:string,target:string,detail:string)=>void;
  failureMode:'none'|'save'|'unknown'|'upload'; setFailureMode:Setter<'none'|'save'|'unknown'|'upload'>;
  guard:(fn:()=>void)=>void; setGuard:(fn:((next:()=>void)=>void)|null)=>void; reset:()=>void;
}
const Context = createContext<Store | null>(null);
const fallback = (item:ItemView):Identity => ({series:null,edition:null,total:null,firstOwnerAt:null,ownerId:null,used:0,entities:item.bound_chip_id?[{id:`E-${item.id}-1`,delivery:1,size:'未记录',color:'未记录',chipId:item.bound_chip_id,chipUid:item.bound_chip_uid,activatedAt:item.bound_chip_provisioned_at}]:[],ownership:[]});
function initial():Data {
  const items = structuredClone(INITIAL_ITEMS), chips=structuredClone(INITIAL_CHIPS);
  // 保留原稿样例规模；两件限定T恤用于核对共享额度、变更尺码和转售归属。
  for(const [index,item] of items.slice(0,2).entries()){
    item.sku_code='BB-TEE-BLK';item.status='active';item.owner_status='claimed';item.owner_account_id=index===0?'DEMO-OWNER-A':'DEMO-OWNER-C';
    item.created_at='2026-03-01T01:20:00Z';item.profile={name:'BUMBUM 限定系列 T 恤 · 黑色',description:'限定100份数字身份，换新与转售保留发行编号。',material:'100%棉',care_instructions:'建议冷水轻柔洗涤，避免高温烘干。',image_urls:[mockPicture],size_chart:'S：胸围100 / 衣长66；M：胸围104 / 衣长68；L：胸围108 / 衣长70；XL：胸围112 / 衣长72（cm）'};
    item.image_assets=[];
  }
  // 离线原型使用内置示意图；不向图片服务或真实业务接口发请求。
  for(const item of items){if(item.profile)item.profile.image_urls=[mockPicture];if(item.image_assets)for(const asset of item.image_assets){asset.url=mockPicture;asset.preview_url=mockPicture;}}
  const identities:Record<number,Identity>={};
  for(const item of items){
    const claimed=item.owner_status==='claimed';const ownerId=item.id===1?'DEMO-OWNER-A':item.id===2?'DEMO-OWNER-C':claimed?'DEMO-OWNER-A':null;
    item.owner_account_id=ownerId;
    identities[item.id]={...fallback(item),ownerId,firstOwnerAt:claimed?'2026-03-12T02:00:00Z':null,series:item.id<=2?'BUMBUM · 限定系列':null,edition:item.id<=2?`#${String(item.id).padStart(3,'0')}/100`:null,total:item.id<=2?100:null,used:item.id===1?1:0,ownership:ownerId?[{ownerId,from:'2026-03-12T02:00:00Z'}]:[]};
    if(item.id<=2){const chip=chips.find(c=>c.id===item.bound_chip_id);if(chip){chip.created_at='2026-03-10T01:00:00Z';chip.provisioned_at='2026-03-12T01:00:00Z';item.bound_chip_provisioned_at=chip.provisioned_at;}}
  }
  identities[1].entities=[{id:'E-001',delivery:1,size:'S',color:'黑色',chipId:null,chipUid:'04:10:20:30:40:50:60',activatedAt:'2026-03-12T02:00:00Z',exitedAt:'2026-05-20T03:00:00Z',reason:'定期换新，旧芯片退出当前授权'},{id:'E-002',delivery:2,size:'M',color:'黑色',chipId:items[0].bound_chip_id,chipUid:items[0].bound_chip_uid,activatedAt:'2026-05-20T03:00:00Z'}];
  identities[2].entities=[{...identities[2].entities[0],size:'S',color:'黑色'}];
  return {items,chips,auditLogs:structuredClone(INITIAL_AUDIT_LOGS),identities,works:[]};
}
const STORAGE='bumbum-make-prototype-v1';
function load():Data {try{const saved=sessionStorage.getItem(STORAGE);if(saved){const data=JSON.parse(saved);if(data.version===1&&Array.isArray(data.items)&&Array.isArray(data.works))return data;}}catch{}return initial();}
export function PrototypeProvider({children}:{children:React.ReactNode}){
  const [data,setData]=useState<Data>(load);
  const [editItemId,setEditItemId]=useState<number|null>(null),[issuanceItemId,setIssuanceItemId]=useState<number|null>(null);
  const [activeWorkId,setActiveWorkId]=useState<string|null>(null),[activeDraft,setActiveDraft]=useState<{itemId:number;kind:WorkKind}|null>(null);
  const [failureMode,setFailureMode]=useState<Store['failureMode']>('none');
  const guardRef=useRef<Store['guard']|null>(null);
  useEffect(()=>{try{sessionStorage.setItem(STORAGE,JSON.stringify({...data,version:1}));}catch{message.warning('浏览器存储空间不足，本次样例暂只保留在当前页面。');}},[data]);
  const setter=<K extends 'items'|'chips'|'auditLogs'>(key:K):Setter<Data[K]> => value => setData(prev=>({...prev,[key]:typeof value==='function'?(value as (v:Data[K])=>Data[K])(prev[key]):value}));
  const audit=(category:AuditLogEntry['category'],action:string,target:string,detail:string)=>setData(prev=>({...prev,auditLogs:[{id:crypto.randomUUID(),timestamp:now(),operator:'演示管理员',category,action,target,detail},...prev.auditLogs]}));
  const identity=(item:ItemView)=>data.identities[item.id]||fallback(item);
  const openWork=(itemId:number,kind:WorkKind)=>{const existing=data.works.find(w=>w.itemId===itemId&&!['completed','cancelled'].includes(w.status));if(existing){setActiveWorkId(existing.id);setActiveDraft(null);}else{setActiveDraft({itemId,kind});setActiveWorkId(null);}};
  const updateWork=(id:string,patch:Partial<Work>,text:string)=>setData(prev=>({...prev,works:prev.works.map(w=>w.id===id?{...w,...patch,history:[...w.history,{time:now(),text}]}:w)}));
  const createWork=(input:Omit<Work,'id'|'step'|'status'|'createdAt'|'history'>)=>{
    const work:Work={...input,id:`${input.kind==='resale'?'TR':'RN'}-${Date.now().toString().slice(-8)}`,step:1,status:'processing',createdAt:now(),history:[{time:now(),text:'已保存申请，等待新实体准备'}]};
    setData(prev=>({...prev,works:[work,...prev.works]}));setActiveWorkId(work.id);setActiveDraft(null);return work;
  };
  const completeWork=(id:string,evidence?:string)=>{
    const work=data.works.find(w=>w.id===id),item=work&&data.items.find(i=>i.id===work.itemId),candidate=work&&data.chips.find(c=>c.id===work.candidateChipId);
    if(!work||!item||!candidate||work.status!=='received'||!(evidence||work.deliveryEvidence)?.trim()||!work.preparationRef?.trim())return {ok:false,error:'请先完成新实体准备、实际收货及交付核验记录。'};
    if(candidate.item_id!==null||candidate.chip_status!=='pending'||(candidate.project&&candidate.project!==item.project))return {ok:false,error:'候选芯片已不可用，请重新核对准备记录。'};
    const old=identity(item);if(old.ownerId!==work.ownerId)return{ok:false,error:'当前持有人已变化，请重新核对。'};
    const stamp=now(),oldId=item.bound_chip_id,newOwner=work.kind==='resale'?work.recipientId:old.ownerId;
    setData(prev=>{
      const meta=prev.identities[item.id]||fallback(item);
      const nextIdentity:Identity={...meta,ownerId:newOwner,quotaReview:work.kind==='resale'?meta.quotaReview:true,
        entities:[...meta.entities.map(e=>!e.exitedAt?{...e,exitedAt:stamp,reason:work.kind==='resale'?'转售交付新实体':'换新交付新实体'}:e),{id:`E-${Date.now().toString().slice(-6)}`,delivery:meta.entities.length+1,size:work.size,color:work.color,chipId:candidate.id,chipUid:candidate.chip_uid,activatedAt:stamp}],
        ownership:work.kind==='resale'?[...meta.ownership.map(o=>!o.to?{...o,to:stamp}:o),{ownerId:newOwner!,from:stamp,workId:id}]:meta.ownership};
      return {...prev,identities:{...prev.identities,[item.id]:nextIdentity},chips:prev.chips.map(c=>c.id===oldId?{...c,chip_status:'retired',updated_at:stamp,replaced_by_chip_uid:candidate.chip_uid}:c.id===candidate.id?{...c,item_id:item.id,item_uid:item.item_uid,project:item.project,chip_status:'bound',keys_generated:true,provisioned_at:stamp,updated_at:stamp,replaces_chip_uid:item.bound_chip_uid||undefined}:c),
        items:prev.items.map(i=>i.id===item.id?{...i,owner_account_id:newOwner,owner_status:'claimed',bound_chip_id:candidate.id,bound_chip_uid:candidate.chip_uid,bound_chip_status:'bound',bound_chip_keys_generated:true,bound_chip_provisioned_at:stamp,carrier_generation:nextIdentity.entities.length,updated_at:stamp}:i),
        works:prev.works.map(w=>w.id===id?{...w,deliveryEvidence:evidence||w.deliveryEvidence,status:'completed',step:4,history:[...w.history,{time:stamp,text:'交付核验后正式接续；旧芯片退役，身份与限定编号保留'}]}:w),
        auditLogs:[{id:crypto.randomUUID(),timestamp:stamp,operator:'演示管理员',category:'replacement',action:'正式接续',target:item.item_uid,detail:`${id}：${work.kind==='resale'?'转售归属变更':'同持有人换新'}；原型样例结果，非真实写卡`},...prev.auditLogs]};
    });return {ok:true};
  };
  const reportLost=(chipId:number,evidence:string)=>setData(prev=>{const chip=prev.chips.find(c=>c.id===chipId);return{...prev,chips:prev.chips.map(c=>c.id===chipId?{...c,chip_status:'lost',updated_at:now()}:c),items:prev.items.map(i=>i.bound_chip_id===chipId?{...i,bound_chip_status:'lost',updated_at:now()}:i),auditLogs:[{id:crypto.randomUUID(),timestamp:now(),operator:'演示管理员',category:'replacement',action:'挂失芯片',target:chip?.chip_uid||String(chipId),detail:evidence+'（原型样例，未操作真实芯片或凭证）'},...prev.auditLogs]};});
  const reset=()=>Modal.confirm({title:'重置原型样例？',content:'仅清除当前浏览器中的原型样例记录与已保存的办理进度，不影响真实项目。',okText:'重置样例',cancelText:'取消',onOk:()=>{setData(initial());setActiveWorkId(null);setActiveDraft(null);setEditItemId(null);setFailureMode('none');}});
  return <Context.Provider value={{...data,setItems:setter('items'),setChips:setter('chips'),setAuditLogs:setter('auditLogs'),editItemId,setEditItemId,issuanceItemId,setIssuanceItemId,activeWorkId,activeDraft,openWork,resumeWork:(id)=>{setActiveDraft(null);setActiveWorkId(id);},closeWork:()=>{setActiveDraft(null);setActiveWorkId(null);},identity,createWork,updateWork,completeWork,reportLost,audit,failureMode,setFailureMode,guard:fn=>guardRef.current?guardRef.current(fn):fn(),setGuard:fn=>{guardRef.current=fn;},reset}}>{children}</Context.Provider>;
}
export function usePrototype(){const value=useContext(Context);if(!value)throw new Error('原型上下文未初始化');return value;}
