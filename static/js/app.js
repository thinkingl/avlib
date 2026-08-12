// DOM元素
const avIdsInput = document.getElementById('avIds');
const searchBtn = document.getElementById('searchBtn');
const loadHistoryBtn = document.getElementById('loadHistoryBtn');
const saveConfigBtn = document.getElementById('saveConfigBtn');
const testConnectionBtn = document.getElementById('testConnectionBtn');
const loading = document.getElementById('loading');
const searchResults = document.getElementById('searchResults');
const resultsList = document.getElementById('resultsList');
const historyList = document.getElementById('historyList');
const toast = document.getElementById('toast');

// 当前搜索结果
let currentResults = [];

// 初始化
document.addEventListener('DOMContentLoaded', () => {
    loadVersion();
    loadConfig();
    setupEventListeners();
});

// 加载git版本信息
async function loadVersion() {
    try {
        const response = await fetch('/api/version');
        const data = await response.json();

        if (data.success) {
            const timeText = data.commit_time ? formatCommitTime(data.commit_time) : '';
            document.getElementById('versionInfo').textContent = `v-${data.commit}${timeText ? ` · ${timeText}` : ''}`;
        }
    } catch (error) {
        console.error('Load version error:', error);
    }
}

// git提交时间(UTC ISO8601)转本地显示
function formatCommitTime(isoStr) {
    if (!isoStr) return '';
    const d = new Date(isoStr);
    if (isNaN(d.getTime())) return isoStr;
    return d.toLocaleString('zh-CN', { hour12: false });
}

// 设置事件监听
function setupEventListeners() {
    searchBtn.addEventListener('click', handleSearch);
    loadHistoryBtn.addEventListener('click', loadHistory);
    saveConfigBtn.addEventListener('click', saveConfig);
    testConnectionBtn.addEventListener('click', testConnection);

    // 历史面板展开时懒加载
    document.getElementById('historyPanel').addEventListener('toggle', () => {
        if (document.getElementById('historyPanel').open) {
            loadHistory();
        }
    });

    // 刷新按钮不触发summary折叠
    loadHistoryBtn.addEventListener('click', (e) => e.stopPropagation());

    // 回车键搜索
    avIdsInput.addEventListener('keydown', (e) => {
        if (e.ctrlKey && e.key === 'Enter') {
            handleSearch();
        }
    });
}

// 处理搜索
async function handleSearch() {
    const avIdsText = avIdsInput.value.trim();

    if (!avIdsText) {
        showToast('请输入番号', 'error');
        return;
    }

    // 解析番号（支持空格、换行、逗号混合分隔）
    const avIds = avIdsText
        .split(/[\n,]+/)
        .flatMap(part => part.trim().split(/\s+/))
        .map(id => id.trim().toUpperCase())
        .filter(id => id);

    if (avIds.length === 0) {
        showToast('请输入有效的番号', 'error');
        return;
    }

    // 获取选中的数据源
    const sources = Array.from(document.querySelectorAll('input[name="source"]:checked'))
        .map(cb => cb.value);

    if (sources.length === 0) {
        showToast('请至少选择一个数据源', 'error');
        return;
    }

    // 显示加载状态
    searchBtn.disabled = true;
    loading.style.display = 'block';
    searchResults.style.display = 'none';

    try {
        const response = await fetch('/api/search', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ av_ids: avIds, sources: sources })
        });

        const data = await response.json();

        if (data.success) {
            currentResults = data.results;
            displayResults(data.results);
            loadHistory(); // 刷新历史记录

            const foundCount = data.results.filter(r => r.status === 'found').length;
            showToast(`搜索完成：找到 ${foundCount}/${avIds.length} 个结果`);
        } else {
            showToast(data.error || '搜索失败', 'error');
        }
    } catch (error) {
        console.error('Search error:', error);
        showToast('搜索请求失败', 'error');
    } finally {
        searchBtn.disabled = false;
        loading.style.display = 'none';
    }
}

