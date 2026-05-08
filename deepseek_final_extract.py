"""
DeepSeek 完整消息提取 — 最终版
Hack：修改容器高度强制虚拟列表渲染全部 items（已验证有效，828个DOM节点）
提取：遍历所有DOM子节点，包括无messageId的节点
"""
import json, time, os
from datetime import datetime
from playwright.sync_api import sync_playwright

def launch():
    p = sync_playwright().start()
    b = p.chromium.launch_persistent_context(
        user_data_dir=r"G:\GOT\chromium_profile",
        executable_path=r"C:\Users\Administrator\AppData\Local\ms-playwright\chromium-1208\chrome-win64\chrome.exe",
        headless=False, viewport={"width": 1280, "height": 900},
        args=["--disable-blink-features=AutomationControlled"]
    )
    page = b.pages[0] if b.pages else b.new_page()
    return p, b, page

def main():
    input("\n>>> 按 Enter 启动浏览器，进入对话后自动开始...")
    p, b, page = launch()
    page.goto("https://chat.deepseek.com", wait_until="domcontentloaded")
    print("请进入目标对话...")

    # 等待 React items >= 800
    for i in range(120):
        time.sleep(1)
        info = page.evaluate(r"""() => {
            const el = document.querySelector('.ds-virtual-list--printable') || document.querySelector('.ds-virtual-list._2bd7b35');
            if (!el) return {items:0, vis:0};
            const vl = el.querySelector('.ds-virtual-list-visible-items');
            const fk = Object.keys(el).find(k => k.startsWith('__reactFiber$'));
            let fb = el[fk], n = 0;
            while (fb) { if (fb.memoizedProps?.items) { n = fb.memoizedProps.items.length; break; } fb = fb.return; }
            return {items: n, vis: vl ? vl.children.length : 0, sH: el.scrollHeight};
        }""")
        if info['items'] >= 800:
            print(f"就绪: items={info['items']}, vis={info['vis']}, sH={info['sH']}")
            time.sleep(2)
            break
        if info['vis'] > 0 and i % 15 == 14:
            print(f"  items={info['items']} ({i+1}s)...")

    # ===== HACK: 强制渲染全部 items =====
    print("\n[HACK] 修改容器高度，强制渲染全部 items...")
    page.evaluate(r"""() => {
        const el = document.querySelector('.ds-virtual-list--printable') || document.querySelector('.ds-virtual-list._2bd7b35');
        if (!el) return;
        el.style.height = el.scrollHeight + 'px';
        el.style.maxHeight = el.scrollHeight + 'px';
        el.style.overflowY = 'visible';
        el.style.overflow = 'visible';
    }""")
    time.sleep(3)

    dom_count = page.evaluate(r"""() => {
        const c = document.querySelector('.ds-virtual-list--printable') || document.querySelector('.ds-virtual-list._2bd7b35');
        const vl = c?.querySelector('.ds-virtual-list-visible-items');
        return vl ? vl.children.length : 0;
    }""")
    print(f"DOM 节点数: {dom_count}")

    if dom_count < 100:
        print("❌ Hack 未生效，DOM 节点太少")
        print("请手动滚到底部再滚回顶部，然后重试")
        input("Enter to close...")
        b.close(); p.stop(); return

    # ===== 提取全部消息 =====
    print("\n[提取] 遍历全部 DOM 节点...")
    result = page.evaluate(r"""() => {
        const c = document.querySelector('.ds-virtual-list--printable') || document.querySelector('.ds-virtual-list._2bd7b35');
        if (!c) return {msgs:[], unknowns:[], total:0};
        const vl = c.querySelector('.ds-virtual-list-visible-items');
        if (!vl) return {msgs:[], unknowns:[], total:0};

        const msgs = [];
        const unknowns = [];
        const seenIds = new Set();

        for (let i = 0; i < vl.children.length; i++) {
            const el = vl.children[i];
            const text = el.innerText || '';
            const textLen = text.length;

            const fk = Object.keys(el).find(k => k.startsWith('__reactFiber$'));
            if (!fk) { unknowns.push({index:i, textLen, reason:'no fiber'}); continue; }

            let fb = el[fk], msgId = null, role = null, content = '';
            let depth = 0;

            // 遍历 fiber 树找 messageId, role, content
            while (fb && depth < 25) {
                const pr = fb.memoizedProps;
                if (!pr) { fb = fb.return; depth++; continue; }

                // messageId 可能在多个位置
                if (pr.messageId && !msgId) msgId = pr.messageId;
                if (pr.value?.messageId && !msgId) msgId = pr.value.messageId;
                if (pr.children?.props?.messageId && !msgId) msgId = pr.children.props.messageId;
                if (pr.children?.props?.value?.messageId && !msgId) msgId = pr.children.props.value.messageId;
                if (pr.children?.children?.props?.value?.messageId && !msgId) msgId = pr.children.children.props.value.messageId;

                // content 在多处
                if (pr.content && typeof pr.content === 'string' && !content) { content = pr.content; role = role || 'assistant'; }
                if (pr.value?.content && typeof pr.value.content === 'string' && !content) { content = pr.value.content; role = role || 'assistant'; }
                if (pr.children?.props?.content && typeof pr.children.props.content === 'string' && !content) { content = pr.children.props.content; role = role || 'assistant'; }

                // role 从 className 判断
                if (pr.className) {
                    const cn = String(pr.className);
                    if (!role && (cn.includes('_9663006') || (cn.includes('user') && !cn.includes('userName') && cn.length < 50))) role = 'user';
                    if (!role && (cn.includes('_4f9bf79') || (cn.includes('assistant') && cn.length < 50))) role = 'assistant';
                }

                fb = fb.return; depth++;
            }

            if (!msgId) {
                // 检查是否是 key=-999 的分隔符
                const fk2 = Object.keys(el).find(k => k.startsWith('__reactFiber$'));
                let fb2 = el[fk2], isSep = false, sepKey = null;
                for (let d = 0; d < 15 && fb2; d++) {
                    const p2 = fb2.memoizedProps;
                    if (p2?.item?.key === -999) { isSep = true; sepKey = -999; break; }
                    if (p2?.item?.key !== undefined && p2?.item?.key !== null) { sepKey = p2.item.key; }
                    fb2 = fb2.return;
                }
                unknowns.push({index:i, textLen, reason:'no messageId', sepKey, html: el.outerHTML.substring(0, 200)});
                continue;
            }

            if (seenIds.has(msgId)) {
                unknowns.push({index:i, msgId, textLen, reason:'duplicate'});
                continue;
            }
            seenIds.add(msgId);

            msgs.push({
                messageId: msgId,
                role: role || 'unknown',
                content: content,
                text: text,
                textLen: textLen
            });
        }

        return {msgs, unknowns, total: vl.children.length};
    }""")

    msgs = result['msgs']
    unknowns = result['unknowns']
    total_dom = result['total']

    print(f"DOM 总节点: {total_dom}")
    print(f"成功提取: {len(msgs)}")
    print(f"未识别: {len(unknowns)}")

    # 分析未识别节点
    no_msgid = [u for u in unknowns if u.get('reason') == 'no messageId']
    duplicates = [u for u in unknowns if u.get('reason') == 'duplicate']
    print(f"  无 messageId: {len(no_msgid)}")
    print(f"  重复: {len(duplicates)}")

    if no_msgid:
        # 看看无 messageId 的节点是否有文本内容
        with_text = [u for u in no_msgid if u.get('textLen', 0) > 0]
        without_text = [u for u in no_msgid if u.get('textLen', 0) == 0]
        print(f"    有文本: {len(with_text)}")
        print(f"    无文本: {len(without_text)}")

        if with_text:
            print(f"\n    有文本的无messageId节点 (前5个):")
            for u in with_text[:5]:
                print(f"      idx={u['index']} text={u['textLen']}字 sepKey={u.get('sepKey')} html={u.get('html','')[:80]}")

    # 统计
    ids = sorted(m['messageId'] for m in msgs)
    gaps = [i for i in range(min(ids), max(ids)+1) if i not in set(ids)] if ids else []
    u = sum(1 for m in msgs if m['role'] == 'user')
    a = sum(1 for m in msgs if m['role'] == 'assistant')

    print(f"\n{'='*55}")
    print(f"提取消息: {len(msgs)} (User:{u} AI:{a})")
    print(f"messageId 范围: {min(ids)}~{max(ids)}")
    print(f"空洞: {len(gaps)}")
    if gaps:
        print(f"  {gaps}")

    # 保存
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out = rf"G:\GOT\output\deepseek_full_{ts}.json"
    os.makedirs(r"G:\GOT\output", exist_ok=True)
    output = {
        "meta": {
            "total": len(msgs),
            "totalDom": total_dom,
            "userCount": u,
            "aiCount": a,
            "unknownRole": len(msgs) - u - a,
            "gaps": gaps,
            "noMessageIdNodes": len(no_msgid),
            "extractedAt": ts
        },
        "messages": sorted(msgs, key=lambda x: x['messageId'] or 0)
    }
    with open(out, 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    print(f"\n保存: {out}")

    input("\nEnter to close...")
    b.close(); p.stop()

if __name__ == '__main__':
    main()
