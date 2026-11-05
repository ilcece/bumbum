import React, {useEffect, useState} from 'react';
import {Alert, App, Button, Card, Checkbox, Col, Collapse, Descriptions, Empty, Form, Input, InputNumber, Modal, Row, Select, Space, Steps, Table, Tag, Timeline, Typography} from 'antd';
import {usePrototype, now, timeText} from '../data/prototypeStore';
import type {FirstDelivery, SalesPlan} from '../data/firstSales';
import {firstStages} from '../data/firstSales';

const {Text}=Typography;
export function FirstSalesPage({onOpenItem,onManageItems,onManageChips}:{onOpenItem:(id:number)=>void;onManageItems:()=>void;onManageChips:()=>void}) {
  const p=usePrototype(), {message}=App.useApp();
  const [planEditor,setPlanEditor]=useState(false), [create,setCreate]=useState(false);
  const [active,setActive]=useState<string|null>(null), [keyword,setKeyword]=useState('');
  const [planForm]=Form.useForm(), [orderForm]=Form.useForm(), [form]=Form.useForm();
  const [dirty,setDirty]=useState(false), [error,setError]=useState(''), [unknown,setUnknown]=useState(false);
  const [checks,setChecks]=useState<string[]>([]);
  const record=p.firstDeliveries.find(r=>r.id===active), plan=p.salesPlans.find(s=>s.id===record?.planId);
  const selectedItemId=Form.useWatch('itemId',form);
  const item=p.items.find(i=>i.id===(selectedItemId??record?.itemId));
  const chip=p.chips.find(c=>c.id===item?.bound_chip_id);
  const close=()=>{setActive(null);setCreate(false);setPlanEditor(false);setDirty(false);setError('');setUnknown(false);};
  const leave=(next:()=>void)=>dirty?Modal.confirm({title:'放弃尚未保存的修改？',content:'已保存的订单与交付事实会保留。',okText:'放弃修改',cancelText:'继续编辑',onOk:()=>{close();next();}}):next();
  useEffect(()=>{
    if(!active&&!create&&!planEditor)return;
    p.setGuard(leave);
    const unload=(e:BeforeUnloadEvent)=>{if(dirty){e.preventDefault();e.returnValue='';}};
    window.addEventListener('beforeunload',unload);
    return ()=>{p.setGuard(null);window.removeEventListener('beforeunload',unload);};
  },[active,create,planEditor,dirty]);
  useEffect(()=>{
    form.resetFields();form.setFieldsValue(record||{});setChecks([]);setDirty(false);setError('');setUnknown(false);
  },[active,record?.stage]);
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
    p.setFirstDeliveries(prev=>prev.map(r=>r.id===record.id?{...r,...patch,history:[...r.history,{time:now(),text}]}:r));
    p.audit('item','首次交付记录',record.id,text+'；仅合成事实，不启用或认领');setDirty(false);setError('');message.success('首次交付记录已保存');
  };
  const saveStage=async()=>{
    if(!record)return;
    let v;try{v=await form.validateFields();}catch{return;}
    if(record.stage===0){saveRecord({...v,stage:1},'人工完成本单投产条件核对，尚未证明工厂接单');}
    if(record.stage===1){saveRecord({...v,stage:2},'已记录工厂接单和寄给品牌的来货依据');}
    if(record.stage===2){
      if(v.quality==='fail'){saveRecord({...v,exception:'到货不合格，等待返工核对'},'到货不合格：未进入配卡/可发货，保留验收事实');return;}
      saveRecord({...v,exception:undefined,stage:3},'到货验收通过，已记录实际规格；等待配卡与出厂检查');
    }
    if(record.stage===3){
      const target=p.items.find(i=>i.id===v.itemId),issue=p.issuances.find(i=>i.id===p.identities[v.itemId]?.issuanceId);
      const targetChip=p.chips.find(c=>c.id===target?.bound_chip_id);
      if(!target||target.style_id!==plan?.styleId||target.status==='archived'||!issue||issue.status!=='issued'||issue.styleId!==plan?.styleId||p.identity(target).ownerId){setError('请选同款已关联确认发行、尚未归属的数字物品；不能借首交重分配身份。');return;}
      if(p.firstDeliveries.some(r=>r.id!==record.id&&r.itemId===target.id)){setError('该数字身份已对应其他首次交付，请核对原记录。');return;}
      if(!targetChip||targetChip.item_id!==target.id||targetChip.chip_status!=='bound'||!targetChip.provisioned_at||!targetChip.keys_generated){setError('关联芯片尚未完成配卡核验，请从物品详情使用已有配卡流程。');return;}
      if(checks.length!==4){setError('请逐项核对实体、规格/编号、芯片和用户资料。');return;}
      saveRecord({...v,stage:4},'发货前四项检查通过，保存单件与实体/芯片对应；未自动启用或认领');
    }
    if(record.stage===4){saveRecord({...v,stage:5},'已记录品牌寄给顾客；不等于收货、启用或所有权确认');}
    if(record.stage===5){saveRecord({...v,stage:6},'实物交付事实已记录；首次启用与归属仍待独立确认');}
  };
  const exception=()=>Modal.confirm({title:'记录异常并暂停',content:<Input.TextArea aria-label="异常说明" placeholder="取消、退款、运输异常或错配；请说明已核对事实" onChange={e=>form.setFieldValue('exceptionNote',e.target.value)}/>,okText:'保存异常',cancelText:'返回',onOk:()=>{
    const reason=String(form.getFieldValue('exceptionNote')||'').trim();if(!reason){message.warning('请填写异常说明');return Promise.reject();}
    saveRecord({exception:reason},'异常暂停：'+reason+'；不释放名额/编号，不删除身份或自动恢复授权');
  }});
  const clearException=()=>Modal.confirm({title:'核对后继续原阶段？',content:<Input.TextArea aria-label="异常处理依据" placeholder="填写已核对的处理依据；不代表已执行退款或取消" onChange={e=>form.setFieldValue('resolution',e.target.value)}/>,okText:'记录核对依据并继续',cancelText:'返回',onOk:()=>{
    const reason=String(form.getFieldValue('resolution')||'').trim();if(!reason){message.warning('请填写核对依据');return Promise.reject();}
    if(record?.quality==='fail'&&record.stage!==2){message.warning('不合格来货须回到验收核对');return Promise.reject();}
    saveRecord({exception:undefined},'异常核对后继续原阶段：'+reason);
  }});
  const rows=p.firstDeliveries.filter(r=>{const s=p.salesPlans.find(s=>s.id===r.planId);return `${r.orderRef} ${r.lineRef} ${s?.name} ${r.id}`.toLowerCase().includes(keyword.toLowerCase());});
  const required=[{required:true,whitespace:true,message:'请填写已核对的事实'}];
  const textField=(name:string,label:string,placeholder?:string)=><Form.Item name={name} label={label} rules={required}><Input.TextArea rows={2} maxLength={1000} placeholder={placeholder}/></Form.Item>;
  return <div className="proto-stack">
    <Alert type="info" showIcon title="同一条首次销售与交付流程" description="网店接单、工厂派单先人工处理；后台记录订单件次、验收、配卡与物流。销售计划数不等于数字发行上限；不会自动扣库存、派单、启用或绑定持有人。"/>
    <Collapse items={[{key:'plans',label:`销售准备 · ${p.salesPlans.length}个计划`,children:<div className="proto-stack">
      <Space wrap><Button onClick={()=>{planForm.resetFields();setDirty(false);setError('');setPlanEditor(true);}}>新建销售计划</Button><Button data-demo-only onClick={()=>{p.seedFirstSales();message.info('已添加三类合成销售计划；未创建发行、数字身份或芯片。');}}>〔演示〕添加三类销售样例</Button></Space>
      <Table rowKey="id" size="small" scroll={{x:900}} dataSource={p.salesPlans} pagination={{pageSize:10,showSizeChanger:false}} columns={[
        {title:'销售计划',dataIndex:'name'},{title:'本轮计划数量',dataIndex:'quantity'},
        {title:'数字发行',render:(_,s)=>{const issues=p.issuances.filter(i=>i.styleId===s.styleId&&i.status==='issued');return issues.length?issues.map(i=>i.total===null?'非限定／无上限':`限定${i.total}个身份`).join('；'):'待确认发行约定';}},
        {title:'渠道商品',render:(_,s)=>s.channel+' / '+s.productRef},
        {title:'已登记首交',render:(_,s)=>p.firstDeliveries.filter(r=>r.planId===s.id).length},
        {title:'实物交付完成',render:(_,s)=>p.firstDeliveries.filter(r=>r.planId===s.id&&r.stage===6).length},
        {title:'操作',render:(_,s)=><Button size="small" onClick={()=>{orderForm.resetFields();orderForm.setFieldValue('planId',s.id);setError('');setDirty(false);setCreate(true);}}>登记订单件次</Button>},
      ]}/><Text type="secondary">计划数、已登记首交、实物交付数各有口径；此处不计算可售余额。手串50身份已确认，T恤100件／帽子20个仅为销售计划，真实发行类型另定。</Text>
    </div>}]} defaultActiveKey={['plans']}/>
    <Card size="small" title="首次交付记录" extra={<Button type="primary" disabled={!p.salesPlans.length} onClick={()=>{orderForm.resetFields();setError('');setDirty(false);setCreate(true);}}>登记订单件次</Button>}>
      <Input aria-label="首次交付查询" placeholder="订单、明细、商品或办理编号" value={keyword} onChange={e=>setKeyword(e.target.value)} style={{maxWidth:400,marginBottom:16}} allowClear/>
      <Table rowKey="id" size="middle" scroll={{x:1150}} dataSource={rows} pagination={{pageSize:10,showSizeChanger:false}} locale={{emptyText:<Empty description="暂无首交记录，先确认款式/发行并登记外部订单件次"/>}} columns={[
        {title:'订单 / 明细 / 件次',render:(_,r)=>`${r.orderRef} / ${r.lineRef} / 第${r.piece}件`},
        {title:'销售计划',render:(_,r)=>p.salesPlans.find(s=>s.id===r.planId)?.name},
        {title:'规格',dataIndex:'requestedSpec'},
        {title:'数字物品',render:(_,r)=>{const i=p.items.find(i=>i.id===r.itemId);return i?<Button type="link" onClick={()=>p.guard(()=>onOpenItem(i.id))}>{i.item_uid}</Button>:'待核对登记';}},
        {title:'当前进度',render:(_,r)=><Tag color={r.exception?'error':r.stage===6?'success':'processing'}>{r.exception?'异常暂停':firstStages[r.stage]}</Tag>},
        {title:'操作',fixed:'right',width:110,render:(_,r)=><Button onClick={()=>{setDirty(false);setActive(r.id);}}>{r.stage===6?'查看交付':'继续首交'}</Button>},
      ]}/>
    </Card>
    <Modal open={planEditor} centered width={720} title="新建销售计划" mask={{closable:false}} onCancel={()=>leave(close)} footer={<Space><Button onClick={()=>leave(close)}>取消</Button><Button type="primary" disabled={unknown} onClick={async()=>{
      let v;try{v=await planForm.validateFields();}catch{return;}if(!attempt())return;
      const entry:SalesPlan={...v,id:crypto.randomUUID(),name:v.name.trim(),channel:v.channel.trim(),productRef:v.productRef.trim()};
      p.setSalesPlans(prev=>[...prev,entry]);p.audit('item','创建销售计划',entry.name,'数量仅为本轮计划，不修改发行承诺');close();
    }}>保存销售计划</Button></Space>}>
      <Alert type="info" showIcon title="仅保存销售计划，不上架、不扣库存、不生成身份" style={{marginBottom:16}}/>
      <Form form={planForm} layout="vertical" onValuesChange={()=>setDirty(true)}>
        <Form.Item name="name" label="销售计划名称" rules={required}><Input maxLength={128}/></Form.Item>
        <Form.Item name="styleId" label="引用款式" rules={[{required:true}]}><Select options={p.styles.map(s=>({value:s.id,label:s.code+' · '+s.profile.name}))}/></Form.Item>
        <Form.Item name="quantity" label="本轮计划销售数量" rules={[{required:true},{type:'number',min:1,max:1000000}]}><InputNumber precision={0} min={1}/></Form.Item>
        <Form.Item name="channel" label="平台与店铺引用" rules={required}><Input maxLength={128} placeholder="只填外部引用，不录入账号密码"/></Form.Item>
        <Form.Item name="productRef" label="渠道商品引用" rules={required}><Input maxLength={128}/></Form.Item>
      </Form>{feedback}
    </Modal>
    <Modal open={create} centered width={720} title="登记订单件次" mask={{closable:false}} onCancel={()=>leave(close)} footer={<Space><Button onClick={()=>leave(close)}>取消</Button><Button type="primary" disabled={unknown} onClick={async()=>{
      let v;try{v=await orderForm.validateFields();}catch{return;}
      v={...v,orderRef:v.orderRef.trim(),lineRef:v.lineRef.trim(),requestedSpec:v.requestedSpec.trim(),recipientRef:v.recipientRef.trim()};
      const selected=p.salesPlans.find(s=>s.id===v.planId);
      if(p.firstDeliveries.some(r=>r.orderRef===v.orderRef&&r.lineRef===v.lineRef&&r.piece===v.piece&&p.salesPlans.find(s=>s.id===r.planId)?.channel===selected?.channel)){setError('该店铺订单明细的件次已登记，请查询原记录，不能重复派产。');return;}
      if(!attempt())return;
      const entry:FirstDelivery={...v,id:'FIRST-'+crypto.randomUUID().slice(0,8),stage:0,history:[{time:now(),text:'已保存外部订单件次，未扣名额、分配数字身份或派单'}]};
      p.setFirstDeliveries(prev=>[entry,...prev]);setCreate(false);setActive(entry.id);setDirty(false);
    }}>保存订单件次</Button></Space>}>
      <Alert type="info" title="一条记录对应订单中的一件商品" description="同单多件分别填写明细和件次；只保存外部引用，不复制收货地址、支付或客户账号。" showIcon style={{marginBottom:16}}/>
      <Form form={orderForm} layout="vertical" initialValues={{piece:1}} onValuesChange={()=>{setDirty(true);if(!unknown)setError('');}}>
        <Form.Item name="planId" label="销售计划" rules={[{required:true}]}><Select options={p.salesPlans.map(s=>({value:s.id,label:s.name}))}/></Form.Item>
        <Row gutter={16}><Col span={12}><Form.Item name="orderRef" label="外部订单引用" rules={required}><Input maxLength={128}/></Form.Item></Col><Col span={12}><Form.Item name="lineRef" label="订单明细引用" rules={required}><Input maxLength={128}/></Form.Item></Col></Row>
        <Form.Item name="piece" label="本明细第几件" rules={[{required:true},{type:'number',min:1,max:1000000}]}><InputNumber precision={0} min={1}/></Form.Item>
        <Form.Item name="requestedSpec" label="订单要求规格" rules={required}><Input maxLength={256} placeholder="实际适用的尺寸、颜色等；不适用请注明"/></Form.Item>
        <Form.Item name="recipientRef" label="收件安排引用" rules={required}><Input maxLength={128} placeholder="如订单收件安排A／礼赠安排B，不填真实地址或手机号"/></Form.Item>
      </Form>{feedback}
    </Modal>
    <Modal open={!!record} centered width={1120} title={`首次销售与交付 · ${record?.id||''}`} mask={{closable:false}} onCancel={()=>leave(close)} styles={{body:{maxHeight:'calc(100dvh - 220px)',overflowY:'auto'}}} footer={<Space wrap>
      <Button onClick={()=>leave(close)}>返回并保留已保存进度</Button>
      {record&&record.stage<6&&<Button danger onClick={exception} disabled={unknown}>记录异常并暂停</Button>}
      {record?.exception?<Button onClick={clearException} disabled={unknown}>核对后继续</Button>:record&&record.stage<6?<Button type="primary" onClick={()=>void saveStage()} disabled={unknown}>{['保存投产核对','保存工厂接单与来货','保存验收结果','保存出厂检查','记录品牌发货','记录实际交付'][record.stage]}</Button>:null}
    </Space>}>
      {record&&<div className="proto-stack">
        <Steps size="small" current={record.stage} items={firstStages.map(title=>({title}))}/>
        <Descriptions size="small" column={3} items={[{label:'销售计划',children:plan?.name},{label:'订单件次',children:`${record.orderRef} / ${record.lineRef} / ${record.piece}`},{label:'收件安排',children:record.recipientRef},{label:'订单要求规格',children:record.requestedSpec},{label:'实际规格',children:record.actualSpec||'待验收'},{label:'首次归属',children:'本记录不自动确认归属'}]}/>
        {record.exception&&<Alert type="error" showIcon title="异常暂停" description={record.exception+'；原身份、名额与历史保留，不自动取消或退款。'}/>}
        <Row gutter={24}><Col span={15}><Form form={form} layout="vertical" disabled={!!record.exception||record.stage===6} onValuesChange={()=>setDirty(true)}>
          {record.stage===0&&<Card size="small" title="人工核对本单是否可投产">{textField('productionEvidence','投产核对依据','说明已核对付款/定金、规格、名额及订单有效性；不代表系统已有统一自动投产政策')}<Text type="secondary">取消、名额释放和投产规则尚待定稿。这里只记录本单人工核对结果，不自动派单。</Text></Card>}
          {record.stage===1&&<Card size="small" title="工厂生产与寄给品牌">{textField('factoryRef','工厂接单确认','生产清单及接单依据；消息已发出不等于工厂已接单')}{textField('factoryReceipt','工厂来货引用','工厂寄给品牌的物流/到货依据，不是品牌寄给顾客')}</Card>}
          {record.stage===2&&<Card size="small" title="到货验收">{textField('actualSpec','实际实体规格','尺寸、颜色或其他适用事实；不按品类另走流程')}<Form.Item name="quality" label="实体质量结果" rules={[{required:true}]}><Select options={[{value:'pass',label:'合格'},{value:'fail',label:'不合格，暂停交付'}]}/></Form.Item>{textField('qualityEvidence','验收依据','对应样品标准、外观和规格核对；不合格不得继续配卡发货')}</Card>}
          {record.stage===3&&<Card size="small" title="关联数字身份与出厂检查">
            <Alert showIcon type="info" title="先使用已有数字物品和芯片流程完成建档配卡" description="编号分配时点仍待确认；此处只引用人工明确准备的身份，不自动新建、改号或发放权益。" style={{marginBottom:16}}/>
            <Form.Item name="itemId" label="对应数字物品" rules={[{required:true}]}><Select showSearch optionFilterProp="label" options={p.items.filter(i=>i.style_id===plan?.styleId&&!p.identity(i).ownerId&&i.status!=='archived').map(i=>({value:i.id,label:i.item_uid+' · '+(p.identity(i).edition||'未关联发行')}))}/></Form.Item>
            <Space wrap style={{marginBottom:16}}><Button onClick={()=>leave(()=>{close();onManageItems();})}>登记数字物品</Button><Button onClick={()=>leave(()=>{close();onManageChips();})}>芯片登记与配卡</Button></Space><Text type="secondary">使用现有流程后，可回办理记录继续此单；已保存进度保留。</Text>
            {textField('checkEvidence','出厂检查依据','引用真实验收/配卡记录；本原型只能保存合成样例')}
            <Checkbox.Group value={checks} onChange={v=>{setChecks(v as string[]);setDirty(true);}} options={['实体质量已通过','订单规格与发行编号对应','关联芯片及配置核验对应','用户商品资料正确']}/>
          </Card>}
          {record.stage===4&&<Card size="small" title="品牌寄给顾客">{textField('tracking','品牌发货引用','核对收件安排后填写物流引用；不等于顾客收货或认领')}<Alert type="info" title="只记录物流，不改变物品启用状态或持有人"/></Card>}
          {record.stage===5&&<Card size="small" title="实际交付核对">{textField('receiptEvidence','实际交付依据','核对收件安排与实际收到；物流签收不能直接确认所有权')}</Card>}
          {record.stage===6&&<Alert type="success" showIcon title="实物交付事实已记录" description="此记录不自动启用物品、不建立持有人或消耗换新额度。首次启用/归属及礼赠政策仍待确认。"/>}
        </Form>{feedback}</Col><Col span={9}><Card size="small" title="本次实体与芯片事实">
          <Descriptions column={1} size="small" items={[{label:'首次实体记录',children:'ENTITY-'+record.id},{label:'实际规格',children:record.actualSpec||'尚未验收'},{label:'数字物品',children:item?<Button type="link" onClick={()=>leave(()=>onOpenItem(item.id))}>{item.item_uid}</Button>:'未关联'},{label:'芯片',children:chip?.chip_uid||'未关联'},{label:'配置核验',children:timeText(chip?.provisioned_at)},{label:'品牌发货',children:record.tracking||'未记录'},{label:'实际交付',children:record.receiptEvidence||'未记录'}]}/>
          <Text type="secondary">准备与实物交付事实不等于当前授权；取消/退款不自动释放发行序号。</Text>
        </Card></Col></Row>
        <Collapse items={[{key:'history',label:'查看本次办理历史',children:<Timeline items={record.history.map((h,i)=>({key:i,title:timeText(h.time),content:h.text}))}/>} ]}/>
      </div>}
    </Modal>
  </div>;
}
