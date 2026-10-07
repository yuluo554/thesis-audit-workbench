# -*- coding: utf-8 -*-
"""合成论文 docx 生成器（M1 核心资产，plan/05 §二）。

产出 data/frozen/thesis/：一篇全部虚构的完整学位论文 docx + 逐处真值 JSON。
四类植入（真值逐处记录位置与期望，语义对齐 plan/04 §七）：
  1. 样式错误   —— 章标题降级 / 题注用 Normal / 正文误用标题样式；
  2. 悬空标记   —— 手打"表 9-1"（对象不存在）、REF 域指向不存在书签；
  3. 术语变体   —— 同一概念两种叫法 / 伪空格 / 千分位不一致 / 标准号空格不一致；
  4. AI 模式    —— 模板连接词、套话重复+句长均匀、总结套话（对接
                    data/knowledge/aigc_features.json 的 feature_id，伦理边界见 plan/04 §六）。

确定性纪律（M1 实测结论）：
- 内容为声明式模型，无随机抽取（taw.rng 可用但当前版本不消费）；
- python-docx 保存时 zipfile.writestr 直接收 str 文件名会把**当前时间**写进
  zip 条目——同一秒内两次构建才位级一致，实测出的确定性杀手；因此保存后把
  zip 原样重写：条目内容不变、时间戳固定 1980-01-01、条目顺序保持；
- 重写后 python-docx 1.1.2(3.8) 与 1.2.0(3.12) 产出字节一致（M1 实测）；
- core_properties 全部显式固定，产物无时间戳。

真值同时给出 style_tree（逐段 style+text，text 与 python-docx .text 口径一致：
fldSimple 内 run 不计入）——M2 docx 解析器的 F1 基线真值。

用法：
    python code/tools/gen_thesis_docx.py [--out DIR] [--force]
不带 --force 且目标目录已有文件时拒绝覆盖（exit 1）。需要 extras docx。
"""

import argparse
import json
import sys
import zipfile
from datetime import datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "code" / "src"))

# docx 依赖惰性加载（build_document 内 _ensure_docx），保持本模块可被无 docx 环境安全导入
Document = OxmlElement = qn = None


def _ensure_docx():
    global Document, OxmlElement, qn
    if Document is not None:
        return
    try:
        from docx import Document as _Document
        from docx.oxml import OxmlElement as _OxmlElement
        from docx.oxml.ns import qn as _qn
    except ImportError:
        raise RuntimeError("缺少 python-docx：python -m pip install -e './code[docx]'")
    Document, OxmlElement, qn = _Document, _OxmlElement, _qn

SCHEMA_VERSION = 1
DATASET_ID = "thesis-synthetic-v1"
FIXED_DATE = datetime(2026, 5, 1, 0, 0, 0)

BOOKMARK_FIG31 = "_Ref30001"     # 图3-1 题注书签（有效）
BOOKMARK_DANGLING = "_Ref99900099"  # 悬空域指向的不存在书签


class Ledger:
    """构建期记录段落/对象/域/植入物；真值 JSON 的唯一来源。"""

    def __init__(self):
        self.paragraphs = []   # {i, style, text}
        self.fields = []       # {para_index, instr, display, target_bookmark, bookmark_exists}
        self.implants = []     # {id, kind, subtype, paras, text_anchor, expect, also_expect}
        self.objects = []      # {kind, label, caption_para, bookmark, mentioned_paras, referenced}

    def para(self, style, text):
        self.paragraphs.append({"i": len(self.paragraphs), "style": style, "text": text})
        return self.paragraphs[-1]["i"]

    def implant(self, iid, kind, subtype, paras, text_anchor, expect, also_expect=None):
        entry = {
            "id": iid, "kind": kind, "subtype": subtype,
            "paras": paras if isinstance(paras, list) else [paras],
            "text_anchor": text_anchor, "expect": expect,
            "also_expect": also_expect or [],
        }
        self.implants.append(entry)
        return entry

    def object(self, kind, label, caption_para, bookmark=None, mentioned_paras=()):
        self.objects.append({
            "kind": kind, "label": label, "caption_para": caption_para,
            "bookmark": bookmark, "mentioned_paras": list(mentioned_paras),
            "referenced": bool(mentioned_paras),
        })
        return self.objects[-1]