// 显示搜索结果
function displayResults(results) {
    searchResults.style.display = 'block';
    resultsList.innerHTML = '';

    if (results.length === 0) {
        resultsList.innerHTML = '<div class="empty-state">无搜索结果</div>';
        return;
    }

    // 显示搜索结果
    resultsList.innerHTML = '';

    if (results.length === 0) {
        resultsList.innerHTML = '<div class="empty-state">无搜索结果</div>';
        return;
    }

    results.forEach(result => {
        const card = createAvCard(result);
        resultsList.appendChild(card);
    });
}

// 创建AV卡片
function createAvCard(result) {
    const card = document.createElement('div');
    card.className = 'av-card';

    if (result.status === 'not_found') {
        card.innerHTML = `
            <div class="info">
                <h3>${result.av_id}</h3>
                <p style="color: #999;">未找到该番号信息</p>
            </div>
        `;
        return card;
    }

    const data = result.data;
    const actresses = Array.isArray(data.actresses) ? data.actresses : safeJsonParse(data.actresses);
    const genres = Array.isArray(data.genres) ? data.genres : safeJsonParse(data.genres);

    // 使用新的API获取封面图片
    const coverUrl = `/api/cover/${escapeHtml(data.av_id)}`;
    const existingBanner = result.from_database ? `
        <div class="existing-banner">该番号已存在（记录于 ${escapeHtml(formatLocalTime(data.created_at))}），以下为本地数据库中的数据</div>
    ` : '';

    card.innerHTML = `
        <div class="cover">
            <img src="${coverUrl}" alt="${escapeHtml(data.av_id)}" onclick="showLightbox('${escapeHtml(data.av_id)}')" onerror="this.src='data:image/svg+xml,<svg xmlns=%22http://www.w3.org/2000/svg%22 viewBox=%220 0 200 280%22><rect fill=%22%23ddd%22 width=%22200%22 height=%22280%22/><text fill=%22%23999%22 font-family=%22sans-serif%22 font-size=%2214%22 x=%2250%25%22 y=%2250%25%22 text-anchor=%22middle%22 dy=%22.3em%22>无封面</text></svg>'">
            <button class="cover-download" title="下载封面" onclick="downloadCover('${escapeHtml(data.av_id)}')">&#8681;</button>
        </div>
        <div class="info">
            ${existingBanner}
            <h3>${escapeHtml(data.av_id)}</h3>
            <p class="title-line">${escapeHtml(data.title) || ''}</p>
            <div class="meta">
                ${data.release_date ? `<span><strong>发行日期</strong> ${escapeHtml(data.release_date)}</span>` : ''}
                ${data.duration ? `<span><strong>时长</strong> ${escapeHtml(data.duration)}</span>` : ''}
                ${data.studio ? `<span><strong>制作商</strong> ${escapeHtml(data.studio)}</span>` : ''}
                ${data.director ? `<span><strong>导演</strong> ${escapeHtml(data.director)}</span>` : ''}
                ${data.rating ? `<span><strong>评分</strong> ${escapeHtml(data.rating)}</span>` : ''}
                <span><strong>来源</strong> ${result.from_database ? '本地数据库' : escapeHtml(result.source) || '-'}</span>
            </div>
            ${actresses.length > 0 ? `
                <div class="tags">
                    ${actresses.map(a => `<span class="tag actress">${escapeHtml(a)}</span>`).join('')}
                </div>
            ` : `
                <div class="tags"><span class="empty-tags">演员：未收录</span></div>
            `}
            ${genres.length > 0 ? `
                <div class="tags">
                    ${genres.map(g => `<span class="tag genre">${escapeHtml(g)}</span>`).join('')}
                </div>
            ` : ''}
            ${data.comment ? `
                <div class="comment-box"><strong>评论：</strong>${escapeHtml(data.comment)}</div>
            ` : ''}
            <div class="actions">
                <button class="btn btn-secondary btn-sm" onclick="openCommentModal('${escapeHtml(data.av_id)}')">${data.comment ? '修改评论' : '添加评论'}</button>
                <button class="btn btn-success btn-sm" onclick="submitToWiki('${escapeHtml(data.av_id)}')">提交到Wiki</button>
                <button class="btn btn-primary btn-sm" onclick="showWikiContent('${escapeHtml(data.av_id)}')">Wiki内容</button>
                <button class="btn btn-danger btn-sm" onclick="deleteAv('${escapeHtml(data.av_id)}')">删除</button>
            </div>
        </div>
    `;

    return card;
}

