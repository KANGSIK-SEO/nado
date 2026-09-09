#!/usr/bin/env python3
"""b6-1 | 정보를 깔끔하게 정리하는 디지털 서랍장 만들기
주제: 도서 대여. Python 3.10+ 내장 sqlite3만 사용, 백엔드 프레임워크 없음.
실행: python3 b6-1.py --out generated/b6-1
생성물: schema.sql, seed.sql, queries.sql, library.db, results/*.txt.
기존 DB를 덮어쓰지 않는다. 재실행은 새 --out 폴더를 사용한다.
category 1:N book, member 1:N rental, book 1:N rental.
회원/책/분류의 중복 정보를 대여 행에 복제하지 않아 수정 불일치를 방지한다.
SQLite는 PRAGMA foreign_keys=ON이 연결마다 필요하다.
15개 쿼리: 조회4, JOIN4, 집계3, 서브쿼리1, UPDATE1, DELETE1, INDEX1.
각 테이블 12행. 삭제 실습 후에도 rental 11행이 남는다.
LIMIT, PRAGMA, EXPLAIN QUERY PLAN은 여기서 선택한 SQLite 문법이다.
"""
import argparse
import sqlite3
from pathlib import Path

SCHEMA='''PRAGMA foreign_keys=ON;
CREATE TABLE category(id INTEGER PRIMARY KEY, name TEXT NOT NULL UNIQUE);
CREATE TABLE member(id INTEGER PRIMARY KEY, name TEXT NOT NULL, email TEXT NOT NULL UNIQUE);
CREATE TABLE book(id INTEGER PRIMARY KEY, title TEXT NOT NULL, category_id INTEGER NOT NULL REFERENCES category(id), price INTEGER NOT NULL CHECK(price>0));
CREATE TABLE rental(id INTEGER PRIMARY KEY, member_id INTEGER NOT NULL REFERENCES member(id), book_id INTEGER NOT NULL REFERENCES book(id), rented_at TEXT NOT NULL, returned_at TEXT, status TEXT NOT NULL CHECK(status IN ('borrowed','returned','overdue')));
'''
QUERIES=[
('01 가격이 15000원 이상인 책','SELECT * FROM book WHERE price>=15000;'),
('02 비싼 책 상위 다섯 권','SELECT * FROM book ORDER BY price DESC LIMIT 5;'),
('03 이름으로 회원 검색',"SELECT * FROM member WHERE name LIKE '%1%';"),
('04 반납하지 않은 기록 최신순',"SELECT * FROM rental WHERE returned_at IS NULL ORDER BY rented_at DESC;"),
('05 INNER JOIN 책과 분류','SELECT b.title,c.name FROM book b INNER JOIN category c ON c.id=b.category_id;'),
('06 INNER JOIN 회원별 대여 기록','SELECT m.name,r.rented_at FROM member m INNER JOIN rental r ON m.id=r.member_id;'),
('07 LEFT JOIN 대여하지 않은 회원도 포함','SELECT m.name,r.id FROM member m LEFT JOIN rental r ON m.id=r.member_id;'),
('08 세 테이블을 연결한 대여 상세','SELECT r.id,m.name,b.title,r.status FROM rental r JOIN member m ON m.id=r.member_id JOIN book b ON b.id=r.book_id;'),
('09 회원별 대여 횟수','SELECT member_id,COUNT(*) AS rental_count FROM rental GROUP BY member_id;'),
('10 분류별 도서 금액 합계','SELECT category_id,SUM(price) AS total FROM book GROUP BY category_id;'),
('11 분류별 평균 가격','SELECT category_id,AVG(price) AS average FROM book GROUP BY category_id;'),
('12 서브쿼리 평균보다 비싼 도서','SELECT title,price FROM book WHERE price>(SELECT AVG(price) FROM book);'),
('13 미반납 오래된 기록을 연체로 변경',"UPDATE rental SET status='overdue' WHERE returned_at IS NULL AND rented_at<'2026-09-05';"),
('14 반납 완료된 연습 기록 한 건 삭제',"DELETE FROM rental WHERE id=12 AND status='returned';"),
('15 대여일 범위 검색을 위한 인덱스: 전체 스캔 대신 범위 탐색','CREATE INDEX idx_rental_date ON rental(rented_at);'),
]

def seed_sql():
    lines=[]
    for i in range(1,13):
        lines.append(f"INSERT INTO category VALUES({i},'분류{i}');")
        lines.append(f"INSERT INTO member VALUES({i},'회원{i}','member{i}@example.test');")
        lines.append(f"INSERT INTO book VALUES({i},'도서{i}',{(i-1)//2+1},{10000+i*1000});")
    for i in range(1,13):
        returned="'2026-09-15'" if i%2==0 else 'NULL'
        status='returned' if i%2==0 else 'borrowed'
        lines.append(f"INSERT INTO rental VALUES({i},{(i-1)//2+1},{i},'2026-09-{i:02d}',{returned},'{status}');")
    return '\n'.join(lines)+'\n'

def main():
    parser=argparse.ArgumentParser(description=__doc__,formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--out',type=Path,default=Path('generated/b6-1'))
    target=parser.parse_args().out
    target.mkdir(parents=True,exist_ok=True)
    database=target/'library.db'
    if database.exists(): raise SystemExit('기존 DB 보존: 새 --out 폴더를 지정하세요')
    (target/'results').mkdir(exist_ok=True)
    for filename,text in [('schema.sql',SCHEMA),('seed.sql',seed_sql()),('queries.sql','\n\n'.join('-- '+title+'\n'+query for title,query in QUERIES))]:
        (target/filename).write_text(text,encoding='utf-8')
    with sqlite3.connect(database) as db:
        db.executescript(SCHEMA); db.executescript(seed_sql())
        for title,query in QUERIES:
            cursor=db.execute(query)
            if cursor.description:
                result=' | '.join(column[0] for column in cursor.description)+'\n'+'\n'.join(str(row) for row in cursor)
            elif query.startswith('CREATE INDEX'):
                result='인덱스 생성 완료\n'+str(db.execute("EXPLAIN QUERY PLAN SELECT * FROM rental WHERE rented_at>='2026-09-05'").fetchall())
            else:
                result=f'변경 행: {cursor.rowcount}\n'+str(db.execute('SELECT * FROM rental ORDER BY id').fetchall())
            report=title+'\n'+query+'\n'+result+'\n'
            print(report)
            (target/'results'/f'{title[:2]}.txt').write_text(report,encoding='utf-8')
        try:
            db.execute("INSERT INTO rental VALUES(999,999,1,'2026-09-01',NULL,'borrowed')")
        except sqlite3.IntegrityError as error:
            (target/'results'/'fk-check.txt').write_text('실제 FK 차단 확인: '+str(error)+'\n없는 회원 999를 먼저 등록하거나 기존 회원 ID를 사용해야 합니다.',encoding='utf-8')
    print('생성 완료:',target.resolve())
if __name__=='__main__': main()