def add_ref_field(paragraph, target_bookmark, display_text):
    """在段落末尾追加 fldSimple REF 域（Word 交叉引用域；M2 按 instr 解析）。"""
    fld = OxmlElement("w:fldSimple")
    fld.set(qn("w:instr"), " REF {} \\h ".format(target_bookmark))
    run = OxmlElement("w:r")
    t = OxmlElement("w:t")
    t.text = display_text
    run.append(t)
    fld.append(run)
    paragraph._p.append(fld)


def add_bookmark_to(paragraph, name):
    """题注段落挂书签（有效 REF 域的目标）。"""
    bid = "1"
    start = OxmlElement("w:bookmarkStart")
    start.set(qn("w:id"), bid)
    start.set(qn("w:name"), name)
    end = OxmlElement("w:bookmarkEnd")
    end.set(qn("w:id"), bid)
    paragraph._p.insert(0, start)
    paragraph._p.append(end)


# ---- 论文内容（全部虚构；声明式模型）----


def build_document(ledger):
    _ensure_docx()
    doc = Document()
    props = doc.core_properties
    props.author = "张合成（taw 合成数据，非真实人物）"
    props.last_modified_by = "taw-gen"
    props.title = "虚构场景下的合成数据生成方法研究"
    props.created = FIXED_DATE
    props.modified = FIXED_DATE
    props.revision = 1

    def para(text, style="Normal"):
        p = doc.add_paragraph(text, style=style)
        idx = ledger.para(style, text)
        return p, idx

    def heading(text, level=1):
        return para(text, style="Heading {}".format(level))

    def caption(text, style="Caption"):
        return para(text, style=style)

    # 封面
    para("虚构场景下的合成数据生成方法研究", style="Title")
    para("作者：张合成    学号：2026999001")
    para("学校：虚构理工大学    指导教师：李虚构")
    para("2026年5月")

    # 摘要
    heading("摘要")
    para("针对真实数据获取成本高、隐私约束强的问题，本文研究基于生成模型的合成数据构建方法。"
         "机器学习任务的性能依赖大规模高质量样本，而真实场景中标注数据往往难以获得。"
         "本文围绕数据分布建模与质量评估两个环节展开，提出一套可控的合成数据生成框架。")
    para("本文的主要工作包括三部分：一是梳理合成数据的构建流程与质量控制要点；"
         "二是设计带噪声注入的可控生成策略；三是在虚构数据集上验证框架的有效性。"
         "GB/T 7714 规范了参考文献的著录格式，本文引用规范遵循其要求。")
    para("关键词：合成数据；数据增强；深度学习")

    # Abstract
    heading("Abstract")
    para("Acquiring real data is expensive and privacy constrained. "
         "This thesis studies controllable synthetic data generation for machine learning tasks. "
         "We design a generation framework with noise injection and quality control, "
         "and validate it on fictional datasets.")
    para("Keywords: synthetic data; data augmentation; deep learning")

    # 第1章
    heading("第1章 绪论")
    heading("1.1 研究背景", 2)
    # T2：伪空格"机器 学习"（摘要处为规范"机器学习"）
    p, idx = para("近年来，机器 学习技术在多个领域取得了显著进展，模型规模与数据规模同步增长。"
                  "合成数据成为缓解数据瓶颈的重要途径，其构建过程需要可复核的质量标准。")
    ledger.implant("T2", "term_variant", "stray_space_in_term", idx, "机器 学习",
                   {"check_type": "term_consistency", "field": "机器学习（伪空格变体）", "severity": "warn",
                    "detail": "与摘要处'机器学习'写法不一致（词内插空格）"})
    para("文献引用格式遵循国家标准 GB/T 7714 的著录规则。")
    heading("1.2 研究意义", 2)
    para("可控的合成数据生成能够为算法验证提供低成本样本，同时避免真实数据的隐私风险。")
    # A2：模板连接词（首先/其次/最后）
    p, idx = para("首先，本文构建了合成数据生成的总体框架。其次，本文设计了带噪声注入的可控生成策略。"
                  "最后，本文在虚构数据集上验证了方法的有效性。")
    ledger.implant("A2", "aigc_pattern", "template_connectors", idx, "首先，本文构建了",
                   {"check_type": "aigc_signal", "field": "aigc-02", "severity": "warn",
                    "detail": "模板连接词：首先/其次/最后 三段式套话"})

    # 第2章
    heading("第2章 相关工作")
    heading("2.1 合成数据生成", 2)
    para("生成对抗网络与扩散模型是合成图像数据的两条主要路线；表格数据的合成则以统计模型与自回归方法为主。")
    heading("2.2 文献综述方法", 2)
    # T4 第一处：标准号无空格（1.1 节为 GB/T 7714）
    # D3：悬空 REF 域（指向不存在书签）
    p, idx = para("本章文献的引用与著录依据 GB/T7714 的顺序编码制执行，如图3-1的域引用示例：")
    add_ref_field(p, BOOKMARK_DANGLING, "图9-9")
    ledger.fields.append({"para_index": idx, "instr": " REF {} \\h ".format(BOOKMARK_DANGLING),
                          "display": "图9-9", "target_bookmark": BOOKMARK_DANGLING, "bookmark_exists": False})
    ledger.implant("D3", "dangling_marker", "ref_field_missing_bookmark", idx, "REF _Ref99900099",
                   {"check_type": "dangling_reference", "field": "REF _Ref99900099（图9-9）", "severity": "error",
                    "detail": "REF 域指向的书签 _Ref99900099 在文档中不存在"})
    ledger.implant("T4", "term_variant", "standard_number_spacing", idx, "GB/T7714",
                   {"check_type": "term_consistency", "field": "GB/T 7714（空格不一致）", "severity": "warn",
                    "detail": "标准号写法 GB/T7714 与 1.1 节 GB/T 7714 不一致"})
    p, idx = para("典型的合成数据生成框架参见：")
    add_ref_field(p, BOOKMARK_FIG31, "图3-1")
    ledger.fields.append({"para_index": idx, "instr": " REF {} \\h ".format(BOOKMARK_FIG31),
                          "display": "图3-1", "target_bookmark": BOOKMARK_FIG31, "bookmark_exists": True})
    fig31_field_para = idx  # 有效域引用，计入图3-1 的提及

    # 第3章
    heading("第3章 方法")
    heading("3.1 总体框架", 2)
    p, idx = para("本方法的总体框架如图3-1所示，整体流程分为数据建模、可控生成与质量评估三个阶段。")
    fig31_hand_para = idx
    cap_p, cap_idx = caption("图3-1 方法总体框架")
    add_bookmark_to(cap_p, BOOKMARK_FIG31)
    ledger.object("figure", "图3-1", cap_idx, bookmark=BOOKMARK_FIG31,
                  mentioned_paras=[fig31_field_para, fig31_hand_para])
    para("框架中各模块的职责与数据流向保持单向，保证生成过程可复核、可复现。")
    p, idx = para("F1 = 2PR/(P+R)    （3-1）")
    ledger.object("equation", "式(3-1)", idx, mentioned_paras=[idx])
    heading("3.2 数据流程", 2)
    # T1 第一处：深度神经网络（4.2 节作"深层神经网络"）
    p, idx = para("数据经过清洗、标注与增强三个环节进入深度神经网络进行训练，全过程如图3-2所示。")
    t1 = ledger.implant("T1", "term_variant", "term_inconsistency", idx, "深度神经网络",
                        {"check_type": "term_consistency", "field": "深度神经网络/深层神经网络", "severity": "warn",
                         "detail": "同一概念两种叫法（4.2 节作'深层神经网络'）"})
    fig32_hand_para = idx
    cap_p, cap_idx = caption("图3-2 数据处理流程")
    ledger.object("figure", "图3-2", cap_idx, mentioned_paras=[fig32_hand_para])
    cap_p, cap_idx = caption("表3-1 虚构数据集统计信息")
    table31 = ledger.object("table", "表3-1", cap_idx, mentioned_paras=[])
    table = doc.add_table(rows=2, cols=3)
    for j, h in enumerate(("数据集", "样本数", "标注率")):
        table.rows[0].cells[j].text = h
    for j, v in enumerate(("虚构集A", "3500", "100%")):
        table.rows[1].cells[j].text = v

    # 第4章（S1：章标题降级为 Heading 2）
    heading("第4章 实验与结果分析", 2)
    s1_idx = ledger.paragraphs[-1]["i"]
    ledger.implant("S1", "style_error", "heading_level_downgraded", s1_idx, "第4章 实验与结果分析",
                   {"check_type": "style", "field": "heading_level", "severity": "error",
                    "detail": "章标题使用 Heading 2，应为 Heading 1"},
                   also_expect=[{"check_type": "structure_order", "field": "heading_sequence",
                                 "detail": "章级标题层级序列断档（第3章 H1 后接 H2）"}])
    heading("4.1 实验设置", 2)
    # D1：手打悬空标记（表 9-1 不存在）
    p, idx = para("训练细节如表 9-1 所示，本节还给出数据规模的统计。")
    ledger.implant("D1", "dangling_marker", "handwritten_missing_object", idx, "表 9-1",
                   {"check_type": "dangling_reference", "field": "表9-1", "severity": "error",
                    "detail": "正文提及'表 9-1'，全文不存在该对象"})
    # T3 第一处：千分位（4.2 节作 3500）
    p, idx = para("实验共使用 3,500 个样本，其中训练集占 80%。")
    t3 = ledger.implant("T3", "term_variant", "number_thousands_inconsistent", idx, "3,500 个样本",
                        {"check_type": "term_consistency", "field": "3500（千分位不一致）", "severity": "warn",
                         "detail": "数字写法 3,500 与 4.2 节 3500 不一致（GB/T 15835 数字用法口径）"})
    # S2：题注误用 Normal（图4-1）
    cap_p, cap_idx = caption("图4-1 各方法准确率对比", style="Normal")
    fig41 = ledger.object("figure", "图4-1", cap_idx, mentioned_paras=[])
    ledger.implant("S2", "style_error", "caption_style_wrong", cap_idx, "图4-1 各方法准确率对比",
                   {"check_type": "style", "field": "caption_style", "severity": "error",
                    "detail": "题注段落使用 Normal 样式，应为 Caption"})
    p, idx = para("各方法准确率如图4-1所示，本文方法在虚构集A上取得最优结果。")
    fig41["mentioned_paras"].append(idx)
    fig41["referenced"] = True
    cap_p, cap_idx = caption("表4-1 各方法在虚构集A上的指标对比")
    table41 = ledger.object("table", "表4-1", cap_idx, mentioned_paras=[])
    table = doc.add_table(rows=3, cols=3)
    for j, h in enumerate(("方法", "准确率", "F1")):
        table.rows[0].cells[j].text = h
    for r, row_vals in enumerate((("基线方法", "82.1", "80.5"), ("本文方法", "85.6", "84.0")), 1):
        for j, v in enumerate(row_vals):
            table.rows[r].cells[j].text = v
    p, idx = para("表4-1给出各方法的指标对比，式(4-1)定义了评价指标的计算方式。")
    table41["mentioned_paras"].append(idx)
    table41["referenced"] = True
    p, idx = para("F1 = 2*P*R/(P+R)    （4-1）")
    ledger.object("equation", "式(4-1)", idx, mentioned_paras=[idx])
    heading("4.2 结果分析", 2)
    # A1：套话重复 + 句长均匀
    p, idx = para("值得注意的是，实验结果证明了方法的有效性。值得注意的是，对比数据验证了模型的稳定性。"
                  "值得注意的是，消融分析确认了策略的可靠性。值得注意的是，参数分析支持了方案的可行性。")
    ledger.implant("A1", "aigc_pattern", "repeated_phrase_uniform_length", idx, "值得注意的是",
                   {"check_type": "aigc_signal", "field": "aigc-02", "severity": "warn",
                    "detail": "同一套话连用四次且句长高度均匀（aigc-01）"})
    # T1/T3 第二处
    p, idx = para("深层神经网络的容量随层数增加而扩大，共使用 3500 个样本进行评估。")
    t1["paras"].append(idx)
    t3["paras"].append(idx)
    # G1/G2：幽灵对象（从未被提及）
    cap_p, cap_idx = caption("图4-2 消融实验结果")
    ledger.object("figure", "图4-2", cap_idx, mentioned_paras=[])
    ledger.implant("G1", "ghost_object", "never_mentioned", cap_idx, "图4-2 消融实验结果",
                   {"check_type": "ghost_object", "field": "图4-2", "severity": "warn",
                    "detail": "对象存在但全文无任何提及"})
    cap_p, cap_idx = caption("表4-2 超参数设置")
    ledger.object("table", "表4-2", cap_idx, mentioned_paras=[])
    ledger.implant("G2", "ghost_object", "never_mentioned", cap_idx, "表4-2 超参数设置",
                   {"check_type": "ghost_object", "field": "表4-2", "severity": "warn",
                    "detail": "对象存在但全文无任何提及"})
    table = doc.add_table(rows=2, cols=3)
    for j, h in enumerate(("参数", "取值", "说明")):
        table.rows[0].cells[j].text = h
    for j, v in enumerate(("学习率", "0.001", "固定值")):
        table.rows[1].cells[j].text = v
    heading("4.3 消融实验", 2)
    para("消融实验结果见图4-2，逐一移除各模块后指标均有下降。")

    # 第5章（A3 套话 + S3 正文误用标题样式）
    heading("第5章 总结与展望")
    para("本文提出了面向机器学习任务的可控合成数据生成框架，并完成了系统性验证。")
    p, idx = para("综上所述，本文方法取得了良好的效果。总而言之，实验充分证明了本文方法的先进性。")
    ledger.implant("A3", "aigc_pattern", "summary_cliches", idx, "综上所述",
                   {"check_type": "aigc_signal", "field": "aigc-03", "severity": "warn",
                    "detail": "总结套话连用（综上所述/总而言之）"})
    para("未来工作将扩展框架到多模态场景，并进一步降低生成开销。", style="Heading 2")
    s3_idx = ledger.paragraphs[-1]["i"]
    ledger.implant("S3", "style_error", "body_styled_as_heading", s3_idx, "未来工作将扩展框架到多模态场景",
                   {"check_type": "style", "field": "body_style", "severity": "error",
                    "detail": "正文段落误用 Heading 2 样式"})

    # 参考文献（内容干净，文献线审计由 data/frozen/refs 承担）
    heading("参考文献")
    for r in [
        "[1] 张合成, 李虚构. 虚构场景下的合成数据生成框架[J]. 虚构学报, 2025, 48(3): 1-12.",
        "[2] 王杜撰. 合成数据质量评估综述[J]. 合成科学进展, 2024, 15(2): 33-45.",
        "[3] SMITH J. Synthetic Data Methods[M]. New York: Fake Academic Press, 2023.",
        "[4] 赵虚构. 面向表格数据的扩散模型研究[D]. 北京: 虚构理工大学, 2024.",
        "[5] 国家虚构标准化委员会. 合成数据通用要求: GB/T 99999—2025[S]. 北京: 虚构出版社, 2025.",
    ]:
        para(r)

    # 致谢
    heading("致谢")
    para("感谢虚构理工大学提供的虚构研究环境。本论文全部内容为程序化合成的测试数据。")
    return doc


