// ==UserScript==
// @name         IELTS Tools in XDF
// @namespace    https://github.com/strike20023/strike20023.github.io
// @version      2025-11-18
// @description  IELTS Tools in XDF
// @author       Zhe Huang
// @match        https://ieltscat.xdf.cn/practice/detail/read*
// @match        https://ieltscat.xdf.cn/practice/analyze/read*
// @run-at       document-end
// @icon         https://ieltscat.xdf.cn/favicon.ico
// @grant        none
// ==/UserScript==

(function() { // IIFE main
    'use strict';

    const btnId = 'ielts-tools-floating-btn';
    if (!document.getElementById(btnId)) {
        const btn = document.createElement('button');
        btn.id = btnId;
        const href = location.href;
        const isDetail = href.includes('/practice/detail/read');
        const isAnalyze = href.includes('/practice/analyze/read');
        btn.textContent = isDetail ? '保存H' : (isAnalyze ? 'load H' : 'IELTS 工具');

        Object.assign(btn.style, {
            position: 'fixed',
            top: '12px',
            left: '12px',
            zIndex: '2147483647',
            background: '#1976d2',
            color: '#fff',
            border: 'none',
            borderRadius: '6px',
            padding: '8px 12px',
            fontSize: '14px',
            boxShadow: '0 2px 8px rgba(0,0,0,0.15)',
            cursor: 'pointer'
        });

        btn.addEventListener('mouseenter', () => { btn.style.filter = 'brightness(1.05)'; });
        btn.addEventListener('mouseleave', () => { btn.style.filter = ''; });
        btn.addEventListener('click', () => {
            if (isDetail) {
                save_h();
            } else if (isAnalyze) {
                load_h();
            } else {
                console.info('[IELTS Tools] unsupported page');
            }
        });

        const insert = () => {
            let targetDoc = document;
            try {
                if (window.top && window.top !== window) {
                    targetDoc = window.top.document; // 尽量插入到顶层窗口
                }
            } catch (_) {
                // 跨域访问顶层失败时，退回当前文档
            }
            const root = targetDoc.body || targetDoc.documentElement;
            if (root && !targetDoc.getElementById(btnId)) {
                root.appendChild(btn);
                console.info('[IELTS Tools] button mounted in', targetDoc === document ? 'current document' : 'top document');
            } else if (!root) {
                // 等待 body 出现
                setTimeout(insert, 200);
            }
        };

        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', insert, { once: true });
            window.addEventListener('load', insert, { once: true });
        } else {
            insert();
        }
    }

    function save_h() {
        const el = document.getElementById('articleTitle');
        if (!el) return;
        const html = el.innerHTML;
        try { localStorage.setItem('ielts-tools:articleTitle:'+location.href.split('/').reverse()[1], JSON.stringify({ v: 2, html })); } catch (_) {}
        showBannerMessage('saved in key: ielts-tools:articleTitle:'+location.href.split('/').reverse()[1]);
    }

    function load_h() {
        let raw = null;
        try { raw = localStorage.getItem('ielts-tools:articleTitle:'+location.href.split('/').reverse()[1]); } catch (_) {}
        if (!raw) return;
        let data;
        try { data = JSON.parse(raw); } catch (_) { return; }
        let html;
        if (typeof data === 'string') {
            html = data;
        } else if (Array.isArray(data)) {
            const looksHtml = data.every(s => typeof s === 'string' && /<[^>]+>/.test(s));
            html = looksHtml ? data.join('') : data.map(s => `<div>${s}</div>`).join('');
        } else if (data && typeof data.html === 'string') {
            html = data.html;
        } else {
            return;
        }
        const dst = document.getElementById('articleTitle');
        if (dst) {
            dst.innerHTML = html;
            return;
        }
        const panelId = 'ielts-tools-h-panel';
        let panel = document.getElementById(panelId);
        if (!panel) {
            panel = document.createElement('div');
            panel.id = panelId;
            Object.assign(panel.style, { position:'fixed', top:'48px', left:'12px', zIndex:'2147483647', background:'#fff', color:'#333', border:'1px solid #ddd', borderRadius:'6px', padding:'8px 12px', fontSize:'14px', boxShadow:'0 2px 8px rgba(0,0,0,0.15)', maxWidth:'40vw', maxHeight:'50vh', overflow:'auto' });
            (document.body || document.documentElement).appendChild(panel);
        }
        panel.innerHTML = html;
        console.info('loaded in key: ielts-tools:articleTitle:'+location.href.split('/').reverse()[1]);
        showBannerMessage('loaded in key: ielts-tools:articleTitle:'+location.href.split('/').reverse()[1]);
    }

    document.addEventListener('click', (ev) => {
        const target = ev.target;
        const div = target && target.closest ? target.closest('div.btn-pass') : null;
        if (div) { save_h(); }
    });

    /**
     * 显示页面顶部横幅消息
     * @param {string} message - 要显示的消息内容
     * @param {Object} [options] - 可选配置参数
     * @param {string} [options.bgColor='#4CAF50'] - 背景颜色
     * @param {string} [options.color='white'] - 文字颜色
     * @param {number} [options.duration=3000] - 显示时长(毫秒)，0表示不自动消失
     * @param {string} [options.position='top'] - 显示位置('top'或'bottom')
     */
    function showBannerMessage(message, options = {}) {
        // 默认配置
        const config = {
            bgColor: '#4CAF50',
            color: 'white',
            duration: 3000,
            position: 'top',
            ...options
        };

        // 创建横幅元素
        const banner = document.createElement('div');
        
        // 设置样式
        banner.style.cssText = `
            position: fixed;
            ${config.position}: 0;
            left: 0;
            right: 0;
            padding: 16px;
            background-color: ${config.bgColor};
            color: ${config.color};
            text-align: center;
            font-family: Arial, sans-serif;
            font-size: 14px;
            z-index: 999999;
            box-shadow: 0 2px 5px rgba(0,0,0,0.2);
            transform: translateY(${config.position === 'top' ? '-100%' : '100%'});
            transition: transform 0.3s ease;
        `;

        // 设置消息内容
        banner.textContent = message;

        // 添加到页面
        document.body.appendChild(banner);

        // 触发显示动画
        setTimeout(() => {
            banner.style.transform = 'translateY(0)';
        }, 10);

        // 自动隐藏
        if (config.duration > 0) {
            setTimeout(() => {
                banner.style.transform = `translateY(${config.position === 'top' ? '-100%' : '100%'})`;
                // 动画结束后移除元素
                setTimeout(() => {
                    document.body.removeChild(banner);
                }, 300);
            }, config.duration);
        }
    }
})();