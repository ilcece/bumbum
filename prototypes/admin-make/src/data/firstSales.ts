import type {Data, SharedStyle} from './prototypeStore';

// 仅保存浏览器中的合成首交事实；不包含支付、库存扣减或所有权授权。
export interface SalesChannel {id:string; shop:string; productRef:string; listed:boolean; closed:boolean; checkedAt?:string; expectedCount?:number; evidence?:string;}
export interface SalesPlan {
  id:string; name:string; styleId:string; quantity:number; channel:string; productRef:string;
  issuanceId?:string; mode?:'fixed'|'timed'|'unlimited'; status?:'draft'|'ready'|'selling'|'reconciling'|'sealed';
  startAt?:string; endAt?:string; basis?:string; deliveryPromise?:string; supplierRef?:string; sampleRef?:string; channels?:SalesChannel[]; sealedAt?:string; sealEvidence?:string; finalCount?:number;
}
export interface FirstDelivery {
  id:string; planId:string; orderRef:string; lineRef:string; piece:number; requestedSpec:string; recipientRef:string;
  channelId?:string; saleState?:'valid'|'review'|'excluded'; salesEvidence?:string; paidAt?:string; editionNumber?:number;
  chipId?:number; chipUid?:string; configuredAt?:string; qualityAttempts?:{time:string;actualSpec:string;quality:'pass'|'fail';evidence:string}[];
  stage:number; productionEvidence?:string; factoryRef?:string; factoryReceipt?:string;
  quality?:'pass'|'fail'; qualityEvidence?:string; actualSpec?:string;
  itemId?:number; checkEvidence?:string; tracking?:string; receiptEvidence?:string;
  exception?:string; history:{time:string;text:string}[];
}
export const firstStages=['订单核对','生产跟进','到货验收','配卡与出厂检查','发货记录','实际交付','实物交付完成'];
export function seedFirstSales(data:Data):Data {
  const examples=[
    {id:'SALE-BRACELET',name:'紫檀手串',quantity:50,project:'jewelry',spec:'腕围／珠径以样品为准',material:'紫檀；具体材种待样品确认'},
    {id:'SALE-TEE',name:'T恤',quantity:100,project:'fashion',spec:'尺码／颜色以订单为准',material:'材料以样品为准'},
    {id:'SALE-CAP',name:'棒球帽',quantity:20,project:'fashion',spec:'帽围／调节范围以订单为准',material:'材料以样品为准'},
  ] as const;
  const styles:SharedStyle[]=examples.filter(e=>!data.styles.some(s=>s.id===e.id)).map(e=>({id:e.id,code:e.id,project:e.project,sizes:[],profile:{name:e.name,description:e.spec,material:e.material,image_urls:[],...(e.project==='fashion'?{care_instructions:null}:{meaning:null})}}));
  return {...data,styles:[...data.styles,...styles],salesPlans:[...data.salesPlans,...examples.filter(e=>!data.salesPlans.some(s=>s.id===e.id)).map(e=>({id:e.id,name:e.name+' · 首次销售',styleId:e.id,quantity:e.quantity,channel:'演示网店',productRef:e.id}))]};
}
