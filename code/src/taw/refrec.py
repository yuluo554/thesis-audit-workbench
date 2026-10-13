# -*- coding: utf-8 -*-
"""REF-07 反向引用推荐与一键插入（plan/04 §五/§十；FR-07，防幻觉闭环）。

**结构防幻觉**：推荐候选只能来自**已审计库内文献**（传入的 cards 序列）——
`recommend` 的返回值恒为输入卡片的 card_id 子集，任何情况下都不会生成库外条目
（本模块不产生新字符串作为题名/作者；守卫测试断言该性质）。

两件能力：
1. **库内 BM25 检索**：句子 → Top-K 命中文献 + 逐条命中证据（词项/频次/分值）；
2. **一键插入 + 编号重排**：插入触发 `taw.renumber` 内核，产出新编号映射；
   任意插入/删除位置 × 组合矩阵回归 100%（同内核 M4 复用于对象编号）。
"""

import math
import re

# 中英混排分词：CJK 逐字 bigram + 西文按词（避免引入第三方分词依赖）
_CJK = r"\u4e00-\u9fff"
_TOKEN_EN = re.compile(r"[A-Za-z][A-Za-z\-]*|\d+(?:\.\d+)?")
_TOKEN_CJK = re.compile("[{}]+".format(_CJK))


def tokenize(text):
    """文本 → 词项列表（西文词 + CJK 单字与 bigram）。确定性、纯本地。"""
    if not text:
        return []
    out = [t.lower() for t in _TOKEN_EN.findall(text)]
    for run in _TOKEN_CJK.findall(text):
        out.extend(list(run))
        out.extend(run[i:i + 2] for i in range(len(run) - 1))
    return out


class BM25:
    """自实现 BM25（k1/b 可调；小语料无需外部依赖，算法本身是创新展示面）。"""

    def __init__(self, k1=1.5, b=0.75):
        self.k1 = k1
        self.b = b
        self.docs = []          # [(doc_id, tokens)]
        self.df = {}
        self.avgdl = 0.0

    def fit(self, docs):
        """docs = [(doc_id, text)]。"""
        self.docs = [(did, tokenize(text)) for did, text in docs]
        self.df = {}
        for _did, toks in self.docs:
            for t in set(toks):
                self.df[t] = self.df.get(t, 0) + 1
        n = len(self.docs)
        self.avgdl = (sum(len(t) for _d, t in self.docs) / n) if n else 0.0
        return self

    def _idf(self, term):
        n = len(self.docs)
        df = self.df.get(term, 0)
        return math.log(1.0 + (n - df + 0.5) / (df + 0.5))

    def search(self, query, top_k=5):
        """→ [{doc_id, score, hits:[{term,tf,idf}]}]，按 score 降序（同分按 doc_id 稳定排序）。"""
        qtoks = tokenize(query)
        if not qtoks or not self.docs:
            return []
        results = []
        for did, toks in self.docs:
            dl = len(toks) or 1
            tf_map = {}
            for t in toks:
                tf_map[t] = tf_map.get(t, 0) + 1
            score = 0.0
            hits = []
            for t in set(qtoks):
                tf = tf_map.get(t)
                if not tf:
                    continue
                idf = self._idf(t)
                denom = tf + self.k1 * (1 - self.b + self.b * dl / (self.avgdl or 1))
                contrib = idf * tf * (self.k1 + 1) / denom
                score += contrib
                hits.append({"term": t, "tf": tf, "idf": round(idf, 4),
                             "contrib": round(contrib, 4)})
            if score > 0:
                hits.sort(key=lambda h: (-h["contrib"], h["term"]))
                results.append({"doc_id": did, "score": round(score, 4), "hits": hits})
        results.sort(key=lambda r: (-r["score"], str(r["doc_id"])))
        return results[:top_k]


