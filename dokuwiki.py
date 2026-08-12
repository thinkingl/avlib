import requests
import base64
import os
import xmlrpc.client
from http.cookiejar import CookieJar
from urllib.request import build_opener, HTTPCookieProcessor, Request
from config import Config

def get_cover_filename(av_info, ext='jpg'):
    """生成封面文件名：发行日期-番号.jpg（如 2024-12-11-hnvr-140.jpg）"""
    av_id = (av_info.get('av_id') or '').lower()
    release_date = av_info.get('release_date') or ''

    date_part = ''
    if len(release_date) >= 10:
        # 取完整日期 YYYY-MM-DD，容忍带时间后缀等格式
        date_part = release_date[:10]
    elif release_date:
        date_part = release_date

    if date_part:
        return f"{date_part}-{av_id}.{ext}"
    return f"{av_id}.{ext}"


class _CookieTransport(xmlrpc.client.Transport):
    """带会话cookie的XML-RPC传输层

    新版DokuWiki（2023-04-04+）改用会话认证：dokuwiki.login 建立PHP会话，
    后续XML-RPC调用必须携带会话cookie，不再使用token参数。
    """

    def __init__(self, use_https=False, timeout=30):
        self._use_https = use_https
        self._timeout = timeout
        self.verbose = 0
        self.cookie_jar = CookieJar()
        self.opener = build_opener(HTTPCookieProcessor(self.cookie_jar))
        super().__init__()

    def request(self, host, handler, request_body, verbose=False):
        scheme = 'https' if self._use_https else 'http'
        req = Request(
            f'{scheme}://{host}{handler}',
            data=request_body,
            headers={'Content-Type': 'text/xml'},
        )
        resp = self.opener.open(req, timeout=self._timeout)
        return self.parse_response(resp)


