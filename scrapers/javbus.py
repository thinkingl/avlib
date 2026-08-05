import re
from bs4 import BeautifulSoup
from .base import BaseScraper

class JavBusScraper(BaseScraper):
    def __init__(self):
        super().__init__()
        self.base_url = 'https://www.javbus.com'
        self.logger.info(f"JavBus base_url: {self.base_url}")

    def get_source_name(self):
        return 'javbus'

    def search(self, av_id):
        """从JavBus搜索番号信息"""
        self.logger.info(f"[JavBus] 开始搜索: {av_id}")
        try:
            search_url = f"{self.base_url}/{av_id}"
            self.logger.info(f"[JavBus] 请求URL: {search_url}")

            response = self.make_request(search_url)

            if not response:
                self.logger.warning(f"[JavBus] 请求失败，无响应")
                return None

            self.logger.info(f"[JavBus] 响应URL: {response.url}")
            self.logger.debug(f"[JavBus] 响应内容长度: {len(response.text)}")

            soup = BeautifulSoup(response.text, 'html.parser')

            # 检查是否被重定向到年龄验证页
            if 'driver-verify' in response.url or 'verify' in response.url:
                self.logger.warning(f"[JavBus] 被重定向到年龄验证页: {response.url}")
                return None

            # 检查是否找到结果
            if '404' in response.url:
                self.logger.warning(f"[JavBus] 页面返回404")
                return None

            alert = soup.find('div', class_='alert-warning')
            if alert:
                self.logger.warning(f"[JavBus] 页面提示警告: {alert.text.strip()}")
                return None

            # 提取信息
            av_info = {
                'av_id': av_id,
                'source': self.get_source_name()
            }

            # 获取标题
            title_tag = soup.find('h3')
            if title_tag:
                av_info['title'] = self.clean_text(title_tag.text)
                self.logger.info(f"[JavBus] 标题: {av_info['title']}")
            else:
                self.logger.warning(f"[JavBus] 未找到标题")

            # 获取封面图片
            cover_img = soup.find('a', class_='bigImage')
            if cover_img:
                img_url = cover_img.get('href')
                if img_url:
                    av_info['cover_url'] = f"{self.base_url}{img_url}" if img_url.startswith('/') else img_url
                    self.logger.info(f"[JavBus] 封面URL: {av_info['cover_url']}")
            else:
                self.logger.warning(f"[JavBus] 未找到封面图片")

            # 获取详细信息
            info_section = soup.find('div', class_='col-md-3 info')
            if info_section:
                self.logger.debug(f"[JavBus] 找到信息区域")
                rows = info_section.find_all('p')
                for row in rows:
                    text = row.text.strip()

                    if '識別碼' in text or '识别码' in text:
                        span = row.find('span', class_='header')
                        if span:
                            code = span.find_next_sibling(text=True)
                            code = code.strip() if code else ''
                            # 解析失败时保留搜索番号，避免覆盖为空
                            av_info['av_id'] = code or av_id

                    if '發行日期' in text or '发行日期' in text:
                        span = row.find('span', class_='header')
                        if span:
                            date_text = span.find_next_sibling(text=True)
                            if date_text:
                                av_info['release_date'] = date_text.strip()

                    if '長度' in text or '长度' in text:
                        span = row.find('span', class_='header')
                        if span:
                            duration_text = span.find_next_sibling(text=True)
                            if duration_text:
                                av_info['duration'] = duration_text.strip()

                    if '導演' in text or '导演' in text:
                        span = row.find('span', class_='header')
                        if span:
                            director_link = span.find_next('a')
                            if director_link:
                                av_info['director'] = self.clean_text(director_link.text)

                    if '製作商' in text or '制作商' in text:
                        span = row.find('span', class_='header')
                        if span:
                            studio_link = span.find_next('a')
                            if studio_link:
                                av_info['studio'] = self.clean_text(studio_link.text)

                    if '發行商' in text or '发行商' in text:
                        span = row.find('span', class_='header')
                        if span:
                            publisher_link = span.find_next('a')
                            if publisher_link:
                                av_info['publisher'] = self.clean_text(publisher_link.text)

                    if '系列' in text:
                        span = row.find('span', class_='header')
                        if span:
                            series_link = span.find_next('a')
                            if series_link:
                                av_info['series'] = self.clean_text(series_link.text)
            else:
                self.logger.warning(f"[JavBus] 未找到信息区域")

            # 获取演员
            actresses = []
            star_section = soup.find('div', id='star-list')
            if star_section:
                for star in star_section.find_all('a'):
                    actress_name = self.clean_text(star.text)
                    if actress_name and actress_name != '...':
                        actresses.append(actress_name)
            av_info['actresses'] = actresses
            self.logger.info(f"[JavBus] 演员: {actresses}")

            # 获取类型
            genres = []
            genre_section = soup.find('span', class_='genre')
            if genre_section:
                for genre in genre_section.find_all('a'):
                    genre_name = self.clean_text(genre.text)
                    if genre_name:
                        genres.append(genre_name)
            av_info['genres'] = genres
            self.logger.info(f"[JavBus] 类型: {genres}")

            self.logger.info(f"[JavBus] 搜索成功: {av_id}")
            return av_info

        except Exception as e:
            self.logger.error(f"[JavBus] 搜索异常: {e}", exc_info=True)
            return None