// HTML转义，防止XSS
function escapeHtml(str) {
    if (str === null || str === undefined) return '';
    return String(str)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;');
}

// 将UTC时间转为本地时间显示（数据库存储为UTC）
function formatLocalTime(utcStr) {
    if (!utcStr) return '';
    // SQLite CURRENT_TIMESTAMP格式：'2026-08-04 17:35:05'（UTC）
    const d = new Date(String(utcStr).replace(' ', 'T') + 'Z');
    if (isNaN(d.getTime())) return utcStr;
    return d.toLocaleString('zh-CN', { hour12: false });
}

// 查看DokuWiki内容预览
async function showWikiContent(avId) {
    try {
        const response = await fetch(`/api/wiki-preview/${encodeURIComponent(avId)}`);
        const data = await response.json();

        if (data.success) {
            document.getElementById('wikiModalTitle').textContent = `DokuWiki内容 - ${data.page_id}`;
            document.getElementById('wikiContent').textContent = data.content;
            document.getElementById('wikiModal').style.display = 'flex';
        } else {
            showToast(data.error || '获取Wiki内容失败', 'error');
        }
    } catch (error) {
        console.error('Wiki preview error:', error);
        showToast('获取Wiki内容失败', 'error');
    }
}

// 关闭Wiki内容弹窗
function closeWikiModal() {
    document.getElementById('wikiModal').style.display = 'none';
}

// 复制Wiki内容到剪贴板
async function copyWikiContent() {
    const content = document.getElementById('wikiContent').textContent;

    if (!content) {
        showToast('内容为空', 'error');
        return;
    }

    try {
        if (navigator.clipboard && window.isSecureContext) {
            await navigator.clipboard.writeText(content);
        } else {
            // 降级方案：临时textarea
            const ta = document.createElement('textarea');
            ta.value = content;
            ta.style.position = 'fixed';
            ta.style.opacity = '0';
            document.body.appendChild(ta);
            ta.select();
            document.execCommand('copy');
            document.body.removeChild(ta);
        }
        showToast('已复制到剪贴板');
    } catch (error) {
        console.error('Copy error:', error);
        showToast('复制失败', 'error');
    }
}

// 评论相关
let currentCommentAvId = null;

// 打开评论编辑弹窗
async function openCommentModal(avId) {
    currentCommentAvId = avId;
    document.getElementById('commentModalTitle').textContent = `评论 - ${avId}`;
    document.getElementById('commentInput').value = '';
    document.getElementById('commentModal').style.display = 'flex';

    // 预填现有评论
    try {
        const response = await fetch(`/api/av/${encodeURIComponent(avId)}`);
        const data = await response.json();
        if (data.success && data.data.comment) {
            document.getElementById('commentInput').value = data.data.comment;
        }
    } catch (error) {
        console.error('Load comment error:', error);
    }
}

// 关闭评论弹窗
function closeCommentModal() {
    document.getElementById('commentModal').style.display = 'none';
    currentCommentAvId = null;
}