def _save_deterministic(doc, path):
    """python-docx 保存后重写 zip：条目内容原样，时间戳固定 1980-01-01。"""
    path = Path(path)
    tmp = path.with_name(path.name + ".tmp")
    doc.save(str(tmp))
    with zipfile.ZipFile(str(tmp)) as src:
        entries = [(info.filename, src.read(info.filename)) for info in src.infolist()]
    tmp.unlink()
    with zipfile.ZipFile(str(path), "w", zipfile.ZIP_DEFLATED) as out:
        for name, data in entries:
            info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o600 << 16
            out.writestr(info, data)


def build_truth(ledger):
    counts = {
        "paragraphs": len(ledger.paragraphs),
        "objects": len(ledger.objects),
        "objects_by_kind": {},
        "implants": len(ledger.implants),
        "implants_by_kind": {},
        "fields": len(ledger.fields),
    }
    for o in ledger.objects:
        counts["objects_by_kind"][o["kind"]] = counts["objects_by_kind"].get(o["kind"], 0) + 1
    for i in ledger.implants:
        counts["implants_by_kind"][i["kind"]] = counts["implants_by_kind"].get(i["kind"], 0) + 1
    return {
        "schema_version": SCHEMA_VERSION,
        "dataset": DATASET_ID,
        "generator": "code/tools/gen_thesis_docx.py",
        "rng": "declarative（声明式内容模型，无随机抽取）",
        "seed": None,
        "implant_semantics": {
            "expect": "逐处植入的主期望（check_type/field/severity），引擎对该处必须产出",
            "also_expect": "同一植入隐含的其余非 pass 结论；对账按全部非 pass 集合（plan/04 §七）",
            "clean_paras": "未列入 implants 的段落应保持无非 pass 判定（判定出即误报）",
            "aigc": "AIGC 类 severity=warn：风险提示≠AIGC 判定（plan/04 §六伦理边界）",
            "style_tree_text": "与 python-docx .text 口径一致：fldSimple 内 run 不计入",
        },
        "counts": counts,
        "style_tree": ledger.paragraphs,
        "objects": ledger.objects,
        "fields": ledger.fields,
        "implants": ledger.implants,
        "doc_props_fixed": {"author": "张合成（taw 合成数据，非真实人物）",
                            "created": "2026-05-01T00:00:00", "modified": "2026-05-01T00:00:00", "revision": 1},
    }


