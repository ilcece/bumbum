import type {SalesPlan,FirstDelivery} from './firstSales';
import {seedFirstSales} from './firstSales';
import {withScenarioExamples} from './prototypeFixtures';
import React, { createContext, useContext, useEffect, useRef, useState } from 'react';
import type { Dispatch, SetStateAction } from 'react';
import { Modal, message } from 'antd';
import { INITIAL_ITEMS, INITIAL_CHIPS, INITIAL_AUDIT_LOGS } from './mockBackend';
import type { ItemView, ChipView, AuditLogEntry, FashionProfile, JewelryProfile, ProjectCode } from './mockBackend';

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
export interface Identity { issuanceId:string|null; editionNumber:number|null; series: string | null; edition: string | null; total: number | null; firstOwnerAt: string | null; ownerId: string | null; used: number; quotaReview?: boolean; entities: EntityRecord[]; ownership: { ownerId: string; from: string; to?: string; workId?: string }[]; }
export type WorkKind = 'periodic' | 'loss' | 'resale';
export interface RightRule {id:string;name:string;version:string;kind:'renewal'|'resale';quotaGroup:string|null;summary:string;qualification:string;transfer:string;fees:string;}
export interface Work {
  demoReadOnly?:boolean; demoNote?:string; id: string; itemId: number; kind: WorkKind; step: number; status: 'processing' | 'shipped' | 'received' | 'completed' | 'cancelled';
  ownerId: string; recipientId: string; size: string; color: string; evidence: string; note: string;
  candidateChipId?: number; preparationRef?: string; dispatchNote?: string; tracking?: string; shippedAt?: string; receivedAt?: string; deliveryEvidence?: string;
  createdAt: string; history: { time: string; text: string }[];
}
export interface SharedStyle {id:string;code:string;project:ProjectCode;profile:FashionProfile|JewelryProfile;sizes:string[];}
export interface Issuance {id:string;name:string;styleId:string;series?:string;version?:string;rightIds:string[];total:number|null;description:string;color?:string;status:'draft'|'issued';confirmedAt?:string;everReferenced?:boolean;}
type ItemRecord=Omit<ItemView,'sku_code'|'profile'|'style_id'|'project'>&{styleId:string};
type IdentityRecord=Omit<Identity,'series'|'edition'|'total'>;
type ChipRecord=Omit<ChipView,'project'|'item_uid'>;
function chipRecords(chips:ChipView[]):ChipRecord[]{return chips.map(({project:_project,item_uid:_uid,...chip})=>chip);}
function itemViews(items:ItemRecord[],styles:SharedStyle[]):ItemView[]{return items.flatMap(({styleId,...item})=>{const style=styles.find(s=>s.id===styleId);return style?[{...item,project:style.project,style_id:styleId,sku_code:style.code,profile:style.profile}]:[];});}
function chipViews(chips:ChipRecord[],items:ItemView[]):ChipView[]{return chips.map(chip=>{const item=items.find(i=>i.id===chip.item_id);return {...chip,project:item?.project||null,item_uid:item?.item_uid||null};});}
function rawIdentity({series:_series,edition:_edition,total:_total,...meta}:Identity):IdentityRecord{return meta;}
export interface Data {salesPlans:SalesPlan[];firstDeliveries:FirstDelivery[];rightsRules:RightRule[];items:ItemRecord[];chips:ChipRecord[];auditLogs:AuditLogEntry[];identities:Record<number,IdentityRecord>;works:Work[];styles:SharedStyle[];issuances:Issuance[];}
type Setter<T> = Dispatch<SetStateAction<T>>;
interface Store extends Omit<Data,'chips'|'items'|'identities'> {
  items:ItemView[];identities:Record<number,Identity>;
  setSalesPlans:Setter<SalesPlan[]>;setFirstDeliveries:Setter<FirstDelivery[]>;seedFirstSales:()=>void;
  styleEditorId:string|null;setStyleEditorId:Setter<string|null>;catalogOpen:boolean;setCatalogOpen:Setter<boolean>;issuanceEditorId:string|null;setIssuanceEditorId:Setter<string|null>;identityEditorId:number|null;setIdentityEditorId:Setter<number|null>;
  deleteIssuance:(id:string)=>{ok:boolean;error?:string};toggleItem:(id:number)=>{ok:boolean;error?:string};confirmIssuance:(id:string)=>{ok:boolean;error?:string};createIdentityItem:(item:ItemView,issuanceId:string,editionNumber:number|null)=>{ok:boolean;error?:string};
  saveStyle:(style:SharedStyle,attachItemId?:number)=>{ok:boolean;error?:string};saveIssuance:(issue:Issuance)=>{ok:boolean;error?:string};assignIdentity:(itemId:number,styleId:string|null,issuanceId:string|null,editionNumber:number|null,evidence?:string)=>{ok:boolean;error?:string};
  chips:ChipView[];
  setItems: Setter<ItemView[]>; setChips: Setter<ChipView[]>; setAuditLogs: Setter<AuditLogEntry[]>;
  editItemId: number | null; setEditItemId: Setter<number | null>; issuanceItemId: number | null; setIssuanceItemId: Setter<number | null>;
  activeWorkId: string | null; activeDraft: {itemId:number;kind:WorkKind} | null; openWork: (itemId:number,kind:WorkKind) => void; resumeWork: (id:string)=>void; closeWork:()=>void;
  identity: (item:ItemView)=>Identity; createWork:(data:Omit<Work,'id'|'step'|'status'|'createdAt'|'history'>)=>Work;
  updateWork:(id:string,patch:Partial<Work>,text:string)=>void; completeWork:(id:string,evidence?:string)=>{ok:boolean;error?:string};
  reportLost:(chipId:number,evidence:string)=>{ok:boolean;error?:string}; audit:(category:AuditLogEntry['category'],action:string,target:string,detail:string)=>void;
  failureMode:'none'|'save'|'unknown'|'upload'; setFailureMode:Setter<'none'|'save'|'unknown'|'upload'>;
  guard:(fn:()=>void)=>void; setGuard:(fn:((next:()=>void)=>void)|null)=>void; reset:()=>void;
}
const Context = createContext<Store | null>(null);
const fallback = (item:ItemView):Identity => ({issuanceId:null,editionNumber:null,series:null,edition:null,total:null,firstOwnerAt:null,ownerId:null,used:0,entities:item.bound_chip_id&&item.bound_chip_provisioned_at?[{id:`E-${item.id}-1`,delivery:1,size:'未记录',color:'未记录',chipId:item.bound_chip_id,chipUid:item.bound_chip_uid,activatedAt:item.bound_chip_provisioned_at}]:[],ownership:[]});
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
    identities[item.id]={...fallback(item),ownerId,firstOwnerAt:claimed?'2026-03-12T02:00:00Z':null,issuanceId:item.id<=2?'ISSUE-TEE-2026':null,editionNumber:item.id<=2?item.id:null,series:item.id<=2?'BUMBUM · 限定系列':null,edition:item.id<=2?`#${String(item.id).padStart(3,'0')}/100`:null,total:item.id<=2?100:null,used:item.id===1?1:0,ownership:ownerId?[{ownerId,from:'2026-03-12T02:00:00Z'}]:[]};
    if(item.id<=2){const chip=chips.find(c=>c.id===item.bound_chip_id);if(chip){chip.created_at='2026-03-10T01:00:00Z';chip.provisioned_at='2026-03-12T01:00:00Z';item.bound_chip_provisioned_at=chip.provisioned_at;}}
  }
  identities[1].entities=[{id:'E-001',delivery:1,size:'S',color:'黑色',chipId:null,chipUid:'04:10:20:30:40:50:60',activatedAt:'2026-03-12T02:00:00Z',exitedAt:'2026-05-20T03:00:00Z',reason:'定期换新，旧芯片退出当前授权'},{id:'E-002',delivery:2,size:'M',color:'黑色',chipId:items[0].bound_chip_id,chipUid:items[0].bound_chip_uid,activatedAt:'2026-05-20T03:00:00Z'}];
  identities[2].entities=[{...identities[2].entities[0],size:'S',color:'黑色'}];
  const styles:SharedStyle[]=[];
  const itemRecords:ItemRecord[]=items.map(({sku_code,profile,project,style_id:_style,...item})=>{let style=styles.find(s=>s.code===sku_code&&s.project===project);if(!style){style={id:'STYLE-'+item.id,code:sku_code||'DEMO-STYLE-'+item.id,project,profile:profile||{name:'未完善款式',description:null,material:null,image_urls:[],...(project==='fashion'?{care_instructions:null}:{meaning:null})},sizes:project==='fashion'?['S','M','L','XL']:[]};styles.push(style);}return {...item,styleId:style.id};});
  const teeStyle=itemRecords[0].styleId!;
  return withScenarioExamples({salesPlans:[],firstDeliveries:[],rightsRules:[{id:'RIGHT-RENEW',name:'付费定期／挂失换新',version:'发行约定样例1',kind:'renewal',quotaGroup:'RENEW-YEAR',summary:'定期与挂失换新共享自然年一次',qualification:'首次绑定所有人后具备资格',transfer:'转售继承物品当年余额，次年恢复一次',fees:'费用、占用/扣减节点及跨年时区待确认'},{id:'RIGHT-RESALE',name:'后台转售数字内容与约定权益',version:'发行约定样例1',kind:'resale',quotaGroup:null,summary:'交付新实体，旧实体无需回收',qualification:'后台核对原持有人和接收人',transfer:'转售履约不扣换新次数、不重置余额',fees:'费用与冻结范围、取消及争议政策待确认'}],items:itemRecords,chips:chipRecords(chips),auditLogs:structuredClone(INITIAL_AUDIT_LOGS),identities:Object.fromEntries(Object.entries(identities).map(([id,meta])=>[id,rawIdentity(meta)])),works:[],styles,issuances:[{id:'ISSUE-TEE-2026',name:'BUMBUM · 限定系列',styleId:teeStyle,series:'限定T恤',version:'首次发行约定样例',rightIds:['RIGHT-RENEW','RIGHT-RESALE'],total:100,color:'黑色',description:'限定100份；允许换新选码，颜色遵守发行约定，旧实体无需回收。',status:'issued'}]});
}
const STORAGE='bumbum-make-prototype-v5';
// 升级兼容旧样例：保留原承诺中的颜色文字、使用事实和原始确认标记，不清空会话。
function normalize(data:Data):Data{return {...data,salesPlans:data.salesPlans||[],firstDeliveries:data.firstDeliveries||[],issuances:data.issuances.map(issue=>({...issue,description:issue.description+(issue.color&&!issue.description.includes('原颜色约定：')?'\n原颜色约定：'+issue.color:''),color:undefined,everReferenced:issue.everReferenced||Object.values(data.identities).some(m=>m.issuanceId===issue.id)}))};}
function load():Data {try{const saved=sessionStorage.getItem(STORAGE);if(saved){const data=JSON.parse(saved);if(data.version===5&&Array.isArray(data.items)&&Array.isArray(data.works)&&Array.isArray(data.styles)&&Array.isArray(data.issuances))return normalize({...data,chips:chipRecords(data.chips)});}}catch{}return normalize(initial());}
export function PrototypeProvider({children}:{children:React.ReactNode}){
  const [data,setData]=useState<Data>(load);
  const [editItemId,setEditItemId]=useState<number|null>(null),[issuanceItemId,setIssuanceItemId]=useState<number|null>(null);
  const [activeWorkId,setActiveWorkId]=useState<string|null>(null),[activeDraft,setActiveDraft]=useState<{itemId:number;kind:WorkKind}|null>(null);
  const [failureMode,setFailureMode]=useState<Store['failureMode']>('none');
  const guardRef=useRef<Store['guard']|null>(null);
  useEffect(()=>{try{sessionStorage.setItem(STORAGE,JSON.stringify({...data,version:5}));}catch{message.warning('浏览器存储空间不足，本次样例暂只保留在当前页面。');}},[data]);
  const items=itemViews(data.items,data.styles);
  const chips=chipViews(data.chips,items);
  const identities=Object.fromEntries(Object.entries(data.identities).map(([id,meta])=>{const issue=data.issuances.find(i=>i.id===meta.issuanceId);return [id,{...meta,series:issue?.name||null,total:issue?.total||null,edition:issue&&meta.editionNumber?`#${String(meta.editionNumber).padStart(3,'0')}${issue.total===null?'':'/'+issue.total}`:null}];}));
  const [styleEditorId,setStyleEditorId]=useState<string|null>(null),[catalogOpen,setCatalogOpen]=useState(false),[issuanceEditorId,setIssuanceEditorId]=useState<string|null>(null),[identityEditorId,setIdentityEditorId]=useState<number|null>(null);
  const setItems:Setter<ItemView[]>=value=>setData(prev=>{const incoming=typeof value==='function'?value(itemViews(prev.items,prev.styles)):value;const styles=[...prev.styles];const records:ItemRecord[]=incoming.map(({profile,sku_code,style_id,project,...item})=>{const style=styles.find(s=>s.id===style_id)||styles.find(s=>s.code===sku_code&&s.project===project);if(style&&profile&&JSON.stringify(profile)!==JSON.stringify(style.profile)){styles[styles.indexOf(style)]={...style,profile};}if(!style)throw new Error('原型物品必须引用已有款式');return {...item,styleId:style.id};});return {...prev,items:records,styles};});
  const setChips:Setter<ChipView[]>=value=>setData(prev=>({...prev,chips:chipRecords(typeof value==='function'?value(chipViews(prev.chips,itemViews(prev.items,prev.styles))):value)}));
  const setter=<K extends 'auditLogs'|'salesPlans'|'firstDeliveries'>(key:K):Setter<Data[K]> => value => setData(prev=>({...prev,[key]:typeof value==='function'?(value as (v:Data[K])=>Data[K])(prev[key]):value}));
  const audit=(category:AuditLogEntry['category'],action:string,target:string,detail:string)=>setData(prev=>({...prev,auditLogs:[{id:crypto.randomUUID(),timestamp:now(),operator:'演示管理员',category,action,target,detail},...prev.auditLogs]}));
  const identity=(item:ItemView):Identity=>identities[item.id]||fallback(item);
  const openWork=(itemId:number,kind:WorkKind)=>{const existing=data.works.find(w=>w.itemId===itemId&&!['completed','cancelled'].includes(w.status));if(existing){setActiveWorkId(existing.id);setActiveDraft(null);}else{setActiveDraft({itemId,kind});setActiveWorkId(null);}};
  const updateWork=(id:string,patch:Partial<Work>,text:string)=>setData(prev=>({...prev,works:prev.works.map(w=>w.id===id?{...w,...patch,history:[...w.history,{time:now(),text}]}:w)}));
  const createWork=(input:Omit<Work,'id'|'step'|'status'|'createdAt'|'history'>)=>{
    const work:Work={...input,id:`${input.kind==='resale'?'TR':'RN'}-${Date.now().toString().slice(-8)}`,step:1,status:'processing',createdAt:now(),history:[{time:now(),text:'已保存申请，等待新实体准备'}]};
    setData(prev=>({...prev,works:[work,...prev.works]}));setActiveWorkId(work.id);setActiveDraft(null);return work;
  };
  const completeWork=(id:string,evidence?:string)=>{
    const work=data.works.find(w=>w.id===id),item=work&&items.find(i=>i.id===work.itemId),candidate=work&&chips.find(c=>c.id===work.candidateChipId);
    if(work?.demoReadOnly)return{ok:false,error:'此为只读历史或异常演示，处置规则待定。'};
    if(!work||!item||!candidate||work.status!=='received'||!(evidence||work.deliveryEvidence)?.trim()||!work.preparationRef?.trim())return {ok:false,error:'请先完成新实体准备、实际收货及交付核验记录。'};
    if(candidate.item_id!==null||candidate.chip_status!=='pending'||(candidate.project&&candidate.project!==item.project))return {ok:false,error:'候选芯片已不可用，请重新核对准备记录。'};
    const old=identity(item);if(old.ownerId!==work.ownerId)return{ok:false,error:'当前持有人已变化，请重新核对。'};
    const stamp=now(),oldId=item.bound_chip_id,newOwner=work.kind==='resale'?work.recipientId:old.ownerId;
    setData(prev=>{
      const meta=prev.identities[item.id]||rawIdentity(fallback(item));
      const nextIdentity:IdentityRecord={...meta,ownerId:newOwner,quotaReview:work.kind==='resale'?meta.quotaReview:true,
        entities:[...meta.entities.map(e=>!e.exitedAt?{...e,exitedAt:stamp,reason:work.kind==='resale'?'转售交付新实体':'换新交付新实体'}:e),{id:`E-${Date.now().toString().slice(-6)}`,delivery:meta.entities.length+1,size:work.size,color:work.color,chipId:candidate.id,chipUid:candidate.chip_uid,activatedAt:stamp}],
        ownership:work.kind==='resale'?[...meta.ownership.map(o=>!o.to?{...o,to:stamp}:o),{ownerId:newOwner!,from:stamp,workId:id}]:meta.ownership};
      return {...prev,identities:{...prev.identities,[item.id]:nextIdentity},chips:prev.chips.map(c=>c.id===oldId?{...c,chip_status:'retired',updated_at:stamp,replaced_by_chip_uid:candidate.chip_uid}:c.id===candidate.id?{...c,item_id:item.id,chip_status:'bound',keys_generated:true,provisioned_at:stamp,updated_at:stamp,replaces_chip_uid:item.bound_chip_uid||undefined}:c),
        items:prev.items.map(i=>i.id===item.id?{...i,owner_account_id:newOwner,owner_status:'claimed',bound_chip_id:candidate.id,bound_chip_uid:candidate.chip_uid,bound_chip_status:'bound',bound_chip_keys_generated:true,bound_chip_provisioned_at:stamp,carrier_generation:nextIdentity.entities.length,updated_at:stamp}:i),
        works:prev.works.map(w=>w.id===id?{...w,deliveryEvidence:evidence||w.deliveryEvidence,status:'completed',step:4,history:[...w.history,{time:stamp,text:'交付核验后正式接续；旧芯片退役，身份与限定编号保留'}]}:w),
        auditLogs:[{id:crypto.randomUUID(),timestamp:stamp,operator:'演示管理员',category:'replacement',action:'正式接续',target:item.item_uid,detail:`${id}：${work.kind==='resale'?'转售归属变更':'同持有人换新'}；原型样例结果，非真实写卡`},...prev.auditLogs]};
    });return {ok:true};
  };
  const toggleItem=(id:number)=>{
    const item=items.find(i=>i.id===id);if(!item||item.status==='archived')return{ok:false,error:'归档物品不可普通启停。'};
    if(failureMode!=='none')return{ok:false,error:failureMode==='unknown'?'启停结果待核对：本次演示未写入。':'模拟启停失败，原状态保留。'};
    if(item.status!=='active'&&(!item.profile?.name.trim()||!identity(item).issuanceId||!item.bound_chip_provisioned_at||item.bound_chip_status!=='bound'))return{ok:false,error:'启用前请补齐发行关联、名称及关联芯片配置核验，并确认芯片可用。'};
    setItems(prev=>prev.map(i=>i.id===id?{...i,status:i.status==='active'?'disabled':'active',updated_at:now()}:i));audit('item','物品启停',item.item_uid,'独立变更启用状态，未改芯片或所有权');return{ok:true};
  };
  const reportLost=(chipId:number,evidence:string)=>{
    const chip=chips.find(c=>c.id===chipId);if(!chip||!['bound','disabled'].includes(chip.chip_status)||!evidence.trim())return{ok:false,error:'请核对当前芯片和申请依据。'};
    if(failureMode!=='none')return{ok:false,error:failureMode==='unknown'?'挂失结果待核对：本次演示未写入，输入保留。':'模拟挂失失败，输入保留。'};
    setData(prev=>({...prev,chips:prev.chips.map(c=>c.id===chipId?{...c,chip_status:'lost',updated_at:now()}:c),items:prev.items.map(i=>i.bound_chip_id===chipId?{...i,bound_chip_status:'lost',updated_at:now()}:i)}));audit('replacement','挂失芯片',chip.chip_uid,evidence+'（仅合成样例）');return{ok:true};
  };
  const saveStyle=(style:SharedStyle,attachItemId?:number)=>{
    if(!style.code.trim()||!style.profile.name.trim())return{ok:false,error:'请填写款式编号与名称。'};
    if(data.styles.some(s=>s.id!==style.id&&s.project===style.project&&s.code===style.code))return{ok:false,error:'同类别款式编号已存在，请选择已有款式。'};
    const used=data.items.filter(i=>i.styleId===style.id);
    const existing=data.styles.find(s=>s.id===style.id);if(existing&&existing.project!==style.project&&(used.length>0||data.issuances.some(i=>i.styleId===style.id)))return{ok:false,error:'已被物品或发行引用的款式，类别不能通过普通资料维护修改。'};
    setData(prev=>({...prev,styles:prev.styles.some(s=>s.id===style.id)?prev.styles.map(s=>s.id===style.id?style:s):[...prev.styles,style],items:attachItemId?prev.items.map(i=>i.id===attachItemId?{...i,styleId:style.id,updated_at:now()}:i):prev.items}));return{ok:true};
  };
  const saveIssuance=(issue:Issuance)=>{
    if(data.issuances.some(i=>i.id===issue.id&&i.status==='issued'))return{ok:false,error:'已确认发行约定只读。'};
    if(!data.styles.some(s=>s.id===issue.styleId)||!issue.name.trim()||!issue.description.trim()||(issue.total!==null&&(!Number.isSafeInteger(issue.total)||issue.total<1)))return{ok:false,error:'请完善款式、名称和说明；限定总量须为正整数，非限定不设上限。'};
    setData(prev=>({...prev,issuances:prev.issuances.some(i=>i.id===issue.id)?prev.issuances.map(i=>i.id===issue.id?{...issue,status:'draft' as const}:i):[...prev.issuances,{...issue,status:'draft' as const}]}));return{ok:true};
  };
  const confirmIssuance=(id:string)=>{
    const issue=data.issuances.find(i=>i.id===id);if(!issue||issue.status!=='draft')return{ok:false,error:'请选择已保存的发行草案。'};
    if(failureMode!=='none')return{ok:false,error:'当前模拟异常未恢复，未确认发行约定。'};
    setData(prev=>({...prev,issuances:prev.issuances.map(i=>i.id===id?{...i,status:'issued' as const,version:'CONF-'+crypto.randomUUID(),confirmedAt:now()}:i)}));
    audit('item','确认发行约定',issue.name,'冻结当次承诺；不创建物品、不启用或认领。');return{ok:true};
  };
  const deleteIssuance=(id:string)=>{
    const issue=data.issuances.find(i=>i.id===id);if(!issue)return{ok:false,error:'发行约定不存在。'};
    if(issue.everReferenced||Object.values(data.identities).some(m=>m.issuanceId===id))return{ok:false,error:'该约定曾被物品引用，不允许硬删除，请查看引用物品。'};
    if(failureMode!=='none')return{ok:false,error:'删除未确认成功：本次演示未写入，请先核对。'};
    setData(prev=>({...prev,issuances:prev.issuances.filter(i=>i.id!==id)}));audit('item','删除未引用发行约定',issue.name,'保留删除事实与原约定：'+JSON.stringify(issue));return{ok:true};
  };
  const checkNumber=(issuanceId:string|null,editionNumber:number|null,itemId?:number)=>{
    const issue=data.issuances.find(i=>i.id===issuanceId);
    if(!issue||issue.status!=='issued')return '请选择已确认的发行约定。';
    if(editionNumber===null||!Number.isSafeInteger(editionNumber)||editionNumber<1)return '本件序号须为正整数。';
    if(issue.total!==null&&editionNumber>issue.total)return '本件序号超出限定发行总量。';
    if(Object.entries(data.identities).some(([id,m])=>Number(id)!==itemId&&m.issuanceId===issuanceId&&m.editionNumber===editionNumber))return '该发行内的本件序号已占用。';
    return null;
  };
  const createIdentityItem=(item:ItemView,issuanceId:string,editionNumber:number|null)=>{
    const error=checkNumber(issuanceId,editionNumber);if(error)return{ok:false,error};
    const issue=data.issuances.find(i=>i.id===issuanceId)!,style=data.styles.find(s=>s.id===issue.styleId);
    if(!style||item.style_id!==style.id||item.project!==style.project)return{ok:false,error:'款式与类别须从发行约定引用。'};
    if(data.items.some(i=>i.item_uid===item.item_uid))return{ok:false,error:'物品编号已存在，不能重复创建。'};
    if(failureMode!=='none')return{ok:false,error:'当前模拟异常未恢复，本次未创建，输入保留。'};
    const {project:_project,profile:_profile,sku_code:_sku,style_id:_style,...record}=item;
    setData(prev=>({...prev,items:[{...record,styleId:style.id},...prev.items],issuances:prev.issuances.map(i=>i.id===issuanceId?{...i,everReferenced:true}:i),identities:{...prev.identities,[item.id]:{...rawIdentity(fallback(item)),issuanceId,editionNumber}}}));return{ok:true};
  };
  const assignIdentity=(itemId:number,styleId:string|null,issuanceId:string|null,editionNumber:number|null,evidence?:string)=>{
    const item=items.find(i=>i.id===itemId);if(!item)return{ok:false,error:'物品不存在。'};const meta=identity(item);
    if(item.status==='archived')return{ok:false,error:'归档物品保持只读。'};
    if(!meta.issuanceId&&!evidence?.trim())return{ok:false,error:'请记录原发行依据并确认仅补齐原有承诺。'};
    if(meta.issuanceId&&(issuanceId!==meta.issuanceId||editionNumber!==meta.editionNumber))return{ok:false,error:'已登记的发行与本件序号不在普通维护中重分配，请走专用纠错。'};
    const error=checkNumber(issuanceId,editionNumber,itemId);if(error)return{ok:false,error};
    const style=data.styles.find(s=>s.id===styleId),issue=data.issuances.find(i=>i.id===issuanceId)!;
    if(!style||issue.styleId!==style.id||style.id!==item.style_id)return{ok:false,error:'缺失信息仅补关联同款发行，不借此更换款式或类别。'};
    if(failureMode!=='none')return{ok:false,error:'当前模拟异常未恢复，未保存关联，输入保留。'};
    setData(prev=>({...prev,issuances:prev.issuances.map(i=>i.id===issuanceId?{...i,everReferenced:true}:i),identities:{...prev.identities,[itemId]:{...rawIdentity(meta),issuanceId,editionNumber}}}));
    audit('item','补齐物品发行关联',item.item_uid,issue.name+'；核对依据：'+(evidence||'已登记关联只读核对'));return{ok:true};
  };
  const reset=()=>Modal.confirm({title:'重置原型样例？',content:'仅清除当前浏览器中的原型样例记录与已保存的办理进度，不影响真实项目。',okText:'重置样例',cancelText:'取消',onOk:()=>{setData(normalize(initial()));setActiveWorkId(null);setActiveDraft(null);setEditItemId(null);setFailureMode('none');}});
  return <Context.Provider value={{...data,items,chips,identities,setSalesPlans:setter('salesPlans'),setFirstDeliveries:setter('firstDeliveries'),seedFirstSales:()=>setData(seedFirstSales),styleEditorId,setStyleEditorId,catalogOpen,setCatalogOpen,issuanceEditorId,setIssuanceEditorId,identityEditorId,setIdentityEditorId,saveStyle,saveIssuance,deleteIssuance,toggleItem,confirmIssuance,createIdentityItem,assignIdentity,setItems,setChips,setAuditLogs:setter('auditLogs'),editItemId,setEditItemId,issuanceItemId,setIssuanceItemId,activeWorkId,activeDraft,openWork,resumeWork:(id)=>{setActiveDraft(null);setActiveWorkId(id);},closeWork:()=>{setActiveDraft(null);setActiveWorkId(null);},identity,createWork,updateWork,completeWork,reportLost,audit,failureMode,setFailureMode,guard:fn=>guardRef.current?guardRef.current(fn):fn(),setGuard:fn=>{guardRef.current=fn;},reset}}>{children}</Context.Provider>;
}
export function usePrototype(){const value=useContext(Context);if(!value)throw new Error('原型上下文未初始化');return value;}
