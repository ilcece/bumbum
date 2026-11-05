import type {SalesPlan, FirstDelivery} from './firstSales';
import type {Issuance} from './prototypeStore';
export const saleStates={draft:'准备中',ready:'待上架',selling:'销售中',reconciling:'对账中',sealed:'已封版'};
export const saleModes={fixed:'固定总量',timed:'限时按销量定量',unlimited:'非限定'};
export const saleStatus=(s:SalesPlan)=>s.status||'draft';
export const issueLabel=(i:Issuance)=>i.mode==='timed'&&!i.sealedAt?'限时定量／总量待核定':i.total===null?'非限定／总量不限':`限定${i.total}份`;
export const isValidSale=(r:FirstDelivery)=>!r.saleState||r.saleState==='valid';
export const saleRows=(s:SalesPlan,rows:FirstDelivery[])=>rows.filter(r=>r.planId===s.id);
export const validRows=(s:SalesPlan,rows:FirstDelivery[])=>saleRows(s,rows).filter(isValidSale);
export const orderedRows=(s:SalesPlan,rows:FirstDelivery[])=>validRows(s,rows).sort((a,b)=>(a.paidAt||'').localeCompare(b.paidAt||'')||(s.channels||[]).findIndex(c=>c.id===a.channelId)-(s.channels||[]).findIndex(c=>c.id===b.channelId)||a.orderRef.localeCompare(b.orderRef,'zh-CN',{numeric:true})||a.lineRef.localeCompare(b.lineRef)||a.piece-b.piece||a.id.localeCompare(b.id));
export const beijingInput=(v:string)=>v?new Date(v+'+08:00').toISOString():'';
export function sealError(s:SalesPlan,rows:FirstDelivery[],issue?:Issuance){
 const own=saleRows(s,rows),valid=validRows(s,rows);
 if(s.status!=='reconciling')return '请先核对各店已停售并进入对账。';
 if(!s.channels?.length||s.channels.some(c=>!c.closed||!c.checkedAt||!c.evidence||c.expectedCount!==valid.filter(r=>r.channelId===c.id).length))return '各店必须停售并核对销售件数、来源依据；订单有变化需重新核对。';
 if(own.some(r=>r.saleState==='review'||r.exception))return '仍有待核订单或交付异常，请先处理。';
 if(!valid.length)return '本次没有有效销售件数；请核对销售结果，不生成虚假的发行总量。';
 if(issue?.mode==='fixed'&&issue.total!==null&&valid.length>issue.total)return '有效销售件数超过固定发行上限，请核对。';
 return '';
}