def generate(out_dir):
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    ledger = Ledger()
    doc = build_document(ledger)
    _save_deterministic(doc, out_dir / "thesis_synthetic.docx")
    truth = build_truth(ledger)
    (out_dir / "thesis_truth.json").write_bytes(
        (json.dumps(truth, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8"))
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "dataset": DATASET_ID,
        "generator": "code/tools/gen_thesis_docx.py",
        "files": ["thesis_synthetic.docx", "thesis_truth.json", "thesis_manifest.json"],
        "zip_entry_timestamp_fixed": "1980-01-01（python-docx writestr 写当前时间的确定性收口）",
        "requires": "python-docx（extras docx）",
    }
    (out_dir / "thesis_manifest.json").write_bytes(
        (json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8"))
    return ["thesis_synthetic.docx", "thesis_truth.json", "thesis_manifest.json"]


def main(argv=None):
    parser = argparse.ArgumentParser(description="合成论文 docx 生成器（确定性声明式模型）")
    default_out = REPO_ROOT / "data" / "frozen" / "thesis"
    parser.add_argument("--out", default=str(default_out), help="输出目录（默认 {}）".format(default_out))
    parser.add_argument("--force", action="store_true", help="允许覆盖已有文件")
    args = parser.parse_args(argv)
    out_dir = Path(args.out)
    if out_dir.exists() and any(out_dir.iterdir()) and not args.force:
        print("[gen_thesis_docx] 目标目录非空且未给 --force，拒绝覆盖：{}".format(out_dir))
        return 1
    written = generate(out_dir)
    print("[gen_thesis_docx] 写出 {} 个文件 -> {}".format(len(written), out_dir))
    for name in written:
        print("  {}".format(name))
    return 0


if __name__ == "__main__":
    sys.exit(main())
