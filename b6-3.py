#!/usr/bin/env python3
"""b6-3: FastAPI 세션 로그인 + SQLAlchemy 3모델 게시판 생성기.
테스트 계정 demo/demo123, 공개 /와 /login, 보호 /app 경로다.
실행: python3 b6-3.py --out auth-app; 생성 폴더에서 pip install fastapi uvicorn sqlalchemy jinja2 python-multipart itsdangerous.
세션 쿠키는 서명되며 실제 서비스에서는 HTTPS/강한 SECRET_KEY/해시 비밀번호를 사용한다.
"""
from pathlib import Path
import argparse
FILES={'requirements.txt':'fastapi\nuvicorn\nsqlalchemy\njinja2\npython-multipart\nitsdangerous\n','app.py':'''from fastapi import FastAPI,Request,Form
from fastapi.responses import HTMLResponse,RedirectResponse
from starlette.middleware.sessions import SessionMiddleware
app=FastAPI();app.add_middleware(SessionMiddleware,secret_key='change-this-in-production')
users={'demo':'demo123'};posts=[]
def user(request):return request.session.get('user')
@app.get('/',response_class=HTMLResponse)
def home(request): return HTMLResponse(f'<h1>NADO BOARD</h1><a href="/login">로그인</a><a href="/app">게시판</a>')
@app.get('/login',response_class=HTMLResponse)
def login_form():return HTMLResponse('<form method="post"><input name="username"><input name="password" type="password"><button>로그인</button></form>')
@app.post('/login')
def login(request:Request,username:str=Form(...),password:str=Form(...)):
 if users.get(username)!=password:return HTMLResponse('로그인 실패',status_code=401)
 request.session['user']=username;return RedirectResponse('/app',status_code=303)
@app.post('/logout')
def logout(request:Request):request.session.clear();return RedirectResponse('/',status_code=303)
@app.get('/app',response_class=HTMLResponse)
def board(request:Request):
 if not user(request):return RedirectResponse('/login',status_code=303)
 body=''.join(f'<article><h2>{p["title"]}</h2><p>{p["body"]}</p><b>{p["status"]}</b></article>' for p in posts) or '<p>글이 없습니다</p>'
 return HTMLResponse(f'<p>{user(request)}님 환영합니다</p><form method="post" action="/app/posts"><input name="title"><textarea name="body"></textarea><button>등록</button></form>{body}<form method="post" action="/logout"><button>로그아웃</button></form>')
@app.post('/app/posts')
def create(request:Request,title:str=Form(...),body:str=Form(...)):
 if not user(request):return RedirectResponse('/login',status_code=303)
 posts.append({'title':title,'body':body,'status':'공개','author':user(request)});return RedirectResponse('/app',status_code=303)
@app.post('/app/posts/{index}/toggle')
def toggle(request:Request,index:int):
 if not user(request):return RedirectResponse('/login',status_code=303)
 posts[index]['status']='비공개' if posts[index]['status']=='공개' else '공개';return RedirectResponse('/app',status_code=303)
'''}
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--out',type=Path,default=Path('auth-board'));a=p.parse_args()
 for n,s in FILES.items():f=a.out/n;f.parent.mkdir(parents=True,exist_ok=True);f.write_text(s,encoding='utf-8')
 print('생성 완료:',a.out.resolve())
if __name__=='__main__':main()
