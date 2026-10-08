import {useState} from 'react';
import {useMutation,useQuery} from '@tanstack/react-query';
import {Badge,Button,Card,Col,Descriptions,Drawer,Input,Layout,List,Menu,Progress,Row,Space,Steps,Table,Tag,Typography,message} from 'antd';
import {Activity,Bot,Database,FileSearch,GitCompareArrows,LayoutDashboard,Search,ShieldCheck,UserCheck} from 'lucide-react';
import {api,AssetTable,Dashboard,SearchResult} from './api';

const {Header,Sider,Content}=Layout;

function Overview(){
  const {data}=useQuery({queryKey:['dashboard'],queryFn:()=>api.get<Dashboard>('/dashboard').then(r=>r.data),refetchInterval:5000});
  const cards=[['数据源',data?.sources,Database],['数据表',data?.tables,LayoutDashboard],['字段资产',data?.columns,FileSearch],['待审核',data?.pending_reviews,Activity],['敏感字段',data?.sensitive_columns,ShieldCheck]];
  return <><Row gutter={[16,16]}>{cards.map(([name,value,Icon]:any)=><Col xs={12} lg={4} flex="1" key={name}><Card><Space><Icon size={22}/><div><Typography.Text type="secondary">{name}</Typography.Text><Typography.Title level={2}>{value??'-'}</Typography.Title></div></Space></Card></Col>)}</Row><Card title="Supervisor 多智能体协作链路" className="block"><Steps responsive items={['Metadata Agent','Governance Agent','Relation Agent','Quality Agent'].map(title=>({title,status:'finish'}))}/><div className="pipeline">Supervisor依据结构化状态调度专业Agent；质量不达标时有限重试，仍不达标则进入人工审核。</div></Card></>
}

function Catalog(){
  const [selected,setSelected]=useState<any>();
  const {data=[]}=useQuery({queryKey:['tables'],queryFn:()=>api.get<AssetTable[]>('/tables').then(r=>r.data)});
  const open=async(id:number)=>setSelected((await api.get('/tables/'+id)).data);
  return <><Table rowKey="id" dataSource={data} onRow={r=>({onClick:()=>open(r.id)})} columns={[{title:'资产名称',dataIndex:'name'},{title:'主题域',dataIndex:'domain',render:v=><Tag color="green">{v}</Tag>},{title:'AI注释',dataIndex:'comment'},{title:'字段数',dataIndex:'column_count'},{title:'置信度',dataIndex:'confidence',render:v=><Progress percent={Math.round(v*100)} size="small"/>}]}/><Drawer open={!!selected} width={850} onClose={()=>setSelected(undefined)} title={selected?.name}>{selected&&<><Descriptions items={[{key:'d',label:'主题域',children:selected.domain},{key:'c',label:'描述',children:selected.comment}]}/><Table rowKey="id" size="small" dataSource={selected.columns} columns={[{title:'字段',dataIndex:'name'},{title:'业务名称',dataIndex:'business_name'},{title:'类型',dataIndex:'type'},{title:'敏感等级',dataIndex:'sensitivity',render:v=><Tag color={v==='L1-公开'?'green':'orange'}>{v}</Tag>},{title:'置信度',dataIndex:'confidence',render:v=>Math.round(v*100)+'%'}]}/></>}</Drawer></>
}

function SemanticSearch(){
  const [query,setQuery]=useState('哪些表保存了客户手机号？');
  const mutation=useMutation({mutationFn:()=>api.post<{results:SearchResult[]}>('/search',{query,limit:15}).then(r=>r.data.results)});
  return <Card title="关键词 + pgvector + RRF 混合检索"><Space.Compact block><Input value={query} onChange={e=>setQuery(e.target.value)} onPressEnter={()=>mutation.mutate()}/><Button type="primary" icon={<Search size={16}/>} onClick={()=>mutation.mutate()} loading={mutation.isPending}>检索</Button></Space.Compact><List className="block" dataSource={mutation.data??[]} renderItem={r=><List.Item><List.Item.Meta title={<Space><Typography.Text code>{r.asset}</Typography.Text><Tag>{r.domain}</Tag></Space>} description={<>{r.business_name} · {r.description}<br/><Typography.Text type="secondary">{r.reason} · RRF {r.retrieval_score}</Typography.Text></>}/></List.Item>}/></Card>
}

