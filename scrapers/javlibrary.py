import re
from bs4 import BeautifulSoup
from .base import BaseScraper

class JavLibraryScraper(BaseScraper):
    def __init__(self):
        super().__init__()
        self.base_url = 'https://www.javlibrary.com/cn'
        self.logger.info(f"JavLibrary base_url: {self.base_url}")

    def get_source_name(self):
        return 'javlibrary'

    def search(self, av_id):
        """从JAV Library搜索番号信息"""
        self.logger.info(f"[JavLibrary] 开始搜索: {av_id}")
        try:
            search_url = f"{self.base_url}/vl_searchbyid.php"
            params = {'keyword': av_id}
            self.logger.info(f"[JavLibrary] 搜索URL: {search_url}, 参数: {params}")

            response = self.make_request(search_url, params=params)

            if not response:
                self.logger.warning(f"[JavLibrary] 搜索请求失败")
                return None

            self.logger.info(f"[JavLibrary] 响应URL: {response.url}")
            soup = BeautifulSoup(response.text, 'html.parser')

            # 检查是否直接跳转到详情页
            if 'vl_searchbyid' not in response.url:
                self.logger.info(f"[JavLibrary] 直接跳转到详情页")
                return self.parse_detail_page(soup, av_id)

            # 搜索结果页，查找匹配项
            video_items = soup.find_all('div', class_='video')
            self.logger.info(f"[JavLibrary] 找到 {len(video_items)} 个结果")

            for item in video_items:
                link = item.find('a')
                if link:
                    href = link.get('href', '')
                    if av_id.upper() in href.upper():
                        self.logger.info(f"[JavLibrary] 找到匹配链接: {href}")
                        detail_url = f"{self.base_url}/{href}" if not href.startswith('http') else href
                        detail_response = self.make_request(detail_url)

                        if detail_response:
                            detail_soup = BeautifulSoup(detail_response.text, 'html.parser')
                            return self.parse_detail_page(detail_soup, av_id)

            self.logger.warning(f"[JavLibrary] 未找到匹配结果")
            return None

        except Exception as e:
            self.logger.error(f"[JavLibrary] 搜索异常: {e}", exc_info=True)
            return None

    def parse_detail_page(self, soup, av_id):
        """解析详情页"""
        self.logger.info(f"[JavLibrary] 解析详情页: {av_id}")

        av_info = {
            'av_id': av_id,
            'source': self.get_source_name()
        }

        # 获取标题
        title_tag = soup.find('h3', class_='post-title')
        if title_tag:
            av_info['title'] = self.clean_text(title_tag.text)
            self.logger.info(f"[JavLibrary] 标题: {av_info['title']}")
        else:
            self.logger.warning(f"[JavLibrary] 未找到标题")

        # 获取封面图片
        cover_img = soup.find('img', id='video_jacket_img')
        if cover_img:
            av_info['cover_url'] = cover_img.get('src', '')
            self.logger.info(f"[JavLibrary] 封面URL: {av_info['cover_url']}")
        else:
            self.logger.warning(f"[JavLibrary] 未找到封面")

        # 获取详细信息
        info_table = soup.find('table', id='video_jacket_info')
        if info_table:
            rows = info_table.find_all('tr')
            self.logger.debug(f"[JavLibrary] 找到 {len(rows)} 行信息")

            for row in rows:
                header = row.find('td', class_='header')
                value = row.find('td', class_='text')

                if not header or not value:
                    continue

                header_text = header.text.strip()
                value_text = value.text.strip()

                if '识别码' in header_text:
                    av_info['av_id'] = value_text
                elif '发行日期' in header_text:
                    av_info['release_date'] = value_text
                elif '长度' in header_text:
                    av_info['duration'] = value_text
                elif '导演' in header_text:
                    director_link = value.find('a')
                    if director_link:
                        av_info['director'] = self.clean_text(director_link.text)
                    else:
                        av_info['director'] = value_text
                elif '制作商' in header_text:
                    studio_link = value.find('a')
                    if studio_link:
                        av_info['studio'] = self.clean_text(studio_link.text)
                elif '发行商' in header_text:
                    publisher_link = value.find('a')
                    if publisher_link:
                        av_info['publisher'] = self.clean_text(publisher_link.text)
                elif '系列' in header_text:
                    series_link = value.find('a')
                    if series_link:
                        av_info['series'] = self.clean_text(series_link.text)
                elif '评分' in header_text:
                    av_info['rating'] = value_text
        else:
            self.logger.warning(f"[JavLibrary] 未找到信息表格")

        # 获取演员
        actresses = []
        cast_section = soup.find('div', id='video_cast')
        if cast_section:
            for link in cast_section.find_all('a'):
                actress_name = self.clean_text(link.text)
                if actress_name and actress_name != '...':
                    actresses.append(actress_name)
        av_info['actresses'] = actresses
        self.logger.info(f"[JavLibrary] 演员: {actresses}")

        # 获取类型
        genres = []
        genre_section = soup.find('div', id='video_genres')
        if genre_section:
            for link in genre_section.find_all('a'):
                genre_name = self.clean_text(link.text)
                if genre_name:
                    genres.append(genre_name)
        av_info['genres'] = genres
        self.logger.info(f"[JavLibrary] 类型: {genres}")

        self.logger.info(f"[JavLibrary] 解析完成: {av_id}")
        return av_info
