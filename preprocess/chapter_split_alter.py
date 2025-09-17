# 本文件用于对书本进行章节拆分，便于后处理，结果输出到指定的文件夹中

import re
import os

def parse_section_number(sec_num):
    try:
        return tuple(map(int, sec_num.strip().split('.')))
    except:
        return (-1,)

def extract_titles_with_positions(text):
    # 1) 更严格的“第X章”匹配：
    # - 必须整行（^...$，MULTILINE）
    # - “章”后允许标题，但不允许出现明显句子标点（。；；？！、括号等）
    # - 允许末尾出现页码，用后处理裁掉
    chapter_pattern = re.compile(
        r'^[ \t\u3000]*第(?:[0-9一二三四五六七八九十百]+)章'               # 第X章（阿拉伯或中文数字）
        r'(?:[ \t\u3000]+[^\n，。,。、；;？！?!（）()\[\]“”\"\'<>]+)?'   # 可选标题，但避免句子标点/括号等
        r'[ \t\u3000]*$',                                                # 到行尾
        re.MULTILINE
    )

    # 2) 更严格的“一级小节 N.N 标题”匹配：
    # - 必须整行
    # - 数字后必须有空白
    # - 标题第一个可见字符必须是中文或英文字母（避免 ~ - . 数字 开头的量纲/区间/数值行）
    section_pattern = re.compile(
        r'^[ \t\u3000]*'          # 行首空白
        r'(\d+\.\d+)(?!\.\d)'     # N.N（禁止 N.N.x）
        r'[ \t\u3000]+'           # 至少一个空白
        r'(?=[\u4e00-\u9fffA-Za-z])'  # 下一字符必须是中文或英文字母
        r'([^\n]*?)'              # 标题内容
        r'[ \t\u3000]*$',         # 行尾空白
        re.MULTILINE
    )

    matches = []

    print("🔍 开始匹配章节标题...")
    for m in chapter_pattern.finditer(text):
        raw = m.group(0).strip()
        # 裁掉行尾页码（常见为若干空格后跟 1-4 位数字）
        clean = re.sub(r'[ \t\u3000]+\d{1,4}[ \t\u3000]*$', '', raw)
        print(f"  ➕ 章节标题: {clean} @ {m.start()}")
        matches.append((m.start(), "chapter", clean))

    print("🔍 开始匹配一级小节标题...")
    last_sec_number = (-1,)
    for m in section_pattern.finditer(text):
        sec_num = m.group(1)
        sec_title = m.group(2).strip()
        full_title = f"{sec_num} {sec_title}".strip()
        current_number = parse_section_number(sec_num)

        if current_number > last_sec_number:
            print(f"  ✅ 小节标题: {full_title} @ {m.start()}")
            matches.append((m.start(), "section", full_title))
            last_sec_number = current_number
        else:
            print(f"  ⚠️ 跳过疑似无效小节: {full_title}（非递增）")

    # 排序确保顺序一致
    matches.sort(key=lambda x: x[0])
    return matches

def split_text_by_titles(text, matches, output_dir="satellite_split_output_alter"):
    os.makedirs(output_dir, exist_ok=True)

    segments = []
    for i in range(len(matches)):
        start_pos = matches[i][0]
        end_pos = matches[i+1][0] if i + 1 < len(matches) else len(text)
        title_type, title = matches[i][1], matches[i][2]
        segment_text = text[start_pos:end_pos].strip()
        print(f"✂️ 切分段落 [{title_type}] {title}，长度：{len(segment_text)} 字符")
        segments.append((title_type, title, segment_text))

    chapter_intro_blocks = []

    for title_type, title, content in segments:
        if title_type == "section":
            sec_num = title.split()[0]
            filename = f"{sec_num.replace('.', '_')}.txt"
            filepath = os.path.join(output_dir, filename)
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(f"{title}\n\n{content}")
            print(f"💾 写入小节文件：{filename}")
        else:  # chapter
            chapter_intro_blocks.append(f"{title}\n{content}")
            print(f"📌 收录章节引言：{title}")

    intro_path = os.path.join(output_dir, "chapter_intros.txt")
    with open(intro_path, "w", encoding="utf-8") as f:
        f.write("\n\n".join(chapter_intro_blocks))
    print("✅ 拆分完成：章节引言保存在 chapter_intros.txt，小节分别保存为多个文件。")

# 示例使用
if __name__ == "__main__":
    # with open("./to_text.txt", "r", encoding="utf-8") as f:
    #     text = f.read()
    with open("../modified.txt", "r", encoding="utf-8") as f:
        text = f.read()
    matches = extract_titles_with_positions(text)
    split_text_by_titles(text, matches)