// 保存评论
async function saveComment() {
    if (!currentCommentAvId) return;

    const comment = document.getElementById('commentInput').value.trim();
    const saveBtn = document.getElementById('saveCommentBtn');
    saveBtn.disabled = true;

    try {
        const response = await fetch(`/api/av/${encodeURIComponent(currentCommentAvId)}/comment`, {
            method: 'PUT',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ comment: comment })
        });

        const data = await response.json();

        if (data.success) {
            showToast('评论已保存');
            closeCommentModal();
            loadHistory(); // 刷新历史显示评论
        } else {
            showToast(data.error || '保存失败', 'error');
        }
    } catch (error) {
        console.error('Save comment error:', error);
        showToast('保存失败', 'error');
    } finally {
        saveBtn.disabled = false;
    }
}

// 大图查看
function showLightbox(avId) {
    const img = document.getElementById('lightboxImg');
    img.src = `/api/cover/${encodeURIComponent(avId)}`;
    document.getElementById('lightbox').style.display = 'flex';
}

function closeLightbox() {
    document.getElementById('lightbox').style.display = 'none';
    document.getElementById('lightboxImg').src = '';
}

// 下载封面图片
function downloadCover(avId) {
    const a = document.createElement('a');
    a.href = `/api/cover/${encodeURIComponent(avId)}?download=1`;
    a.download = `${avId}.jpg`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
}

// 安全的JSON解析
function safeJsonParse(str) {
    if (!str) return [];
    if (Array.isArray(str)) return str;
    try {
        return JSON.parse(str);
    } catch {
        return [str];
    }
}

// 提交单个番号到Wiki
async function submitToWiki(avId) {
    try {
        const response = await fetch('/api/submit-to-wiki', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ av_ids: [avId] })
        });

        const data = await response.json();

        if (data.success && data.results[0].status === 'success') {
            showToast(`${avId} 已提交到Wiki`);
        } else {
            showToast(data.results[0]?.message || '提交失败', 'error');
        }
    } catch (error) {
        console.error('Submit error:', error);
        showToast('提交请求失败', 'error');
    }
}

// 加载历史记录
async function loadHistory() {
    try {
        const response = await fetch('/api/av?limit=50');
        const data = await response.json();

        if (data.success) {
            displayHistory(data.data);
        }
    } catch (error) {
        console.error('Load history error:', error);
    }
}

// 显示历史记录
function displayHistory(avList) {
    historyList.innerHTML = '';

    if (avList.length === 0) {
        historyList.innerHTML = '<div class="empty-state">暂无历史记录</div>';
        return;
    }

    avList.forEach(av => {
        const card = document.createElement('div');
        card.className = 'av-card';

        const actresses = safeJsonParse(av.actresses);
        const genres = safeJsonParse(av.genres);

        // 使用新的API获取封面图片
        const coverUrl = `/api/cover/${escapeHtml(av.av_id)}`;

        card.innerHTML = `
            <div class="cover">
                <img src="${coverUrl}" alt="${escapeHtml(av.av_id)}" onclick="showLightbox('${escapeHtml(av.av_id)}')" onerror="this.src='data:image/svg+xml,<svg xmlns=%22http://www.w3.org/2000/svg%22 viewBox=%220 0 200 280%22><rect fill=%22%23ddd%22 width=%22200%22 height=%22280%22/><text fill=%22%23999%22 font-family=%22sans-serif%22 font-size=%2214%22 x=%2250%25%22 y=%2250%25%22 text-anchor=%22middle%22 dy=%22.3em%22>无封面</text></svg>'">
                <button class="cover-download" title="下载封面" onclick="downloadCover('${escapeHtml(av.av_id)}')">&#8681;</button>
            </div>
            <div class="info">
                <h3>${escapeHtml(av.av_id)}</h3>
                <p class="title-line">${escapeHtml(av.title) || ''}</p>
                <div class="meta">
                    ${av.studio ? `<span><strong>制作商</strong> ${escapeHtml(av.studio)}</span>` : ''}
                    ${av.release_date ? `<span><strong>发行日期</strong> ${escapeHtml(av.release_date)}</span>` : ''}
                    ${av.rating ? `<span><strong>评分</strong> ${escapeHtml(av.rating)}</span>` : ''}
                    ${av.created_at ? `<span><strong>记录时间</strong> ${escapeHtml(formatLocalTime(av.created_at))}</span>` : ''}
                    <span><strong>来源</strong> ${escapeHtml(av.source) || '-'}</span>
                </div>
                ${actresses.length > 0 ? `
                    <div class="tags">
                        ${actresses.map(a => `<span class="tag actress">${escapeHtml(a)}</span>`).join('')}
                    </div>
                ` : `
                    <div class="tags"><span class="empty-tags">演员：未收录</span></div>
                `}
                ${av.comment ? `
                    <div class="comment-box"><strong>评论：</strong>${escapeHtml(av.comment)}</div>
                ` : ''}
                <div class="actions">
                    <button class="btn btn-secondary btn-sm" onclick="openCommentModal('${escapeHtml(av.av_id)}')">${av.comment ? '修改评论' : '添加评论'}</button>
                    <button class="btn btn-success btn-sm" onclick="submitToWiki('${escapeHtml(av.av_id)}')">提交到Wiki</button>
                    <button class="btn btn-primary btn-sm" onclick="showWikiContent('${escapeHtml(av.av_id)}')">Wiki内容</button>
                    <button class="btn btn-danger btn-sm" onclick="deleteAv('${escapeHtml(av.av_id)}')">删除</button>
                </div>
            </div>
        `;

        historyList.appendChild(card);
    });
}