class DokuWikiClient:
    def __init__(self, url=None, username=None, password=None, api_token=None):
        self.url = url or Config.DOKUWIKI_URL
        self.username = username or Config.DOKUWIKI_USERNAME
        self.password = password or Config.DOKUWIKI_PASSWORD
        self.api_token = api_token or Config.DOKUWIKI_API_TOKEN
        self.api_url = f"{self.url}/lib/exe/ajax.php"
        self.xmlrpc_url = f"{self.url}/lib/exe/xmlrpc.php"

    def _call(self, method, *args):
        """登录并调用XML-RPC方法（新版DokuWiki：会话cookie认证）"""
        if self.api_token:
            print("Warning: api_token 已不被新版DokuWiki支持，改用账号密码登录")
        transport = _CookieTransport(use_https=self.url.startswith('https://'))
        proxy = xmlrpc.client.ServerProxy(f"{self.url}/lib/exe/xmlrpc.php", transport=transport)
        ok = proxy.dokuwiki.login(self.username, self.password)
        if not ok:
            raise RuntimeError('Authentication failed')
        return getattr(proxy, method)(*args)

    def test_connection(self):
        """测试连接（验证XML-RPC API可用且账号密码正确）"""
        try:
            return bool(self._call('dokuwiki.getTitle'))
        except Exception as e:
            print(f"Connection test failed: {e}")
            return False

    def create_page(self, page_id, content, summary=None):
        """创建或更新Wiki页面"""
        try:
            result = self._call('wiki.putPage', page_id, content, {
                'sum': summary or f'Created page {page_id}',
                'minor': False
            })
            return result, "Success" if result else "Failed"

        except Exception as e:
            print(f"Error creating page: {e}")
            return False, str(e)

    def upload_media(self, page_id, file_path, overwrite=True):
        """上传媒体文件"""
        try:
            with open(file_path, 'rb') as f:
                file_data = xmlrpc.client.Binary(f.read())
            result = self._call('wiki.putAttachment', page_id, file_data, {
                'ow': overwrite
            })
            return result, "Success" if result else "Failed"

        except Exception as e:
            print(f"Error uploading media: {e}")
            return False, str(e)

    def upload_media_data(self, page_id, data, overwrite=True):
        """上传媒体数据（二进制）"""
        try:
            file_data = xmlrpc.client.Binary(data)
            result = self._call('wiki.putAttachment', page_id, file_data, {
                'ow': overwrite
            })
            return result, "Success" if result else "Failed"

        except Exception as e:
            print(f"Error uploading media data: {e}")
            return False, str(e)

    def page_exists(self, page_id):
        """检查页面是否存在"""
        try:
            result = self._call('wiki.getPageInfo', page_id)
            return bool(result)
        except Exception as e:
            print(f"Error checking page: {e}")
            return False

    def get_page(self, page_id):
        """获取页面内容"""
        try:
            return self._call('wiki.getPage', page_id)
        except Exception as e:
            print(f"Error getting page: {e}")
            return None

    def format_av_page(self, av_info):
        """将AV信息格式化为Wiki页面内容"""
        import json

        av_id = av_info.get('av_id', '')
        title = av_info.get('title', '')
        release_date = av_info.get('release_date', '')
        duration = av_info.get('duration', '')
        director = av_info.get('director', '')
        studio = av_info.get('studio', '')
        publisher = av_info.get('publisher', '')
        series = av_info.get('series', '')

        # 处理演员
        actresses = av_info.get('actresses', [])
        if isinstance(actresses, str):
            try:
                actresses = json.loads(actresses)
            except:
                actresses = [actresses] if actresses else []

        # 处理类型
        genres = av_info.get('genres', [])
        if isinstance(genres, str):
            try:
                genres = json.loads(genres)
            except:
                genres = [genres] if genres else []

        # 构建页面内容
        lines = []
        tab = '\t'

        # 标题行：番号 + 标题
        lines.append(f"====== {av_id} {title} ======")
        lines.append("")

        # 基本信息
        lines.append(f"识别码:{tab}{av_id}  \\\\")
        if release_date:
            lines.append(f"发行日期:{tab}{release_date}  \\\\")
        if duration:
            lines.append(f"长度:{tab}{duration}  \\\\")
        if director:
            lines.append(f"导演:{tab}{director}  \\\\")
        if studio:
            lines.append(f"制作商:{tab}{studio}  \\\\")
        if publisher:
            lines.append(f"发行商:{tab}{publisher}  \\\\")
        if series:
            lines.append(f"系列:{tab}{series}  \\\\")

        # 类别
        if genres:
            genres_str = " ".join(genres)
            lines.append(f"类别:{tab}{genres_str}  \\\\")

        # 演员（始终输出该字段，未收录时显示-）
        actresses_str = " ".join(actresses) if actresses else "-"
        lines.append(f"演员:{tab}{actresses_str}  \\\\")

        # 评论（多行评论转为DokuWiki换行，始终输出该字段）
        comment = (av_info.get('comment') or '').strip()
        if comment:
            comment_str = comment.replace('\n', '  \\\\')
            lines.append(f"评论:{tab}{comment_str}  \\\\")
        else:
            lines.append(f"评论:{tab}-  \\\\")

        lines.append("")

        # 封面图片 - 使用日期-番号格式
        img_filename = get_cover_filename(av_info)

        lines.append(f"{{{{:av:{img_filename}|}}}}")

        return "\n".join(lines)

    def submit_av_info(self, av_info, namespace='av'):
        """提交AV信息到DokuWiki"""
        av_id = av_info.get('av_id', '')
        page_id = f"{namespace}:{av_id}"

        # 格式化页面内容
        page_content = self.format_av_page(av_info)

        # 创建页面
        success, message = self.create_page(page_id, page_content)

        if not success:
            return False, f"Failed to create page: {message}"

        # 上传封面图片（优先使用数据库中的二进制数据）
        cover_data = av_info.get('cover_data')
        if cover_data:
            # 生成图片文件名：日期-番号.jpg
            img_filename = get_cover_filename(av_info)

            media_id = f"{namespace}:{img_filename}"
            success, message = self.upload_media_data(media_id, cover_data)
            if not success:
                print(f"Warning: Failed to upload cover image data: {message}")
        else:
            # 兼容旧方式：从文件路径上传
            cover_path = av_info.get('cover_path')
            if cover_path and os.path.exists(cover_path):
                img_filename = get_cover_filename(av_info)

                media_id = f"{namespace}:{img_filename}"
                success, message = self.upload_media(media_id, cover_path)
                if not success:
                    print(f"Warning: Failed to upload cover image: {message}")

        return True, "Success"
