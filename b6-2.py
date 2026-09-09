#!/usr/bin/env python3
## 쉬운 설명: 요청은 라우터, 규칙은 서비스, DB 읽기는 저장소가 담당한다.
"""b6-2: FastAPI + SQLAlchemy + Jinja2 메모 CRUD 프로젝트 생성기.
실행: python3 b6-2.py --out memo-app; cd memo-app; python3 -m venv .venv;
source .venv/bin/activate; pip install -r requirements.txt; uvicorn app:app --reload.
라우터/서비스/저장소/모델/템플릿을 분리하고 POST는 303 PRG로 처리한다."""
from pathlib import Path
import argparse

FILES = {
    "requirements.txt": "fastapi\nuvicorn\nsqlalchemy\njinja2\npython-multipart\n",
    "models.py": """from sqlalchemy.orm import DeclarativeBase,Mapped,mapped_column
from sqlalchemy import String,Text,DateTime,create_engine
from datetime import datetime
class Base(DeclarativeBase): pass
class Memo(Base):
    __tablename__='memos';id:Mapped[int]=mapped_column(primary_key=True);title:Mapped[str]=mapped_column(String(120));content:Mapped[str]=mapped_column(Text);created_at:Mapped[datetime]=mapped_column(DateTime,default=datetime.utcnow)
engine=create_engine('sqlite:///./database.db',connect_args={'check_same_thread':False});Base.metadata.create_all(engine)
""",
    "repositories.py": """from sqlalchemy.orm import Session
from models import Memo
class MemoRepository:
    def all(self,db): return db.query(Memo).order_by(Memo.id.desc()).all()
    def get(self,db,identifier): return db.get(Memo,identifier)
    def add(self,db,title,content): item=Memo(title=title,content=content);db.add(item);db.commit();db.refresh(item);return item
    def delete(self,db,item): db.delete(item);db.commit()
repo=MemoRepository()
""",
    "services.py": """from repositories import repo
class MemoService:
    def create(self,db,title,content):
        if not title.strip() or not content.strip(): raise ValueError('제목과 내용을 입력하세요')
        return repo.add(db,title.strip(),content.strip())
    def remove(self,db,item): repo.delete(db,item)
service=MemoService()
""",
    "app.py": """from fastapi import FastAPI,Request,Form,Depends
from fastapi.responses import HTMLResponse,RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from models import engine
from sqlalchemy.orm import sessionmaker
from repositories import repo
from services import service
app=FastAPI();templates=Jinja2Templates(directory='templates');SessionLocal=sessionmaker(bind=engine)
def db():
 s=SessionLocal()
 try: yield s
 finally:s.close()
@app.get('/',response_class=HTMLResponse)
def home(request:Request): return templates.TemplateResponse(request,'home.html',{})
@app.get('/memos',response_class=HTMLResponse)
def listing(request:Request,session:Session=Depends(db)): return templates.TemplateResponse(request,'list.html',{'memos':repo.all(session)})
@app.get('/memos/new',response_class=HTMLResponse)
def new(request:Request): return templates.TemplateResponse(request,'form.html',{})
@app.post('/memos',response_class=RedirectResponse,status_code=303)
def create(title:str=Form(...),content:str=Form(...),session:Session=Depends(db)): service.create(session,title,content);return '/memos'
@app.get('/memos/{identifier}',response_class=HTMLResponse)
def detail(request:Request,identifier:int,session:Session=Depends(db)):
 item=repo.get(session,identifier)
 if not item:return templates.TemplateResponse(request,'not_found.html',status_code=404)
 return templates.TemplateResponse(request,'detail.html',{'memo':item})
@app.post('/memos/{identifier}/delete',response_class=RedirectResponse,status_code=303)
def delete(identifier:int,session:Session=Depends(db)): item=repo.get(session,identifier);item and service.remove(session,item);return '/memos'
""",
    "templates/home.html": '<h1>나의 메모 앱</h1><p>메모를 등록하고 관리합니다.</p><a href="/memos">목록</a> <a href="/memos/new">새 메모</a>',
    "templates/list.html": '<h1>메모 목록</h1>{% for memo in memos %}<article><a href="/memos/{{memo.id}}"><h2>{{memo.title}}</h2></a><p>{{memo.content}}</p></article>{% else %}<p>메모가 없습니다.</p>{% endfor %}<a href="/memos/new">새 메모</a>',
    "templates/form.html": '<h1>새 메모</h1><form method="post" action="/memos"><label>제목<input name="title" required></label><label>내용<textarea name="content" required></textarea></label><button>저장</button></form>',
    "templates/detail.html": '<h1>{{memo.title}}</h1><p>{{memo.content}}</p><form method="post" action="/memos/{{memo.id}}/delete"><button>삭제</button></form><a href="/memos">목록</a>',
    "templates/not_found.html": '<h1>해당 데이터를 찾을 수 없습니다.</h1><a href="/memos">목록</a>',
}


# main: FastAPI CRUD 프로젝트 파일을 생성한다.
def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--out", type=Path, default=Path("memo-app"))
    a = p.parse_args()
    for n, s in FILES.items():
        f = a.out / n
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(s, encoding="utf-8")
    print("생성 완료:", a.out.resolve())


if __name__ == "__main__":
    main()
