#!/usr/bin/env python3
"""b1-2 답안: React + Supabase 메모 SPA 생성기.
Supabase는 원격 PostgreSQL/Auth를 제공하는 백엔드 서비스다. 계정이 없으면
생성 후 README 대신 이 주석의 SQL을 Supabase SQL Editor에서 실행한다.
create table items(id uuid primary key default gen_random_uuid(), title text not null, content text not null, created_at timestamptz default now());
alter table items enable row level security; create policy public_demo on items for all using(true) with check(true);
`.env`에 VITE_SUPABASE_URL, VITE_SUPABASE_ANON_KEY를 넣고 npm install && npm run dev.
라우트 5개(/,/login,/items,/items/new,/items/:id), 컴포넌트와 hooks를 분리한다."""
from pathlib import Path
import argparse
FILES={
'package.json':'''{"scripts":{"dev":"vite","build":"vite build"},"dependencies":{"@supabase/supabase-js":"latest","@vitejs/plugin-react":"latest","vite":"latest","react":"latest","react-dom":"latest","react-router-dom":"latest"},"devDependencies":{}}''',
'.env.example':'VITE_SUPABASE_URL=\nVITE_SUPABASE_ANON_KEY=\n',
'index.html':'<div id="root"></div><script type="module" src="/src/main.jsx"></script>',
'src/lib/supabase.js':'''import { createClient } from '@supabase/supabase-js';
export const supabase=createClient(import.meta.env.VITE_SUPABASE_URL||'',import.meta.env.VITE_SUPABASE_ANON_KEY||'');''',
'src/hooks/useItems.js':'''import {useCallback,useEffect,useState} from 'react';import {supabase} from '../lib/supabase';
export function useItems(){const [items,setItems]=useState([]),[status,setStatus]=useState('loading'),[error,setError]=useState('');const load=useCallback(async()=>{setStatus('loading');const {data,error}=await supabase.from('items').select('*').order('created_at',{ascending:false});if(error){setError(error.message);setStatus('error')}else{setItems(data||[]);setStatus('ready')}},[]);useEffect(()=>{load()},[load]);return {items,status,error,reload:load}}''',
'src/main.jsx':'''import React,{useState} from 'react';import {createRoot} from 'react-dom/client';import {BrowserRouter,useNavigate,useParams,Routes,Route,Link} from 'react-router-dom';import {supabase} from './lib/supabase';import {useItems} from './hooks/useItems';import './style.css';
const Loading=()=> <p>로딩 중...</p>;const ErrorState=({message,retry})=><p>요청에 실패했습니다: {message} <button onClick={retry}>다시 시도</button></p>;const Empty=()=> <p>표시할 데이터가 없습니다.</p>;function Layout({children}){return <><nav><Link to="/">NADO NOTES</Link><Link to="/items">목록</Link><Link to="/items/new">새 메모</Link></nav><main>{children}</main></>}function List(){const {items,status,error,reload}=useItems();if(status==='loading')return <Loading/>;if(status==='error')return <ErrorState message={error} retry={reload}/>;return <>{!items.length?<Empty/>:items.map(i=><article key={i.id}><Link to={'/items/'+i.id}><h2>{i.title}</h2></Link><p>{i.content}</p></article>)}</>}function Form(){const nav=useNavigate(),[form,setForm]=useState({title:'',content:''}),[busy,setBusy]=useState(false),[error,setError]=useState('');async function submit(e){e.preventDefault();if(!form.title.trim()||!form.content.trim()){setError('제목과 내용을 입력하세요');return}setBusy(true);const {error}=await supabase.from('items').insert(form);if(error)setError(error.message);else nav('/items');setBusy(false)}return <form onSubmit={submit}><input placeholder="제목" value={form.title} onChange={e=>setForm({...form,title:e.target.value})}/><textarea placeholder="내용" value={form.content} onChange={e=>setForm({...form,content:e.target.value})}/><p>{error}</p><button disabled={busy}>{busy?'저장 중...':'저장'}</button></form>}function Detail(){const {id}=useParams(),[item,setItem]=useState(null);React.useEffect(()=>{supabase.from('items').select('*').eq('id',id).single().then(({data})=>setItem(data))},[id]);if(!item)return <Loading/>;return <article><h1>{item.title}</h1><p>{item.content}</p></article>}function App(){return <BrowserRouter><Layout><Routes><Route path="/" element={<h1>나의 메모 서비스<br/><Link to="/items">메모 보기</Link></h1>}/><Route path="/login" element={<p>로그인 화면</p>}/><Route path="/items" element={<List/>}/><Route path="/items/new" element={<Form/>}/><Route path="/items/:id" element={<Detail/>}/><Route path="*" element={<p>Not Found</p>}/></Routes></Layout></BrowserRouter>}createRoot(document.getElementById('root')).render(<App/>);''',
'src/style.css':'body{font:16px system-ui;max-width:900px;margin:auto;padding:2rem}nav{display:flex;gap:1rem;margin-bottom:3rem}article{border:1px solid #ddd;padding:1rem;margin:1rem 0}form{display:grid;gap:1rem;max-width:600px}input,textarea{font:inherit;padding:.7rem}textarea{min-height:150px}'
}
def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--out',type=Path,default=Path('react-notes'));a=p.parse_args()
    for n,s in FILES.items():f=a.out/n;f.parent.mkdir(parents=True,exist_ok=True);f.write_text(s,encoding='utf-8')
    print('생성 완료:',a.out.resolve())
if __name__=='__main__':main()