// 删除AV
async function deleteAv(avId) {
    if (!confirm(`确定要删除 ${avId} 吗？`)) {
        return;
    }

    try {
        const response = await fetch(`/api/av/${avId}`, {
            method: 'DELETE'
        });

        const data = await response.json();

        if (data.success) {
            showToast(`已删除 ${avId}`);
            loadHistory();
        } else {
            showToast(data.error || '删除失败', 'error');
        }
    } catch (error) {
        console.error('Delete error:', error);
        showToast('删除请求失败', 'error');
    }
}

// 加载配置
async function loadConfig() {
    try {
        const response = await fetch('/api/config');
        const data = await response.json();

        document.getElementById('wikiUrl').value = data.dokuwiki_url || '';
        document.getElementById('wikiUsername').value = data.dokuwiki_username || '';
    } catch (error) {
        console.error('Load config error:', error);
    }
}

// 保存配置
async function saveConfig() {
    const config = {
        dokuwiki_url: document.getElementById('wikiUrl').value,
        dokuwiki_username: document.getElementById('wikiUsername').value,
        dokuwiki_password: document.getElementById('wikiPassword').value,
        dokuwiki_api_token: document.getElementById('wikiToken').value
    };

    try {
        const response = await fetch('/api/config', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(config)
        });

        const data = await response.json();

        if (data.success) {
            showToast('配置已保存');
        } else {
            showToast(data.error || '保存失败', 'error');
        }
    } catch (error) {
        console.error('Save config error:', error);
        showToast('保存配置失败', 'error');
    }
}

// 测试连接
async function testConnection() {
    testConnectionBtn.disabled = true;
    showToast('正在测试连接...');

    try {
        const response = await fetch('/api/test-wiki-connection');
        const data = await response.json();

        if (data.success) {
            showToast('连接成功', 'success');
        } else {
            showToast('连接失败', 'error');
        }
    } catch (error) {
        console.error('Test connection error:', error);
        showToast('测试连接失败', 'error');
    } finally {
        testConnectionBtn.disabled = false;
    }
}

// 显示提示消息
function showToast(message, type = 'success') {
    toast.textContent = message;
    toast.className = `toast ${type}`;
    toast.style.display = 'block';

    setTimeout(() => {
        toast.style.display = 'none';
    }, 3000);
}
