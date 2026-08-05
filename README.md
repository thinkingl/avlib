# AVLib - AV信息管理系统

## 项目简介

一个基于Flask的AV信息管理系统，支持根据番号搜索AV信息和封面图片，并可以将信息提交到DokuWiki。

## 功能特性

- 根据番号搜索AV信息（支持批量搜索）
- 从多个网站获取数据（javbus, javdb, javlibrary）
- 封面图片下载和管理
- SQLite数据库存储历史记录
- 一键提交到DokuWiki
- 简洁的Web界面

## 技术栈

- **后端**: Python + Flask
- **数据库**: SQLite
- **前端**: HTML + CSS + JavaScript
- **爬虫**: requests + BeautifulSoup4

## 项目结构

```
avlib/
├── app.py              # Flask主应用
├── config.py           # 配置文件
├── requirements.txt    # Python依赖
├── database.py         # 数据库操作
├── scrapers/           # 爬虫模块
│   ├── __init__.py
│   ├── base.py         # 爬虫基类
│   ├── javbus.py       # JavBus爬虫
│   ├── javdb.py        # JavDB爬虫
│   └── javlibrary.py   # JAV Library爬虫
├── dokuwiki.py         # DokuWiki API集成
├── static/             # 静态文件
│   ├── css/
│   │   └── style.css
│   └── js/
│       └── app.js
├── templates/          # HTML模板
│   └── index.html
└── images/             # 下载的封面图片
```

## 数据库设计

### av_info 表
- id: 主键
- av_id: 番号（唯一）
- title: 标题
- studio: 制作商
- publisher: 发行商
- series: 系列
- release_date: 发行日期
- duration: 时长
- director: 导演
- actresses: 演员（JSON格式）
- genres: 类型（JSON格式）
- cover_url: 封面图片URL
- cover_path: 本地封面路径
- source: 数据来源网站
- created_at: 创建时间
- updated_at: 更新时间

### search_history 表
- id: 主键
- av_id: 番号
- search_time: 搜索时间
- source: 搜索来源

## 安装和运行

1. 安装依赖：
```bash
pip install -r requirements.txt
```

2. 运行应用：
```bash
python app.py
```

3. 访问 http://localhost:5000

## 配置说明

在 `config.py` 中配置：
- DokuWiki地址和认证信息
- 图片存储路径
- 数据库路径