def _entry_text(card):
    """文献卡 → 检索文本（题名 + 刊名/书名 + 著者 + 年份）。"""
    parts = [card.get("title") or ""]
    src = card.get("source") or {}
    parts.append(src.get("container") or "")
    parts.append(" ".join(a.get("raw") or "" for a in card.get("authors", [])))
    parts.append(str(src.get("year") or ""))
    return " ".join(p for p in parts if p)


def build_index(cards):
    """已审计库内文献 → BM25 索引（doc_id = card_id）。"""
    return BM25().fit([(c["card_id"], _entry_text(c)) for c in cards])


def recommend(cards, sentence, top_k=5, index=None):
    """句子 → 库内 Top-K 推荐（附命中证据）。

    防幻觉：返回项的 `card_id` 恒为传入 cards 的子集；不构造任何库外文献文本。
    """
    index = index or build_index(cards)
    by_id = {c["card_id"]: c for c in cards}
    out = []
    for r in index.search(sentence, top_k=top_k):
        card = by_id.get(r["doc_id"])
        if card is None:
            continue                      # 结构防幻觉：库外 id 一律丢弃
        out.append({
            "card_id": r["doc_id"],
            "label": card["evidence"].get("label"),
            "title": card.get("title"),
            "year": card["source"].get("year"),
            "score": r["score"],
            "hits": r["hits"],
            "in_library": True,
        })
    return out


def insert_reference(items, cards, new_card_id, before=False):
    """一键插入：把库内条目 new_card_id 插入编号序列 items → RenumberPlan。

    `new_card_id` 必须是库内已审计条目（`recommend` 的产出）：不在 cards 中 → ValueError，
    这是"推荐候选只能来自已审计库内文献"的结构保证在插入路径上的延伸。
    默认插在**末位**（顺序编码制按首次引用先后，新引用通常在文末附近）。
    """
    from taw import renumber
    if new_card_id not in {c["card_id"] for c in cards}:
        raise ValueError("插入目标必须是已审计库内文献：{}".format(new_card_id))
    if not items:
        return renumber.renumber([{"item_id": new_card_id, "markers": []}], [])
    anchor = items[0]["item_id"] if before else items[-1]["item_id"]
    edits = [{"type": "insert", "new_item_id": new_card_id,
              "target": anchor, "before": before}]
    return renumber.renumber(list(items), edits)


def delete_reference(items, target_id):
    """删除编号项 → RenumberPlan（与插入同一内核，矩阵回归共用）。"""
    from taw import renumber
    return renumber.renumber(list(items), [{"type": "delete", "target": target_id}])


def edit_matrix(n_items, max_edits=2):
    """生成插入/删除矩阵（基准与回归用）：所有单编辑 + 双编辑组合位置。

    返回 [(edits, 描述)]；位置覆盖首位/中位/末位 × before/after。
    """
    base_ids = ["it{}".format(i + 1) for i in range(n_items)]
    cases = []
    for i, iid in enumerate(base_ids):
        cases.append(([{"type": "delete", "target": iid}], "delete@{}".format(i)))
    for pos in range(n_items + 1):
        cases.append(([{"type": "insert", "new_item_id": "new{}".format(pos),
                        "target": base_ids[min(pos, n_items - 1)],
                        "before": pos == 0}], "insert@{}".format(pos)))
    if max_edits >= 2:
        for i, a in enumerate(base_ids):
            for j, b in enumerate(base_ids):
                if i == j:
                    continue
                cases.append(([{"type": "delete", "target": a},
                               {"type": "delete", "target": b}],
                              "delete@{}+{}".format(i, j)))
        for pos in range(n_items + 1):
            for i, iid in enumerate(base_ids):
                if pos == i:
                    continue
                cases.append(([{"type": "insert", "new_item_id": "xa{}".format(pos),
                                "target": iid, "before": True},
                               {"type": "delete", "target": base_ids[(pos + 1) % n_items]}],
                              "ins@{}del@{}".format(pos, i)))
    return base_ids, cases

