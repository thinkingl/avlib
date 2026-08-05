import sqlite3
import json
from datetime import datetime, timezone
from config import Config

def utc_now_str():
    """当前UTC时间，格式与SQLite CURRENT_TIMESTAMP一致"""
    return datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')

class Database:
    def __init__(self, db_path=None):
        self.db_path = db_path or Config.DATABASE_PATH
        self.init_db()

    def get_connection(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def init_db(self):
        conn = self.get_connection()
        cursor = conn.cursor()

        # 创建AV信息表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS av_info (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                av_id TEXT UNIQUE NOT NULL,
                title TEXT,
                studio TEXT,
                publisher TEXT,
                series TEXT,
                release_date TEXT,
                duration TEXT,
                director TEXT,
                actresses TEXT,
                genres TEXT,
                cover_url TEXT,
                cover_path TEXT,
                cover_data BLOB,
                cover_mime TEXT DEFAULT 'image/jpeg',
                source TEXT,
                rating TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # 检查并添加缺失的列
        self._add_missing_columns(cursor, 'av_info', {
            'cover_data': 'BLOB',
            'cover_mime': 'TEXT DEFAULT "image/jpeg"'
        })

        # 创建搜索历史表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS search_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                av_id TEXT NOT NULL,
                search_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                source TEXT,
                success BOOLEAN DEFAULT 1
            )
        ''')

        # 创建DokuWiki提交记录表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS dokuwiki_submissions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                av_id TEXT NOT NULL,
                wiki_page TEXT,
                submit_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                status TEXT DEFAULT 'pending'
            )
        ''')

        conn.commit()
        conn.close()

    def _add_missing_columns(self, cursor, table_name, columns):
        """添加缺失的列到表中"""
        # 获取现有列
        cursor.execute(f"PRAGMA table_info({table_name})")
        existing_columns = {row[1] for row in cursor.fetchall()}

        # 添加缺失的列
        for col_name, col_type in columns.items():
            if col_name not in existing_columns:
                try:
                    cursor.execute(f"ALTER TABLE {table_name} ADD COLUMN {col_name} {col_type}")
                    print(f"Added column {col_name} to {table_name}")
                except Exception as e:
                    print(f"Error adding column {col_name}: {e}")

    def insert_av_info(self, av_data):
        conn = self.get_connection()
        cursor = conn.cursor()

        try:
            # 处理列表类型的数据
            actresses = av_data.get('actresses', [])
            genres = av_data.get('genres', [])

            # 如果已经是字符串，直接使用；否则转为JSON
            if isinstance(actresses, str):
                # 验证是否为有效JSON
                try:
                    json.loads(actresses)
                except:
                    actresses = json.dumps([actresses], ensure_ascii=False)
            else:
                actresses = json.dumps(actresses, ensure_ascii=False)

            if isinstance(genres, str):
                try:
                    json.loads(genres)
                except:
                    genres = json.dumps([genres], ensure_ascii=False)
            else:
                genres = json.dumps(genres, ensure_ascii=False)

            cursor.execute('''
                INSERT OR REPLACE INTO av_info 
                (av_id, title, studio, publisher, series, release_date, 
                 duration, director, actresses, genres, cover_url, cover_path, cover_data, cover_mime, source, rating, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                av_data['av_id'],
                av_data.get('title'),
                av_data.get('studio'),
                av_data.get('publisher'),
                av_data.get('series'),
                av_data.get('release_date'),
                av_data.get('duration'),
                av_data.get('director'),
                actresses,
                genres,
                av_data.get('cover_url'),
                av_data.get('cover_path'),
                av_data.get('cover_data'),
                av_data.get('cover_mime', 'image/jpeg'),
                av_data.get('source'),
                av_data.get('rating'),
                utc_now_str()
            ))

            conn.commit()
            return True
        except Exception as e:
            print(f"Error inserting AV info: {e}")
            return False
        finally:
            conn.close()

    def get_av_info(self, av_id):
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute('SELECT * FROM av_info WHERE av_id = ?', (av_id,))
        row = cursor.fetchone()
        conn.close()

        if row:
            return dict(row)
        return None

    def get_all_av_info(self, limit=100, offset=0):
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute('SELECT * FROM av_info ORDER BY updated_at DESC LIMIT ? OFFSET ?', (limit, offset))
        rows = cursor.fetchall()
        conn.close()

        return [dict(row) for row in rows]

    def add_search_history(self, av_id, source, success=True):
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute('''
            INSERT INTO search_history (av_id, source, success)
            VALUES (?, ?, ?)
        ''', (av_id, source, success))

        conn.commit()
        conn.close()

    def add_dokuwiki_submission(self, av_id, wiki_page, status='pending'):
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute('''
            INSERT INTO dokuwiki_submissions (av_id, wiki_page, status)
            VALUES (?, ?, ?)
        ''', (av_id, wiki_page, status))

        conn.commit()
        conn.close()

    def update_dokuwiki_submission_status(self, av_id, status):
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute('''
            UPDATE dokuwiki_submissions 
            SET status = ? 
            WHERE av_id = ? AND id = (
                SELECT id FROM dokuwiki_submissions 
                WHERE av_id = ? 
                ORDER BY submit_time DESC 
                LIMIT 1
            )
        ''', (status, av_id, av_id))

        conn.commit()
        conn.close()

    def get_av_count(self):
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute('SELECT COUNT(*) FROM av_info')
        count = cursor.fetchone()[0]
        conn.close()

        return count

    def get_cover_data(self, av_id):
        """获取封面图片二进制数据"""
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute('SELECT cover_data, cover_mime FROM av_info WHERE av_id = ?', (av_id,))
        row = cursor.fetchone()
        conn.close()

        if row and row['cover_data']:
            return row['cover_data'], row['cover_mime']
        return None, None

    def delete_av_info(self, av_id):
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute('DELETE FROM av_info WHERE av_id = ?', (av_id,))
        conn.commit()
        conn.close()
