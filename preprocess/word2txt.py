from docx import Document
import pdfplumber
import re

# 处理 docx，忽略页眉页脚
def docx_to_txt(path):
    doc = Document(path)
    text_list = []

    # 只取正文段落
    for para in doc.paragraphs:
        if para.text.strip():  # 去掉空行
            text_list.append(para.text.strip())

    return "\n".join(text_list)

# 处理 pdf，忽略页眉页脚（通过位置或模式过滤）
def pdf_to_txt(path):
    text_list = []
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            # 获取页面高度，用于过滤页眉/页脚
            height = page.height
            lines = page.extract_text_lines()  # 更精准控制行位置

            for line in lines:
                y = line["top"]  # 行的纵坐标
                text = line["text"].strip()

                # 忽略页眉（太靠上）和页脚（太靠下）
                if y < 50 or y > height - 50:
                    continue

                # 过滤掉页码、目录页模式
                if re.match(r'^\s*\d+\s*$', text):  # 纯数字页码
                    continue
                if re.match(r'^第.+章', text):  # 目录标题之类
                    continue

                text_list.append(text)

    return "\n".join(text_list)


if __name__ == "__main__":
    docx_txt = docx_to_txt("./../卫星工程.docx")
    with open("output_docx.txt", "w", encoding="utf-8") as f:
        f.write(docx_txt)

    # pdf_txt = pdf_to_txt("./../example.pdf")
    # with open("output_pdf.txt", "w", encoding="utf-8") as f:
    #     f.write(pdf_txt)
