import React, {useEffect, useState} from 'react';
import {Alert, App, Button, Card, Checkbox, Col, Collapse, Descriptions, Empty, Form, Input, InputNumber, Modal, Row, Select, Space, Steps, Table, Tag, Timeline, Typography} from 'antd';
import {usePrototype, now, timeText} from '../data/prototypeStore';
import type {FirstDelivery, SalesPlan} from '../data/firstSales';
import {firstStages} from '../data/firstSales';
import {beijingInput,isValidSale} from '../data/salesJourney';

const {Text}=Typography;
export function FirstSalesPage({onOpenItem,onManageItems,onManageChips,planId,initialRecordId,onRecordChange,onPrepareItem,onOpenSale}:{onOpenItem:(id:number)=>void;onManageItems:()=>void;onManageChips:(record?:FirstDelivery)=>void;planId?:string;initialRecordId?:string|null;onRecordChange?:(id:string|null)=>void;onPrepareItem?:(id:string)=>{ok:boolean;error?:string};onOpenSale?:(id:string)=>void}) {
  const p=usePrototype(), {message}=App.useApp();
  const [create,setCreate]=useState(false);
  const [active,setActive]=useState<string|null>(initialRecordId||null), [keyword,setKeyword]=useState('');
  const [phase,setPhase]=useState('');
  const [orderForm]=Form.useForm(), [form]=Form.useForm();
  const [dirty,setDirty]=useState(false), [error,setError]=useState(''), [unknown,setUnknown]=useState(false);
  const [checks,setChecks]=useState<string[]>([]);
  const [exceptionEditor,setExceptionEditor]=useState<'pause'|'resume'|null>(null),[exceptionText,setExceptionText]=useState('');
  const selectedPlanId=Form.useWatch('planId',orderForm);const selectedPlan=p.salesPlans.find(s=>s.id===selectedPlanId);
  useEffect(()=>{setActive(initialRecordId||null);},[initialRecordId]);
  const record=p.firstDeliveries.find(r=>r.id===active), plan=p.salesPlans.find(s=>s.id===record?.planId);
  const selectedItemId=Form.useWatch('itemId',form);
  const item=p.items.find(i=>i.id===(selectedItemId??record?.itemId));
  const chip=p.chips.find(c=>c.id===(record?.chipId??item?.bound_chip_id));
  const close=()=>{setActive(null);setCreate(false);setDirty(false);setError('');setUnknown(false);setExceptionEditor(null);onRecordChange?.(null);};
  const leave=(next:()=>void)=>dirty?Modal.confirm({title:'放弃尚未保存的修改？',content:'已保存的订单与交付事实会保留。',okText:'放弃修改',cancelText:'继续编辑',onOk:()=>{close();next();}}):next();
  useEffect(()=>{
    if(!active&&!create)return;
    p.setGuard(leave);
    const unload=(e:BeforeUnloadEvent)=>{if(dirty){e.preventDefault();e.returnValue='';}};
    window.addEventListener('beforeunload',unload);
    return ()=>{p.setGuard(null);window.removeEventListener('beforeunload',unload);};
  },[active,create,dirty]);
  useEffect(()=>{
    form.resetFields();form.setFieldsValue(record||{});setChecks([]);setDirty(false);setError('');setUnknown(false);
  },[active,record?.stage]);
  useEffect(()=>{if(record?.itemId)form.setFieldValue('itemId',record.itemId);},[record?.itemId]);
  const attempt=()=>{
    if(unknown)return false;
    if(p.failureMode==='save'||p.failureMode==='unknown'){
      setError(p.failureMode==='unknown'?'保存结果待核对：本次演示未写入，输入保留。':'模拟保存失败，输入保留。');
      setUnknown(p.failureMode==='unknown');return false;
    }
    return true;
  };
  const feedback=error&&<Alert showIcon type="warning" title={error} action={unknown?<Button onClick={()=>{p.setFailureMode('none');setUnknown(false);setError('已核对：本次未保存，可明确重试。');}}>核对保存结果</Button>:undefined}/>;
  const saveRecord=(patch:Partial<FirstDelivery>,text:string)=>{
    if(!record||!attempt())return;
    if(patch.saleState&&patch.saleState!==(record.saleState||'valid')&&plan?.sealedAt){setError('封版后不普通改写核定销量，请按售后流程核对。');return;}
    if(patch.saleState&&patch.saleState!==(record.saleState||'valid'))p.setSalesPlans(prev=>prev.map(s=>s.id===record.planId?{...s,channels:s.channels?.map(c=>c.id===record.channelId?{...c,checkedAt:undefined}:c)}:s));
    p.setFirstDeliveries(prev=>prev.map(r=>r.id===record.id?{...r,...patch,history:[...r.history,{time:now(),text}]}:r));
    p.audit('item','首次交付记录',record.id,text+'；仅合成事实，不启用或认领');setDirty(false);setError('');message.success('首次交付记录已保存');
  };
  const saveStage=async()=>{
    if(!record)return;
    let v;try{v=await form.validateFields();}catch{return;}
    if(record.stage===0){const fixed=p.issuances.find(i=>i.id===plan?.issuanceId);if(v.saleState==='valid'&&!isValidSale(record)&&plan?.mode==='fixed'&&fixed?.total!=null&&p.firstDeliveries.filter(r=>r.planId===plan.id&&isValidSale(r)).length>=fixed.total){setError('有效销售件数将超过固定发行上限，请核对或保持待核，不增发身份。');return;}if(v.saleState==='valid'&&plan?.mode==='timed'&&record.paidAt&&(record.paidAt<(plan.startAt||'')||record.paidAt>(plan.endAt||''))){setError('付款不在约定窗口，请保留待核或排除状态，不能直接计入有效销量。');return;}saveRecord({...v,stage:v.saleState==='excluded'||v.saleState==='review'?0:1},'已保存销售/投产人工核对：'+(v.saleState||'valid')+'；尚未证明工厂接单');}
    if(record.stage===1){saveRecord({...v,stage:v.factoryReceipt?.trim()?2:1},v.factoryReceipt?.trim()?'已记录工厂接单及来货依据：'+v.factoryRef+' / '+v.factoryReceipt:'已独立保存工厂接单，尚未来货：'+v.factoryRef);}
    if(record.stage===2){
      v={...v,qualityAttempts:[...(record.qualityAttempts||[]),{time:now(),actualSpec:v.actualSpec,quality:v.quality,evidence:v.qualityEvidence}]};
      if(v.quality==='fail'){saveRecord({...v,exception:'到货不合格，等待返工核对'},'到货不合格：未进入配卡/可发货，保留验收事实');return;}
      saveRecord({...v,exception:undefined,stage:3},'到货验收通过，已记录实际规格；等待配卡与出厂检查');
    }
    if(record.stage===3){
      const target=p.items.find(i=>i.id===v.itemId),issue=p.issuances.find(i=>i.id===p.identities[v.itemId]?.issuanceId);
      const targetChip=p.chips.find(c=>c.id===target?.bound_chip_id);
      if(!target||(plan?.issuanceId&&issue?.id!==plan.issuanceId)||target.style_id!==plan?.styleId||target.status==='archived'||!issue||issue.status!=='issued'||issue.styleId!==plan?.styleId||p.identity(target).ownerId){setError('请选同款已关联确认发行、尚未归属的数字物品；不能借首交重分配身份。');return;}
      if(p.firstDeliveries.some(r=>r.id!==record.id&&r.itemId===target.id)){setError('该数字身份已对应其他首次交付，请核对原记录。');return;}
      if(!targetChip||targetChip.item_id!==target.id||targetChip.chip_status!=='bound'||!targetChip.provisioned_at||!targetChip.keys_generated){setError('关联芯片尚未完成配卡核验，请从物品详情使用已有配卡流程。');return;}
      if(checks.length!==4){setError('请逐项核对实体、规格/编号、芯片和用户资料。');return;}
      saveRecord({...v,chipId:targetChip.id,chipUid:targetChip.chip_uid,configuredAt:targetChip.provisioned_at,stage:4},'发货前四项检查通过，保存单件与实体/芯片对应；未自动启用或认领');
    }
    if(record.stage===4){saveRecord({...v,stage:5},'已记录品牌寄给顾客；不等于收货、启用或所有权确认');}
    if(record.stage===5){saveRecord({...v,stage:6},'实物交付事实已记录；首次启用与归属仍待独立确认');}
  };
  const exception=()=>{setExceptionText('');setExceptionEditor('pause');};
  const clearException=()=>{setExceptionText('');setExceptionEditor('resume');};
  const rows=p.firstDeliveries.filter(r=>{const s=p.salesPlans.find(s=>s.id===r.planId);return (!phase||(phase==='exception'?!!r.exception:phase==='review'?r.saleState==='review':String(r.stage)===phase))&&(!planId||r.planId===planId)&&`${r.orderRef} ${r.lineRef} ${s?.name} ${r.id}`.toLowerCase().includes(keyword.toLowerCase());});
  const required=[{required:true,whitespace:true,message:'请填写已核对的事实'}];
  const textField=(name:string,label:string,placeholder?:string)=><Form.Item name={name} label={label} rules={required}><Input.TextArea rows={2} maxLength={1000} placeholder={placeholder}/></Form.Item>;
  return <div className="proto-stack">
    <Alert type="info" showIcon title={planId?'本次发售的订单与交付':'全部首次交付任务'} description="销售与生产交付并行。先登记外部订单件次，再按需生产、验收、配卡及交付；每次质量和芯片对应保留历史。"/>
    <Card size="small" title="首次交付记录" extra={<Button type="primary" disabled={!p.salesPlans.some(s=>(!planId||s.id===planId)&&(!s.status||['selling','reconciling'].includes(s.status)))} onClick={()=>{orderForm.resetFields();orderForm.setFieldsValue({planId,quantity:1,piece:1,saleState:'valid'});setError('');setDirty(false);setCreate(true);}}>登记订单件次</Button>}>
      <Input aria-label="首次交付查询" placeholder="订单、明细、商品或办理编号" value={keyword} onChange={e=>setKeyword(e.target.value)} style={{maxWidth:400,marginBottom:16,marginRight:12}} allowClear/><Select aria-label="首次交付阶段" style={{width:210,marginBottom:16}} value={phase} onChange={setPhase} options={[{value:'',label:'全部交付阶段'},...firstStages.map((label,index)=>({value:String(index),label})),{value:'exception',label:'异常暂停'},{value:'review',label:'销售待核对'}]}/>
      <Table rowKey="id" size="middle" scroll={{x:1150}} dataSource={rows} pagination={{pageSize:10,showSizeChanger:false}} locale={{emptyText:<Empty description="暂无首交记录，先确认款式/发行并登记外部订单件次"/>}} columns={[
        {title:'订单 / 明细 / 件次',render:(_,r)=>`${r.orderRef} / ${r.lineRef} / 第${r.piece}件`},
        {title:'本次发售',render:(_,r)=><Button type="link" onClick={()=>onOpenSale?.(r.planId)}>{p.salesPlans.find(s=>s.id===r.planId)?.name}</Button>},
        {title:'规格',dataIndex:'requestedSpec'},{title:'销售核对',render:(_,r)=>r.saleState==='review'?'待核对':r.saleState==='excluded'?'已排除':'有效'},
        {title:'数字物品',render:(_,r)=>{const i=p.items.find(i=>i.id===r.itemId);return i?<Button type="link" onClick={()=>p.guard(()=>onOpenItem(i.id))}>{i.item_uid}</Button>:'待核对登记';}},
        {title:'当前进度',render:(_,r)=><Tag color={r.exception?'error':r.stage===6?'success':'processing'}>{r.exception?'异常暂停':firstStages[r.stage]}</Tag>},
        {title:'操作',fixed:'right',width:110,render:(_,r)=><Button onClick={()=>{setDirty(false);setActive(r.id);onRecordChange?.(r.id);}}>{r.stage===6?'查看交付':'继续首交'}</Button>},
      ]}/>
    </Card>
    <Modal open={create} centered width={720} title="登记订单件次" mask={{closable:false}} onCancel={()=>leave(close)} footer={<Space><Button onClick={()=>leave(close)}>取消</Button><Button type="primary" disabled={unknown} onClick={async()=>{
      let v;try{v=await orderForm.validateFields();}catch{return;}
      v={...v,orderRef:v.orderRef.trim(),lineRef:v.lineRef.trim(),requestedSpec:v.requestedSpec.trim(),recipientRef:v.recipientRef.trim()};
      const selected=p.salesPlans.find(s=>s.id===v.planId),channel=selected?.channels?.find(c=>c.id===v.channelId);
      if(!selected||selected.sealedAt||selected.status&&!['selling','reconciling'].includes(selected.status)){setError('请先确认规则并开始销售；封版后不能补入本次销售。');return;}
      if(selected.channels?.length&&!channel){setError('请选择本次发售的网店商品');return;}
      const paidAt=v.paid?beijingInput(v.paid):undefined;
      if(selected.mode==='timed'&&v.saleState==='valid'&&(!paidAt||paidAt<(selected.startAt||'')||paidAt>(selected.endAt||''))){setError('有效订单须在约定付款窗口内；跨期请登记待核对。');return;}
      const count=v.quantity||1;const issue=p.issuances.find(i=>i.id===selected.issuanceId);
      if(v.saleState==='valid'&&selected.mode==='fixed'&&issue?.total!=null&&p.firstDeliveries.filter(r=>r.planId===selected.id&&isValidSale(r)).length+count>issue.total){setError('有效销售件数将超过固定发行上限，请核对或登记为待核对，不增发身份。');return;}
      const pieces=Array.from({length:count},(_,i)=>v.piece+i);
      const shop=(s:SalesPlan,r:FirstDelivery)=>s.channels?.find(c=>c.id===r.channelId)?.shop||s.channel;
      if(p.firstDeliveries.some(r=>r.orderRef===v.orderRef&&r.lineRef===v.lineRef&&pieces.includes(r.piece)&&shop(p.salesPlans.find(s=>s.id===r.planId)||selected,r)===(channel?.shop||selected.channel))){setError('该店铺订单明细的件次已登记，请查询原记录。');return;}
      if(!attempt())return;
      const {quantity:_quantity,paid:_paid,...values}=v;
      const entries:FirstDelivery[]=pieces.map(piece=>({...values,piece,paidAt,id:'FIRST-'+crypto.randomUUID().slice(0,12),stage:0,history:[{time:now(),text:'已保存外部订单件次；核对范围：'+v.salesEvidence}]}));
      p.setFirstDeliveries(prev=>[...entries,...prev]);p.setSalesPlans(prev=>prev.map(s=>s.id===selected.id?{...s,channels:s.channels?.map(c=>c.id===v.channelId?{...c,checkedAt:undefined}:c)}:s));setCreate(false);setActive(entries[0].id);onRecordChange?.(entries[0].id);setDirty(false);
    }}>保存订单件次</Button></Space>}>
      <Alert type="info" title="一条记录对应订单中的一件商品" description="同单多件分别填写明细和件次；只保存外部引用，不复制收货地址、支付或客户账号。" showIcon style={{marginBottom:16}}/>
      <Form name="first_order" form={orderForm} layout="vertical" initialValues={{piece:1}} onValuesChange={()=>{setDirty(true);if(!unknown)setError('');}}>
        <Form.Item name="planId" label="销售计划" rules={[{required:true}]}><Select options={p.salesPlans.filter(s=>(!planId||s.id===planId)&&(!s.status||['selling','reconciling'].includes(s.status))).map(s=>({value:s.id,label:s.name}))}/></Form.Item>
        {!!selectedPlan?.channels?.length&&<Form.Item name="channelId" label="网店商品" rules={[{required:true}]}><Select options={selectedPlan.channels.map(c=>({value:c.id,label:c.shop+' / '+c.productRef}))}/></Form.Item>}
        <Form.Item name="quantity" label="本次登记件数（同一明细逐件展开）" rules={[{required:true},{type:'number',min:1,max:10000}]}><InputNumber precision={0} min={1} max={10000}/></Form.Item>
        <Form.Item name="saleState" label="销售有效性核对" rules={[{required:true}]}><Select options={[{value:'valid',label:'已核对有效'},{value:'review',label:'付款/退款/跨期等待核对'}]}/></Form.Item>
        {selectedPlan?.mode==='timed'&&<Form.Item name="paid" label="达到付款条件时间（北京时间）" rules={[{required:true}]}><Input type="datetime-local"/></Form.Item>}
        <Form.Item name="salesEvidence" label="订单范围及付款核对依据" rules={required}><Input.TextArea rows={2}/></Form.Item>
        <Row gutter={16}><Col span={12}><Form.Item name="orderRef" label="外部订单引用" rules={required}><Input maxLength={128}/></Form.Item></Col><Col span={12}><Form.Item name="lineRef" label="订单明细引用" rules={required}><Input maxLength={128}/></Form.Item></Col></Row>
        <Form.Item name="piece" label="本明细第几件" rules={[{required:true},{type:'number',min:1,max:1000000}]}><InputNumber precision={0} min={1}/></Form.Item>
        <Form.Item name="requestedSpec" label="订单要求规格" rules={required}><Input maxLength={256} placeholder="实际适用的尺寸、颜色等；不适用请注明"/></Form.Item>
        <Form.Item name="recipientRef" label="收件安排引用" rules={required}><Input maxLength={128} placeholder="如订单收件安排A／礼赠安排B，不填真实地址或手机号"/></Form.Item>
      </Form>{feedback}
    </Modal>
    <Modal open={!!record} centered width={1120} title={`首次销售与交付 · ${record?.id||''}`} mask={{closable:false}} onCancel={()=>leave(close)} styles={{body:{maxHeight:'calc(100dvh - 220px)',overflowY:'auto'}}} footer={<Space wrap>
      <Button onClick={()=>leave(close)}>返回并保留已保存进度</Button>
      {record&&record.stage<6&&<Button danger onClick={exception} disabled={unknown}>记录异常并暂停</Button>}
      {record?.exception?<Button onClick={clearException} disabled={unknown}>核对后继续</Button>:record&&record.stage<6?<Button type="primary" onClick={()=>void saveStage()} disabled={unknown}>{['保存投产核对',record.factoryRef?'记录来货，进入验收':'保存工厂接单','保存验收结果','保存出厂检查','记录品牌发货','记录实际交付'][record.stage]}</Button>:null}
    </Space>}>
      {record&&<div className="proto-stack">
        <Steps size="small" current={record.stage} items={firstStages.map(title=>({title}))}/>
        <Descriptions size="small" column={3} items={[{label:'销售计划',children:plan?.name},{label:'订单件次',children:`${record.orderRef} / ${record.lineRef} / ${record.piece}`},{label:'收件安排',children:record.recipientRef},{label:'订单要求规格',children:record.requestedSpec},{label:'实际规格',children:record.actualSpec||'待验收'},{label:'首次归属',children:'本记录不自动确认归属'}]}/>
        {record.exception&&<Alert type="error" showIcon title="异常暂停" description={record.exception+'；原身份、名额与历史保留，不自动取消或退款。'}/>}
        <Row gutter={24}><Col span={15}><Form name="first_stage" form={form} layout="vertical" disabled={!!record.exception||record.stage===6} onValuesChange={()=>setDirty(true)}>
          {record.stage===0&&<Card size="small" title="人工核对本单是否可投产"><Form.Item name="saleState" label="销售核对结论"><Select disabled={!!plan?.sealedAt} options={[{value:'valid',label:'核对有效'},{value:'review',label:'继续待核'},{value:'excluded',label:'核对排除（不删除记录）'}]}/></Form.Item>{textField('productionEvidence','投产核对依据','说明已核对付款/定金、规格、名额及订单有效性；不代表系统已有统一自动投产政策')}<Text type="secondary">取消、名额释放和投产规则尚待定稿。这里只记录本单人工核对结果，不自动派单。</Text></Card>}
          {record.stage===1&&<Card size="small" title="工厂生产与寄给品牌">{textField('factoryRef','工厂接单确认','生产清单及接单依据；消息已发出不等于工厂已接单')}<Form.Item name="factoryReceipt" label="工厂来货引用（未寄出时可留空）"><Input.TextArea rows={2} placeholder="来货后填写，保存并进入验收；没有来货时可先独立保存接单"/></Form.Item></Card>}
          {record.stage===2&&<Card size="small" title="到货验收">{textField('actualSpec','实际实体规格','尺寸、颜色或其他适用事实；不按品类另走流程')}<Form.Item name="quality" label="实体质量结果" rules={[{required:true}]}><Select options={[{value:'pass',label:'合格'},{value:'fail',label:'不合格，暂停交付'}]}/></Form.Item>{textField('qualityEvidence','验收依据','对应样品标准、外观和规格核对；不合格不得继续配卡发货')}</Card>}
          {record.stage===3&&<Card size="small" title="关联数字身份与出厂检查">
            <Alert showIcon type="info" title="先使用已有数字物品和芯片流程完成建档配卡" description="限时模式先准备稳定身份，正式编号在封版时确定；固定发行按已确认约定登记。此处不自动认领或发放权益。" style={{marginBottom:16}}/>
            <Form.Item name="itemId" label="对应数字物品" rules={[{required:true}]}><Select showSearch optionFilterProp="label" options={p.items.filter(i=>(!plan?.issuanceId||p.identity(i).issuanceId===plan.issuanceId)&&i.style_id===plan?.styleId&&!p.identity(i).ownerId&&i.status!=='archived').map(i=>({value:i.id,label:i.item_uid+' · '+(p.identity(i).edition||'未关联发行')}))}/></Form.Item>
            <Space wrap style={{marginBottom:16}}>{onPrepareItem&&plan?.issuanceId&&!record.itemId&&<Button type="primary" onClick={()=>{if(!attempt())return;const result=onPrepareItem(record.id);if(!result.ok)setError(result.error||'建档失败');}}>为本件建档并关联</Button>}<Button onClick={()=>leave(()=>{close();onManageItems();})}>登记数字物品</Button><Button onClick={()=>leave(()=>{close();onManageChips(record);})}>芯片登记与配卡</Button></Space><Text type="secondary">从任务进入配卡后，可用“返回本次交付”回到本件，继续出厂检查。</Text>
            {textField('checkEvidence','出厂检查依据','引用真实验收/配卡记录；本原型只能保存合成样例')}
            <Checkbox.Group value={checks} onChange={v=>{setChecks(v as string[]);setDirty(true);}} options={['实体质量已通过','订单规格与发行编号对应','关联芯片及配置核验对应','用户商品资料正确']}/>
          </Card>}
          {record.stage===4&&<Card size="small" title="品牌寄给顾客">{textField('tracking','品牌发货引用','核对收件安排后填写物流引用；不等于顾客收货或认领')}<Alert type="info" title="只记录物流，不改变物品启用状态或持有人"/></Card>}
          {record.stage===5&&<Card size="small" title="实际交付核对">{textField('receiptEvidence','实际交付依据','核对收件安排与实际收到；物流签收不能直接确认所有权')}</Card>}
          {record.stage===6&&<Alert type="success" showIcon title="实物交付事实已记录" description="此记录不自动启用物品、不建立持有人或消耗换新额度。首次启用/归属及礼赠政策仍待确认。"/>}
        </Form>{feedback}</Col><Col span={9}><Card size="small" title="本次实体与芯片事实">
          <Descriptions column={1} size="small" items={[{label:'首次实体记录',children:'ENTITY-'+record.id},{label:'实际规格',children:record.actualSpec||'尚未验收'},{label:'数字物品',children:item?<Button type="link" onClick={()=>leave(()=>onOpenItem(item.id))}>{item.item_uid}</Button>:'未关联'},{label:'芯片',children:record.chipUid||chip?.chip_uid||'未关联'},{label:'配置核验',children:timeText(record.configuredAt||chip?.provisioned_at)},{label:'品牌发货',children:record.tracking||'未记录'},{label:'实际交付',children:record.receiptEvidence||'未记录'}]}/>
          <Text type="secondary">准备与实物交付事实不等于当前授权；取消/退款不自动释放发行序号。</Text>
        </Card></Col></Row>
        <Collapse items={[{key:'history',label:'查看本次办理历史',children:<><Descriptions column={1} items={[{label:'投产核对依据',children:record.productionEvidence},{label:'工厂接单',children:record.factoryRef},{label:'工厂寄给品牌',children:record.factoryReceipt},{label:'出厂检查',children:record.checkEvidence}]}/><Table rowKey="time" size="small" pagination={{pageSize:5,showSizeChanger:false}} dataSource={record.qualityAttempts||[]} columns={[{title:'验收时间',render:(_,a)=>timeText(a.time)},{title:'实际规格',dataIndex:'actualSpec'},{title:'结果',render:(_,a)=>a.quality==='pass'?'合格':'不合格'},{title:'依据',dataIndex:'evidence'}]}/><Timeline items={record.history.map((h,i)=>({key:i,title:timeText(h.time),content:h.text}))}/></>} ]}/>
      </div>}
    </Modal>
    <Modal title={exceptionEditor==='pause'?'记录异常并暂停':'核对后继续原阶段'} open={!!exceptionEditor} onCancel={()=>{setExceptionEditor(null);setExceptionText('');}} okText={exceptionEditor==='pause'?'保存异常':'记录核对依据并继续'} onOk={()=>{const reason=exceptionText.trim();if(!reason){message.warning('请填写当前核对依据');return;}if(!attempt())return;saveRecord(exceptionEditor==='pause'?{exception:reason}:{exception:undefined},(exceptionEditor==='pause'?'异常暂停：':'异常核对后继续：')+reason);setExceptionEditor(null);setExceptionText('');}}>
      <Input.TextArea aria-label={exceptionEditor==='pause'?'异常说明':'异常处理依据'} value={exceptionText} onChange={e=>setExceptionText(e.target.value)} rows={3}/>{feedback}
    </Modal>
  </div>;
}