function Sources(){
  const q=useQuery({queryKey:['sources'],queryFn:()=>api.get('/sources').then(r=>r.data)});
  const jobs=useQuery({queryKey:['jobs'],queryFn:()=>api.get('/jobs').then(r=>r.data),refetchInterval:2000});
  const scan=async(id:number)=>{await api.post(`/sources/${id}/scan`);message.success('多智能体盘点任务已提交');jobs.refetch()};
  return <><Card title="数据源"><Table rowKey="id" dataSource={q.data??[]} columns={[{title:'名称',dataIndex:'name'},{title:'类型',dataIndex:'kind'},{title:'连接地址',dataIndex:'url'},{title:'操作',render:(_,r:any)=><Button type="primary" onClick={()=>scan(r.id)}>启动盘点</Button>}]}/></Card><Card title="Supervisor任务" className="block"><Table rowKey="id" dataSource={jobs.data??[]} columns={[{title:'任务',dataIndex:'id'},{title:'状态',dataIndex:'status',render:v=><Badge status={v.startsWith('completed')?'success':v==='failed'?'error':'processing'} text={v}/>},{title:'当前Agent',dataIndex:'stage'},{title:'工作流',dataIndex:['stats','workflow']}]}/></Card></>
}

function AgentTrace(){
  const jobs=useQuery({queryKey:['jobs-for-trace'],queryFn:()=>api.get('/jobs').then(r=>r.data)});
  const latest=jobs.data?.[0]?.id;
  const runs=useQuery({queryKey:['agent-runs',latest],queryFn:()=>api.get(`/jobs/${latest}/agents`).then(r=>r.data),enabled:!!latest});
  return <Card title={`Agent执行轨迹${latest?' · Job '+latest:''}`}><Table rowKey="id" dataSource={runs.data??[]} columns={[{title:'Agent',dataIndex:'agent_name',render:v=><Tag color="blue">{v}</Tag>},{title:'尝试',dataIndex:'attempt'},{title:'状态',dataIndex:'status',render:v=><Badge status={v==='completed'?'success':'error'} text={v}/>},{title:'耗时(ms)',dataIndex:['metrics','duration_ms']},{title:'输出摘要',dataIndex:'output',render:v=><Typography.Text ellipsis style={{maxWidth:440}}>{JSON.stringify(v)}</Typography.Text>}]}/></Card>
}

function Reviews(){
  const reviews=useQuery({queryKey:['reviews'],queryFn:()=>api.get('/reviews').then(r=>r.data)});
  return <Card title="Human-in-the-loop 审核队列"><Table rowKey="id" dataSource={reviews.data??[]} columns={[{title:'资产',dataIndex:'asset'},{title:'原因',dataIndex:'reason'},{title:'优先级',dataIndex:'priority',render:v=><Tag color={v==='high'?'red':'orange'}>{v}</Tag>},{title:'AI置信度',dataIndex:['ai_snapshot','confidence'],render:v=>Math.round((v??0)*100)+'%'},{title:'状态',dataIndex:'status'}]}/></Card>
}

export default function App(){
  const [page,setPage]=useState('overview');
  const pages:any={overview:<Overview/>,sources:<Sources/>,agents:<AgentTrace/>,reviews:<Reviews/>,catalog:<Catalog/>,search:<SemanticSearch/>,changes:<Card title="结构变更"><Typography.Text>字段级增量Diff可通过 /api/changes 查询。</Typography.Text></Card>};
  const items=[{key:'overview',icon:<LayoutDashboard size={16}/>,label:'资产总览'},{key:'sources',icon:<Database size={16}/>,label:'数据源与任务'},{key:'agents',icon:<Bot size={16}/>,label:'Agent执行轨迹'},{key:'reviews',icon:<UserCheck size={16}/>,label:'人工审核'},{key:'catalog',icon:<FileSearch size={16}/>,label:'资产目录'},{key:'search',icon:<Search size={16}/>,label:'语义检索'},{key:'changes',icon:<GitCompareArrows size={16}/>,label:'结构变更'}];
  return <Layout className="shell"><Sider width={245} theme="dark"><div className="brand">⚡ ChargeMeta<small>新能源数据资产多智能体</small></div><Menu theme="dark" selectedKeys={[page]} onClick={e=>setPage(e.key)} items={items}/></Sider><Layout><Header className="header"><Typography.Title level={4}>ChargeMeta Multi-Agent Console</Typography.Title><Tag color="green">Supervisor · 4 Agents · HITL</Tag></Header><Content className="content">{pages[page]}</Content></Layout></Layout>
}
