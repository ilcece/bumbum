import type {Data, Work} from './prototypeStore';

// 仅生成原型合成场景，不用于正式服务、真实芯片或数据迁移。
export function withScenarioExamples(data: Data): Data {
  const beads=Array.from({length:14},(_,i)=>{const angle=i*Math.PI/7;return `<circle cx="${260+120*Math.cos(angle)}" cy="${225+120*Math.sin(angle)}" r="24" fill="#a37e51" stroke="#785f42" stroke-width="3"/>`;}).join('');
  const bracelet='data:image/svg+xml;charset=utf-8,'+encodeURIComponent(`<svg xmlns="http://www.w3.org/2000/svg" width="520" height="480"><rect width="520" height="480" fill="#f5f2ed"/>${beads}<text x="260" y="425" text-anchor="middle" fill="#785f42" font-size="22">BUMBUM · 手串示意</text></svg>`);
  data.styles=data.styles.map(s=>s.project==='jewelry'?{...s,profile:{...s.profile,image_urls:[bracelet]}}:s);
  const baseItem=data.items[0],baseChip=data.chips[0],baseIdentity=data.identities[1];
  const stamp='2026-11-01T02:00:00Z';
  const stages=['preparing','dispatch','shipped','received','completed','cancelled','attention'] as const;
  const names=['待准备','待发货','运输中','待交付核验','转售已完成','已取消历史','运输异常待核对'];
  for(let index=0;index<stages.length;index++){
    const stage=stages[index],id=101+index,oldChipId=1001+index,candidateId=2001+index;
    const kind:Work['kind']=index===2||index===4?'resale':index===3?'loss':'periodic';
    const completed=stage==='completed',cancelled=stage==='cancelled';
    const oldUid=`04:DE:10:00:00:00:${String(index+1).padStart(2,'0')}`;
    const newUid=`04:DE:20:00:00:00:${String(index+1).padStart(2,'0')}`;
    const workId=`DEMO-${kind==='resale'?'TR':'RN'}-${index+1}`;
    data.chips.push({...baseChip,id:oldChipId,chip_uid:oldUid,item_id:id,chip_status:completed?'retired':kind==='loss'?'lost':'bound',batch_no:'DEMO-SCENARIO',keys_generated:true,provisioned_at:stamp,created_at:stamp,updated_at:stamp,is_validation_object:false});
    if(!cancelled)data.chips.push({...baseChip,id:candidateId,chip_uid:newUid,item_id:completed?id:null,chip_status:completed?'bound':'pending',keys_generated:completed,provisioned_at:completed?stamp:null,key_version:completed?'DEMO-V1':null,batch_no:'DEMO-CANDIDATE',created_at:stamp,updated_at:stamp,is_validation_object:false});
    data.items.push({...baseItem,id,item_uid:`FASH-2026-${String(id).padStart(6,'0')}`,bound_chip_id:completed?candidateId:oldChipId,bound_chip_uid:completed?newUid:oldUid,bound_chip_status:kind==='loss'?'lost':'bound',owner_account_id:completed?'DEMO-OWNER-B':'DEMO-OWNER-A',created_at:stamp,updated_at:stamp});
    const oldEntity={id:`E-DEMO-${id}-1`,delivery:1,size:'M',color:'黑色',chipId:oldChipId,chipUid:oldUid,activatedAt:stamp};
    data.identities[id]={...structuredClone(baseIdentity),firstOwnerAt:stamp,editionNumber:11+index,ownerId:completed?'DEMO-OWNER-B':'DEMO-OWNER-A',used:index===4?1:0,quotaReview:false,entities:completed?[{...oldEntity,exitedAt:stamp,reason:'转售交付新实体，旧实体无需回收'},{id:`E-DEMO-${id}-2`,delivery:2,size:'L',color:'黑色',chipId:candidateId,chipUid:newUid,activatedAt:stamp}]:[oldEntity],ownership:completed?[{ownerId:'DEMO-OWNER-A',from:stamp,to:stamp},{ownerId:'DEMO-OWNER-B',from:stamp,workId}]:[{ownerId:'DEMO-OWNER-A',from:stamp}]};
    data.works.push({id:workId,itemId:id,kind,step:completed?4:stage==='received'?3:stage==='preparing'||cancelled?1:2,status:completed?'completed':cancelled?'cancelled':stage==='received'?'received':stage==='shipped'?'shipped':'processing',ownerId:'DEMO-OWNER-A',recipientId:kind==='resale'?'DEMO-OWNER-B':'DEMO-OWNER-A',size:'L',color:'黑色',evidence:'演示：已记录申请来源和账户核对；具体资格证据待定',note:`合成场景：${names[index]}`,candidateChipId:stage==='preparing'||cancelled?undefined:candidateId,preparationRef:stage==='preparing'||cancelled?undefined:'DEMO-CHECK-'+id,dispatchNote:['shipped','received','completed'].includes(stage)?'演示发货，无真实地址':undefined,tracking:['shipped','received','completed'].includes(stage)?'DEMO-TRACK-'+id:undefined,shippedAt:['shipped','received','completed'].includes(stage)?stamp:undefined,receivedAt:['received','completed'].includes(stage)?stamp:undefined,deliveryEvidence:completed?'演示：已核对实际交付及接收对象':undefined,createdAt:stamp,demoReadOnly:cancelled||stage==='attention',demoNote:stage==='attention'?'异常只读示意：运输异常与争议处理规则待定，不擅自恢复旧卡、退费或改归属。':cancelled?'只读取消历史示意；取消条件、退费和冻结解除规则尚未批准。':undefined,history:[{time:stamp,text:`演示样例：${names[index]}；不是实际业务证据`}]});
  }
  for(const [offset,status] of (['disabled','archived'] as const).entries()){
    const id=120+offset,chipId=301+offset,chipUid=`04:DE:30:00:00:00:0${offset+1}`;
    data.chips.push({...baseChip,id:chipId,chip_uid:chipUid,item_id:id,chip_status:status==='disabled'?'disabled':'retired',keys_generated:true,provisioned_at:stamp,batch_no:'DEMO-STATE',created_at:stamp,updated_at:stamp});
    data.items.push({...baseItem,id,item_uid:`FASH-2026-${String(id).padStart(6,'0')}`,status,owner_account_id:'DEMO-OWNER-C',bound_chip_id:status==='archived'?null:chipId,bound_chip_uid:status==='archived'?null:chipUid,bound_chip_status:status==='archived'?null:'disabled',bound_chip_keys_generated:status!=='archived',bound_chip_provisioned_at:status==='archived'?null:stamp,created_at:stamp,updated_at:stamp});
    data.identities[id]={...structuredClone(baseIdentity),firstOwnerAt:stamp,editionNumber:30+offset,ownerId:'DEMO-OWNER-C',used:0,quotaReview:false,entities:[{id:`E-DEMO-${id}`,delivery:1,size:'M',color:'黑色',chipId,chipUid,activatedAt:stamp,...(status==='archived'?{exitedAt:stamp,reason:'只读归档/退役历史样例，不提供归档执行或恢复入口'}:{})}],ownership:[{ownerId:'DEMO-OWNER-C',from:stamp}]};
  }
  const style=data.styles[0];
  data.styles.push({id:'STYLE-UNUSED',code:'BB-DEMO-NEXT',project:'fashion',profile:{...style.profile,name:'下一款产品 · 未引用样例',description:'演示尚未关联任何物品的共用款式'},sizes:['S','M','L']});
  data.issuances.push({id:'ISSUE-DEMO-DRAFT',name:'同款再次发行 · 草稿样例',series:'限定T恤',version:'下一次发行草案',styleId:style.id,total:50,color:'蓝色',rightIds:[],description:'模拟同款再次发行的不同颜色和权益约定；草稿不影响首次发行物品。新编号范围未定，不能发行。',status:'draft'});
  return data;
}
