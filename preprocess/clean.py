import os
import re
from collections import Counter


def clean_text_lines(lines, min_repeated=3):
    """
    清洗 txt 文件的行内容，去掉页码/目录/页眉页脚等噪声。
    :param lines: 原始行列表
    :param min_repeated: 认为是页眉页脚的最小重复次数
    :return: 清洗后的行列表
    """
    cleaned = []
    freq = Counter([line.strip() for line in lines if line.strip()])

    for line in lines:
        stripped = line.strip()

        # 过滤空行
        if not stripped:
            continue

        # 过滤单独的页码（例如：41）
        if re.fullmatch(r"\d+", stripped):
            continue

        # 过滤带章节号 + 页码的目录行，例如 "第2章 卫星总体设计      41"
        if re.match(r"^第?\s*\d+章.*\d+$", stripped):
            continue

        # 过滤高频短语（页眉/页脚，通常短且重复很多次）
        if freq[stripped] >= min_repeated and len(stripped) <= 15:
            continue

        # 去掉末尾页码，例如 "第2章 卫星总体设计  41" → "第2章 卫星总体设计"
        stripped = re.sub(r"\s+\d+$", "", stripped)

        cleaned.append(stripped)

    return cleaned


def clean_file(input_path, output_path=None):
    """
    清洗单个 txt 文件
    :param input_path: 输入文件路径
    :param output_path: 输出文件路径（默认在同目录下生成 *_cleaned.txt）
    """
    if not output_path:
        base, ext = os.path.splitext(input_path)
        output_path = base + "_cleaned.txt"

    with open(input_path, "r", encoding="utf-8") as f:
        lines = f.readlines()

    cleaned_lines = clean_text_lines(lines)

    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(cleaned_lines))

    print(f"✅ Cleaned file saved: {output_path}")


def batch_clean(directory):
    """
    批量清洗目录下的所有 txt 文件
    """
    for filename in os.listdir(directory):
        if filename.endswith(".txt") and not filename.endswith("_cleaned.txt"):
            input_path = os.path.join(directory, filename)
            clean_file(input_path)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Clean converted txt files (remove page numbers, headers, TOC)")
    parser.add_argument("path", help="Input file or directory")
    args = parser.parse_args()

    if os.path.isdir(args.path):
        batch_clean(args.path)
    else:
        clean_file(args.path)
