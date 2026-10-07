# HalluRef-Bench 条目格式规范（v1 格式冻结，2026-10-07）

> 公开幻觉文献评测基准（BENCH-01 的文献线数据面，REF-06 AI 幻觉文献风险画像的基准）。
> 全部条目为程序化合成的虚构文献（作者/刊名/DOI 均不指向真实出版物）。
> 条目正文（citation）为 GB/T 7714 顺序编码制单条著录字符串；fields 为其结构化展开。

## 条目 JSONL 格式（每行一个 JSON 对象，UTF-8，无 BOM）

```json
{
  "entry_id": "hr-0001",
  "label": "genuine | hallucinated",
  "classes": [],                        // hallucinated 至少 1 类；genuine 恒为 []
  "signals": [],                        // 可检测信号清单 {type, field, detail}
  "citation": "张三. 虚构题名[J]. 虚构学报, 2024, 47(5): 101-110.",
  "fields": {
    "entry_type": "J",
    "authors": ["张三"],
    "title": "虚构题名",
    "container": "虚构学报",
    "year": "2024", "volume": "47", "issue": "5", "pages": "101-110",
    "publisher": null, "city": null, "isbn": null,
    "doi": "10.9999/halluref.2024.0001"
  }
}
```

字段约定：
- `entry_id`：`hr-` + 4 位序号，全库唯一；
- `citation`：与 fields 自洽（genuine 条目自洽；hallucinated 条目的缺陷同时体现在两级）；
- DOI：genuine 条目一律 `10.9999/` 前缀（登记于 `data/knowledge/doi_fake_prefixes.json`，
  幻觉画像不计为信号）；hallucinated 条目使用**未登记**前缀（如 10.7777/）作为可检信号；
- 禁止时间戳字段；条目内容与顺序一经冻结不得手改（改体例=固定 seed 重新生成整库提交）。

## 幻觉类目（v1 冻结 6 类）

| class | 含义 | 主检信号 |
|---|---|---|
| `doi_prefix_unknown` | DOI 前缀不在已知注册前缀集 | 前缀比对 + 白名单 |
| `isbn_checksum_invalid` | ISBN 校验位错误 | GB/T 5792 校验算法 |
| `year_out_of_range` | 年份超前于基准时点或超合理范围 | 年界规则 |
| `page_range_inverted` | 起止页倒置 | page_range 规则 |
| `impossible_field_combo` | 字段组合矛盾（期刊条目含 ISBN / 图书条目带卷期页等） | 类型-字段矩阵 |
| `self_referential_title` | 题名与载体名相同/题名内嵌载体名 | 字符串比对 |

复合条目：一条带 ≥2 类（classes 列出全部），评测时可按"任一类命中即判中"或
"全类命中"两种口径分别计分（基准报告须声明口径）。

## 规模拍板（plan/00 决策 D-4，2026-10-07）

- **v1 目标 200 条**：genuine 100 + hallucinated 100；
- hallucinated 100 = 6 单类 × 16 + 复合 4；
- 全量库随 M3（REF-06 实现时）用 `taw.rng` 固定 seed 一次性生成入库；
  本目录当前仅冻结**格式 + 本规范 + 12 条示例**（`halluref_v1_examples.jsonl`）；
- 生成纪律与 `data/frozen/` 一致：无时间戳、两次运行位级一致、CR 守门。

## 对账口径（随格式一并冻结）

- 文献线基准逐条给出 REF-06 的期望输出：genuine → 体检分不低于阈值；hallucinated →
  至少命中 signals 中声明的信号之一（宽容口径）或全部（严格口径）；
- 误报优先：genuine 条目被标任何幻觉信号，计误报，权重高于漏报。
